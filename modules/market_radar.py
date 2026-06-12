#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
market_radar.py

AI Intel Bot V5 - Market Radar
Principle:
- No fake fallback.
- TXF/WTXP data must come from TAIFEX MIS.
- If TXF/WTXP cannot be identified reliably, show ERROR / 資料暫缺.
- Do NOT use TAIEX spot index as a substitute for TXF night session.

Expected path:
    /config/workspace/modules/market_radar.py

Run test:
    cd /config/workspace
    source .venv/bin/activate
    python modules/market_radar.py
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

try:
    import pytz
except Exception:
    pytz = None

try:
    import yfinance as yf
except Exception:
    yf = None


TAIPEI_TZ_NAME = "Asia/Taipei"


@dataclass
class Quote:
    symbol: str
    name: str
    source: str
    status: str  # OK / ERROR / STALE
    price: Optional[float] = None
    change: Optional[float] = None
    change_pct: Optional[float] = None
    volume: Optional[float] = None
    quote_time: Optional[str] = None
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _now_taipei() -> datetime:
    if pytz:
        return datetime.now(pytz.timezone(TAIPEI_TZ_NAME))
    return datetime.now(timezone.utc)


def _to_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return None
        return float(v)
    s = str(v).strip()
    if not s or s in {"-", "--", "N/A", "NaN", "nan", "None"}:
        return None
    s = s.replace(",", "").replace("%", "")
    m = re.search(r"[-+]?\d+(?:\.\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except Exception:
        return None


def _find_first_existing(row: Dict[str, Any], keys: List[str]) -> Any:
    for k in keys:
        if k in row and row[k] not in ("", "-", None):
            return row[k]
    return None


def _extract_taifex_rows(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    candidates: List[Any] = [
        data.get("RtData", {}).get("QuoteList"),
        data.get("RtData", {}).get("Items"),
        data.get("RtData", {}).get("Quote"),
        data.get("QuoteList"),
        data.get("Items"),
        data.get("data"),
    ]

    for c in candidates:
        if isinstance(c, list) and c and all(isinstance(x, dict) for x in c):
            return c

    lists: List[List[Dict[str, Any]]] = []

    def walk(x: Any) -> None:
        if isinstance(x, list):
            if x and all(isinstance(i, dict) for i in x):
                lists.append(x)
            for i in x:
                walk(i)
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)

    walk(data)
    if not lists:
        return []
    return sorted(lists, key=len, reverse=True)[0]


def _row_text(row: Dict[str, Any]) -> str:
    return json.dumps(row, ensure_ascii=False)


def _select_txf_row(rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Select Taiwan index futures night-session row.

    Some quote pages display night session as WTXP&.
    Do not accept TAIEX spot index / 加權指數 as TXF.
    """
    if not rows:
        return None

    exclude_keywords = [
        "加權指數",
        "發行量加權",
        "TAIEX",
        "TSE",
        "TWSE",
        "IX0001",
    ]

    strong_keywords = [
        "WTXP&",
        "WTXP",
        "TXF",
        "台指期盤後",
        "臺指期盤後",
        "台指期",
        "臺指期",
        "臺股期貨",
        "台股期貨",
        "TAIEX Futures",
    ]

    scored: List[tuple[int, Dict[str, Any]]] = []

    for row in rows:
        text = _row_text(row)

        if any(k in text for k in exclude_keywords):
            continue

        score = 0
        for i, kw in enumerate(strong_keywords):
            if kw in text:
                score += 100 - i * 4

        if "期貨" in text:
            score += 20
        if "盤後" in text:
            score += 30
        if "近月" in text:
            score += 10
        if ("指數" in text and "期" not in text) or "加權" in text:
            score -= 50

        if score > 0:
            scored.append((score, row))

    if not scored:
        return None

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]


def _parse_taifex_quote_time(row: Dict[str, Any]) -> Optional[str]:
    raw = _find_first_existing(
        row,
        ["CTime", "Time", "QuoteTime", "DateTime", "CDateTime", "成交時間", "時間"],
    )
    return str(raw) if raw else None


def _parse_taifex_price(row: Dict[str, Any]) -> Optional[float]:
    return _to_float(
        _find_first_existing(
            row,
            ["CLastPrice", "LastPrice", "Last", "Price", "Close", "成交價", "收盤價", "最新價"],
        )
    )


def _parse_taifex_change(row: Dict[str, Any]) -> Optional[float]:
    return _to_float(
        _find_first_existing(
            row,
            ["CDiff", "Diff", "Change", "PriceChange", "漲跌", "漲跌價"],
        )
    )


def _parse_taifex_change_pct(row: Dict[str, Any], price: Optional[float], change: Optional[float]) -> Optional[float]:
    val = _to_float(
        _find_first_existing(row, ["CChangePercent", "ChangePercent", "ChangeRate", "漲跌幅", "漲跌%"])
    )
    if val is not None:
        return val

    ref = _to_float(
        _find_first_existing(row, ["CRefPrice", "RefPrice", "PreviousClose", "PrevClose", "昨收", "參考價"])
    )
    if ref and change is not None:
        return change / ref * 100

    if price is not None and change is not None and price != change:
        prev = price - change
        if prev:
            return change / prev * 100

    return None


def _parse_taifex_volume(row: Dict[str, Any]) -> Optional[float]:
    return _to_float(
        _find_first_existing(row, ["CTotalVolume", "TotalVolume", "Volume", "成交量", "累計成交量"])
    )


def fetch_txf_from_taifex(timeout: int = 12) -> Quote:
    url = "https://mis.taifex.com.tw/futures/api/getQuoteList"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json;charset=UTF-8",
        "Origin": "https://mis.taifex.com.tw",
        "Referer": "https://mis.taifex.com.tw/futures/",
    }

    payloads = [
        {
            "MarketType": "1",
            "SymbolType": "F",
            "KindID": "1",
            "CID": "TXF",
            "ExpireMonth": "",
            "RowSize": "全部",
            "PageNo": "",
            "SortColumn": "",
            "AscDesc": "A",
        },
        {
            "MarketType": "0",
            "SymbolType": "F",
            "KindID": "1",
            "CID": "TXF",
            "ExpireMonth": "",
            "RowSize": "全部",
            "PageNo": "",
            "SortColumn": "",
            "AscDesc": "A",
        },
        {
            "MarketType": "1",
            "SymbolType": "F",
            "KindID": "1",
            "CID": "WTXP",
            "ExpireMonth": "",
            "RowSize": "全部",
            "PageNo": "",
            "SortColumn": "",
            "AscDesc": "A",
        },
    ]

    errors: List[str] = []

    for payload in payloads:
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=timeout)
            r.raise_for_status()
            data = r.json()

            rows = _extract_taifex_rows(data)
            if not rows:
                errors.append(f"empty rows for CID={payload.get('CID')} MT={payload.get('MarketType')}")
                continue

            target = _select_txf_row(rows)
            if target is None:
                sample = [_row_text(x)[:220] for x in rows[:3]]
                errors.append("no TXF/WTXP row matched; samples=" + " || ".join(sample))
                continue

            text = _row_text(target)
            if "加權指數" in text or "發行量加權" in text:
                errors.append("matched row is TAIEX spot index, rejected")
                continue

            price = _parse_taifex_price(target)
            change = _parse_taifex_change(target)
            change_pct = _parse_taifex_change_pct(target, price, change)
            volume = _parse_taifex_volume(target)
            quote_time = _parse_taifex_quote_time(target)

            if price is None:
                errors.append("matched TXF row but price is empty")
                continue

            return Quote(
                symbol="TXF",
                name="台指期盤後/近月",
                source="TAIFEX MIS",
                status="OK",
                price=price,
                change=change,
                change_pct=change_pct,
                volume=volume,
                quote_time=quote_time,
                message="TAIFEX MIS 即時行情；未使用台股現貨指數替代。",
            )

        except Exception as e:
            errors.append(f"{payload.get('CID')} MT={payload.get('MarketType')}: {e}")

    return Quote(
        symbol="TXF",
        name="台指期盤後/近月",
        source="TAIFEX MIS",
        status="ERROR",
        price=None,
        change=None,
        change_pct=None,
        volume=None,
        quote_time=None,
        message="TAIFEX MIS 讀取或辨識失敗；不使用台股現貨指數替代。錯誤：" + " | ".join(errors[:3]),
    )


def fetch_yfinance_quote(symbol: str, name: str, timeout: int = 12) -> Quote:
    if yf is None:
        return Quote(symbol=symbol, name=name, source="Yahoo Finance/yfinance", status="ERROR", message="yfinance not installed")

    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="2d", interval="5m")
        if hist is None or hist.empty:
            hist = ticker.history(period="5d", interval="1d")

        if hist is None or hist.empty:
            return Quote(symbol=symbol, name=name, source="Yahoo Finance/yfinance", status="ERROR", message="empty history")

        last = hist.iloc[-1]
        price = _to_float(last.get("Close"))

        prev_close = None
        if len(hist) >= 2:
            prev_close = _to_float(hist.iloc[-2].get("Close"))

        change = None
        change_pct = None
        if price is not None and prev_close is not None:
            change = price - prev_close
            if prev_close:
                change_pct = change / prev_close * 100

        quote_time = None
        try:
            quote_time = str(hist.index[-1])
        except Exception:
            pass

        volume = _to_float(last.get("Volume"))

        return Quote(
            symbol=symbol,
            name=name,
            source="Yahoo Finance/yfinance",
            status="OK",
            price=price,
            change=change,
            change_pct=change_pct,
            volume=volume,
            quote_time=quote_time,
            message="",
        )
    except Exception as e:
        return Quote(symbol=symbol, name=name, source="Yahoo Finance/yfinance", status="ERROR", message=str(e))


def calculate_risk_score(quotes: Dict[str, Quote]) -> Dict[str, Any]:
    score = 50
    reasons: List[str] = []

    def add_if(q: Optional[Quote], label: str, bullish_when_positive: bool = True, weight: int = 8) -> None:
        nonlocal score
        if not q or q.status != "OK" or q.change_pct is None:
            return
        pct = q.change_pct
        if bullish_when_positive:
            if pct > 0.25:
                score += weight
                reasons.append(f"{label} {pct:+.2f}% → 利多")
            elif pct < -0.25:
                score -= weight
                reasons.append(f"{label} {pct:+.2f}% → 利空")
        else:
            if pct < -1.0:
                score += weight
                reasons.append(f"{label} {pct:+.2f}% → 利多")
            elif pct > 1.0:
                score -= weight
                reasons.append(f"{label} {pct:+.2f}% → 利空")

    add_if(quotes.get("txf"), "台指期", True, 12)
    add_if(quotes.get("nasdaq_fut"), "Nasdaq期貨", True, 10)
    add_if(quotes.get("sp500_fut"), "S&P期貨", True, 8)
    add_if(quotes.get("vix"), "VIX", False, 10)
    add_if(quotes.get("dxy"), "美元指數", False, 4)
    add_if(quotes.get("us10y"), "美債10Y", False, 4)

    score = max(0, min(100, score))

    if score >= 70:
        mood = "Risk ON"
        emoji = "🟢"
    elif score <= 35:
        mood = "Risk OFF"
        emoji = "🔴"
    else:
        mood = "Neutral"
        emoji = "🟡"

    return {"score": score, "mood": mood, "emoji": emoji, "reasons": reasons}


def get_market_radar() -> Dict[str, Any]:
    quotes = {
        "txf": fetch_txf_from_taifex(),
        "nasdaq_fut": fetch_yfinance_quote("NQ=F", "Nasdaq 100 Futures"),
        "sp500_fut": fetch_yfinance_quote("ES=F", "S&P 500 Futures"),
        "vix": fetch_yfinance_quote("^VIX", "VIX"),
        "dxy": fetch_yfinance_quote("DX-Y.NYB", "US Dollar Index"),
        "us10y": fetch_yfinance_quote("^TNX", "US 10Y Treasury Yield"),
    }

    return {
        "generated_at": _now_taipei().strftime("%Y-%m-%d %H:%M:%S %Z"),
        "principle": "No fake fallback: TXF 抓不到或辨識不到就顯示資料暫缺，不用台股現貨指數替代。",
        "quotes": {k: v.to_dict() for k, v in quotes.items()},
        "risk": calculate_risk_score(quotes),
    }


def _fmt_num(v: Optional[float], digits: int = 2) -> str:
    if v is None:
        return "N/A"
    return f"{v:,.{digits}f}"


def _fmt_pct(v: Optional[float]) -> str:
    if v is None:
        return "N/A"
    return f"{v:+.2f}%"


def _fmt_change(v: Optional[float]) -> str:
    if v is None:
        return "N/A"
    return f"{v:+.2f}"


def format_market_radar_text(radar: Dict[str, Any]) -> str:
    quotes = radar.get("quotes", {})
    risk = radar.get("risk", {})

    def qline(key: str, label: str) -> str:
        q = quotes.get(key, {})
        if q.get("status") != "OK":
            return f"{label}：資料暫缺"
        return (
            f"{label}：{_fmt_num(q.get('price'))} | "
            f"{_fmt_change(q.get('change'))} | {_fmt_pct(q.get('change_pct'))}"
        )

    lines = [
        "🌙 Market Radar",
        f"{risk.get('emoji', '🟡')} {risk.get('mood', 'Neutral')} | Score {risk.get('score', 50)}/100",
        "",
        qline("txf", "台指期盤後/近月"),
        qline("nasdaq_fut", "Nasdaq期貨"),
        qline("sp500_fut", "S&P期貨"),
        qline("vix", "VIX"),
        qline("dxy", "美元指數"),
        qline("us10y", "美債10Y"),
    ]

    reasons = risk.get("reasons") or []
    if reasons:
        lines += ["", "重點："]
        lines += [f"- {r}" for r in reasons[:4]]

    lines += ["", "原則：TXF 抓不到或辨識不到就顯示資料暫缺，不以台股現貨指數替代。"]
    return "\n".join(lines)


if __name__ == "__main__":
    radar = get_market_radar()
    print(json.dumps(radar, ensure_ascii=False, indent=2))
    print()
    print(format_market_radar_text(radar))
