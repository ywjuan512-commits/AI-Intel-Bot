import argparse
import logging
import os
import re
import json
import sys
import time
import requests
import feedparser
from datetime import datetime
from dotenv import load_dotenv
from anthropic import Anthropic

from modules.market_radar import get_market_radar, format_market_radar_text

from config import (
    RSS_FEEDS,
    STOCK_SYMBOLS,
    REDDIT_SUBREDDITS,
    KEYWORDS,
    DISCOVERY_KEYWORDS,
    AI_SUPPLY_CHAIN,
    TAIWAN_THEMES,
    TAIWAN_AI_KEYWORDS,
    ELON_ECOSYSTEM,
    DISCOVERY_LIMITS,
    PROMPT_LIMITS,
)

load_dotenv(override=True)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")

client = Anthropic(api_key=ANTHROPIC_API_KEY)

logger = logging.getLogger("ai_intel_report")


def setup_logging():
    os.makedirs("logs", exist_ok=True)
    log_path = os.path.join("logs", f"ai_intel_bot_{datetime.now().strftime('%Y-%m-%d')}.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_path, encoding="utf-8"),
        ],
    )
    logger.info("Logging initialized: %s", log_path)



# =====================
# Basic helpers
# =====================

def clean_text(value, limit=220):
    if not value:
        return ""
    text = re.sub(r"<.*?>", "", str(value))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def safe_get(data, path, default=None):
    cur = data
    for key in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
        if cur is None:
            return default
    return cur


# =====================
# RSS / news collectors
# =====================

def fetch_rss_items(feed_url, limit=3):
    headers = {"User-Agent": "personal-ai-intel-bot/1.0"}
    response = requests.get(feed_url, headers=headers, timeout=15)
    response.raise_for_status()
    feed = feedparser.parse(response.content)
    if getattr(feed, "bozo", False):
        logger.warning("RSS parse warning for %s: %s", feed_url, getattr(feed, "bozo_exception", "unknown"))

    items = []

    for entry in feed.entries[:limit]:
        items.append({
            "title": clean_text(entry.get("title", ""), 160),
            "link": entry.get("link", ""),
            "summary": clean_text(entry.get("summary", ""), 220),
        })

    return items


def fetch_all_rss():
    results = {}
    source_status = {}
    per_feed = DISCOVERY_LIMITS.get("rss_per_feed", 3)

    for category, urls in RSS_FEEDS.items():
        category_items = []
        feed_statuses = []

        for url in urls:
            try:
                items = fetch_rss_items(url, limit=per_feed)
                category_items.extend(items)
                feed_statuses.append({
                    "url": url,
                    "status": "OK",
                    "items": len(items),
                })
            except Exception as e:
                logger.warning("RSS讀取失敗：%s (%s)", url, e)
                category_items.append({
                    "title": f"RSS讀取失敗：{url}",
                    "link": "",
                    "summary": str(e),
                })
                feed_statuses.append({
                    "url": url,
                    "status": "ERROR",
                    "error": str(e),
                })

        results[category] = category_items[:7]
        source_status[category] = feed_statuses

    return {"status": source_status, "items": results}


def fetch_yahoo_stock_news(symbol):
    url = f"https://finance.yahoo.com/rss/headline?s={symbol}"

    try:
        return fetch_rss_items(url, limit=3)
    except Exception as e:
        return [{
            "title": f"{symbol} 新聞讀取失敗",
            "link": "",
            "summary": str(e),
        }]


def fetch_stock_news():
    return {
        symbol: fetch_yahoo_stock_news(symbol)
        for symbol in STOCK_SYMBOLS
    }


def fetch_global_discovery_candidates(rss_data):
    candidates = []

    rss_items = rss_data.get("items", rss_data)
    for category, items in rss_items.items():
        for item in items:
            text = f"{item.get('title', '')} {item.get('summary', '')}".lower()

            if any(k.lower() in text for k in DISCOVERY_KEYWORDS):
                candidates.append({
                    "source": category,
                    "title": item.get("title", ""),
                    "summary": item.get("summary", ""),
                    "link": item.get("link", ""),
                })

    return candidates[:DISCOVERY_LIMITS.get("dynamic_candidates", 10)]


# =====================
# Reddit collectors
# =====================

def fetch_reddit_hot(subreddit, limit=10):
    url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"
    headers = {"User-Agent": "personal-ai-intel-bot/1.0"}

    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()

        posts = []

        for child in data["data"]["children"]:
            post = child["data"]
            title = clean_text(post.get("title", ""), 180)
            body = clean_text(post.get("selftext", ""), 220)
            text = f"{title} {body}"

            if any(k.lower() in text.lower() for k in KEYWORDS):
                posts.append({
                    "subreddit": subreddit,
                    "title": title,
                    "score": post.get("score", 0),
                    "comments": post.get("num_comments", 0),
                    "url": "https://reddit.com" + post.get("permalink", ""),
                })

        posts = sorted(
            posts,
            key=lambda x: x.get("score", 0) + x.get("comments", 0) * 2,
            reverse=True,
        )

        return posts[:DISCOVERY_LIMITS.get("reddit_posts", 6)]

    except Exception as e:
        return [{
            "subreddit": subreddit,
            "title": f"Reddit r/{subreddit} 讀取失敗",
            "score": 0,
            "comments": 0,
            "url": str(e),
        }]


def fetch_reddit_discussions():
    return {
        subreddit: fetch_reddit_hot(subreddit)
        for subreddit in REDDIT_SUBREDDITS
    }


def fetch_reddit_discovery(reddit_data):
    candidates = []

    for subreddit, posts in reddit_data.items():
        for post in posts:
            score = post.get("score", 0)
            comments = post.get("comments", 0)

            if score >= 50 or comments >= 30:
                candidates.append(post)

    candidates = sorted(
        candidates,
        key=lambda x: x.get("score", 0) + x.get("comments", 0) * 2,
        reverse=True,
    )

    return candidates[:DISCOVERY_LIMITS.get("dynamic_candidates", 10)]


# =====================
# TWSE collectors
# =====================

def fetch_twse_hot_stocks():
    url = "https://www.twse.com.tw/exchangeReport/MI_INDEX?response=json&type=ALLBUT0999"

    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        data = r.json()

        target_table = None

        for table in data.get("tables", []):
            if "每日收盤行情" in table.get("title", ""):
                target_table = table
                break

        if not target_table:
            return [{"error": "找不到台股每日收盤行情資料"}]

        fields = target_table["fields"]
        rows = target_table["data"]
        result = []

        for row in rows:
            item = dict(zip(fields, row))

            try:
                amount = int(item.get("成交金額", "0").replace(",", ""))
            except Exception:
                amount = 0

            try:
                change = float(
                    str(item.get("漲跌價差", "0"))
                    .replace("X", "0")
                    .replace("+", "")
                    .replace(",", "")
                )
            except Exception:
                change = 0

            result.append({
                "代號": item.get("證券代號"),
                "名稱": item.get("證券名稱"),
                "收盤價": item.get("收盤價"),
                "漲跌價差": item.get("漲跌價差"),
                "成交金額": amount,
                "change_num": change,
            })

        return sorted(
            result,
            key=lambda x: x["成交金額"],
            reverse=True,
        )[:DISCOVERY_LIMITS.get("twse_top_stocks", 25)]

    except Exception as e:
        return [{"error": str(e)}]


def fetch_twse_discovery(twse_hot):
    candidates = []

    for item in twse_hot:
        name = str(item.get("名稱", ""))
        amount = item.get("成交金額", 0)
        change = item.get("change_num", 0)

        matched_theme = []

        for theme, stocks in TAIWAN_THEMES.items():
            if name in stocks:
                matched_theme.append(theme)

        keyword_hit = any(k in name for k in TAIWAN_AI_KEYWORDS)

        if matched_theme or keyword_hit or abs(change) > 3 or amount > 3_000_000_000:
            candidates.append({
                "代號": item.get("代號"),
                "名稱": name,
                "收盤價": item.get("收盤價"),
                "漲跌價差": item.get("漲跌價差"),
                "成交金額": amount,
                "可能題材": matched_theme or ["成交金額/漲跌異常"],
            })

    return candidates[:DISCOVERY_LIMITS.get("dynamic_candidates", 10)]


# =====================
# Market radar
# =====================

def fetch_market_radar_safe():
    try:
        return get_market_radar()
    except Exception as e:
        return {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "principle": "Market Radar 讀取失敗時，不使用替代假資料。",
            "error": str(e),
            "quotes": {},
            "risk": {
                "score": 50,
                "mood": "Neutral",
                "emoji": "🟡",
                "reasons": ["Market Radar 讀取失敗，暫不納入風險判斷"],
            },
        }


def build_source_status(market_radar, rss, stock_news, reddit, twse_hot):
    def has_error_items(items):
        return any(
            isinstance(item, dict)
            and (
                item.get("error")
                or "讀取失敗" in str(item.get("title", ""))
                or item.get("status") == "ERROR"
            )
            for item in items
        )

    stock_errors = {
        symbol: "ERROR" if has_error_items(items) else "OK"
        for symbol, items in stock_news.items()
    }
    reddit_errors = {
        subreddit: "ERROR" if has_error_items(posts) else "OK"
        for subreddit, posts in reddit.items()
    }

    return {
        "market_radar": "ERROR" if market_radar.get("error") else "OK",
        "rss": rss.get("status", {}),
        "stock_news": stock_errors,
        "reddit": reddit_errors,
        "twse": "ERROR" if has_error_items(twse_hot) else "OK",
    }


# =====================
# Prompt compaction
# =====================

def compact_data_for_prompt(data):
    compact = dict(data)

    max_rss = PROMPT_LIMITS.get("max_rss_items", 20)
    max_reddit = PROMPT_LIMITS.get("max_reddit_items", 15)
    max_dynamic = PROMPT_LIMITS.get("max_dynamic_items", 10)

    rss_flat = []
    rss_data = data.get("rss", {})
    rss_items = rss_data.get("items", rss_data)
    for category, items in rss_items.items():
        for item in items:
            rss_flat.append({
                "category": category,
                "title": item.get("title", ""),
                "summary": item.get("summary", ""),
            })

    compact["rss_compact"] = rss_flat[:max_rss]
    compact.pop("rss", None)

    reddit_flat = []
    for subreddit, posts in data.get("reddit", {}).items():
        for post in posts:
            reddit_flat.append({
                "subreddit": subreddit,
                "title": post.get("title", ""),
                "score": post.get("score", 0),
                "comments": post.get("comments", 0),
            })

    compact["reddit_compact"] = reddit_flat[:max_reddit]
    compact.pop("reddit", None)

    if "dynamic_discovery" in compact:
        compact["dynamic_discovery"]["twse_candidates"] = compact["dynamic_discovery"].get("twse_candidates", [])[:max_dynamic]
        compact["dynamic_discovery"]["global_candidates"] = compact["dynamic_discovery"].get("global_candidates", [])[:max_dynamic]
        compact["dynamic_discovery"]["reddit_candidates"] = compact["dynamic_discovery"].get("reddit_candidates", [])[:max_dynamic]

    return compact


def build_input_data():
    source_metrics = {}

    def timed(name, func):
        started = time.perf_counter()
        value = func()
        source_metrics[f"{name}_seconds"] = round(time.perf_counter() - started, 2)
        logger.info("%s completed in %.2fs", name, source_metrics[f"{name}_seconds"])
        return value

    market_radar = timed("market_radar", fetch_market_radar_safe)
    rss = timed("rss", fetch_all_rss)
    stock_news = timed("stock_news", fetch_stock_news)
    reddit = timed("reddit", fetch_reddit_discussions)
    twse_hot = timed("twse", fetch_twse_hot_stocks)

    data = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_metrics": source_metrics,
        "source_status": build_source_status(market_radar, rss, stock_news, reddit, twse_hot),
        "market_radar": market_radar,
        "ai_supply_chain_reference": AI_SUPPLY_CHAIN,
        "taiwan_themes_reference": TAIWAN_THEMES,
        "elon_ecosystem_reference": ELON_ECOSYSTEM,
        "stock_news": stock_news,
        "rss": rss,
        "reddit": reddit,
        "twse_hot": twse_hot,
        "dynamic_discovery": {
            "twse_candidates": fetch_twse_discovery(twse_hot),
            "global_candidates": fetch_global_discovery_candidates(rss),
            "reddit_candidates": fetch_reddit_discovery(reddit),
        },
    }

    return compact_data_for_prompt(data)


# =====================
# Claude Prompt
# =====================

def build_prompt(data):
    return f"""
你是我的私人 Bloomberg AI 情報終端，請根據資料產出「決策型情報」，不是新聞文章。

核心原則：
1. 分析順序必須是「產業 → 供應鏈 → 公司」，不得先從固定公司出發。
2. 不要固定只分析 MU、NVDA、TSM、TSLA、AVGO、MRVL；請先找今天真正強的產業與資金流，再挑出代表標的。
3. Tesla / SpaceX / xAI 不要單獨佔版面；只有重大事件才放入 Discovery / Event Watch。
4. 請優先參考 market_radar 的即時資料：
   - 台指期盤後/近月
   - Nasdaq 期貨
   - S&P 期貨
   - VIX
   - 美元指數
   - 美債10Y
   若資料暫缺，不要猜測，不要用其他資料替代。
5. 若沒有 TrendForce / DRAMeXchange 即時價格資料，不要假裝有 DDR4 / DDR5 / NAND 報價；可以根據新聞與候選資料判斷「Memory Cycle」，但需標示為「新聞/市場訊號」而非即時報價。
6. 不要給絕對買賣建議，只給觀察重點與風險。

請只回傳 JSON，不要 markdown，不要解釋，不要 code block。

JSON 格式必須如下：

{{
  "market_view": {{
    "status": "Risk ON / Neutral / Risk OFF",
    "score": 0,
    "one_liner": "一句話描述今日盤前市場氣氛",
    "us_bias": "偏多 / 觀望 / 偏空",
    "tw_bias": "偏多 / 觀望 / 偏空",
    "key_drivers": ["市場驅動1", "市場驅動2", "市場驅動3"],
    "key_risks": ["風險1", "風險2", "風險3"]
  }},
  "ai_cycle_radar": {{
    "cycle_status": "升溫 / 高檔延續 / 分歧 / 降溫",
    "one_liner": "一句話描述 AI / 記憶體 / 半導體主循環",
    "memory_cycle": {{
      "status": "偏多 / 觀望 / 偏空 / 資料不足",
      "summary": "DDR4、DDR5、NAND、HBM 的新聞與供需訊號；若無即時報價需明說",
      "confidence": 0
    }},
    "theme_heat": [
      {{"theme": "HBM", "score": 0, "reason": "原因"}},
      {{"theme": "ASIC", "score": 0, "reason": "原因"}},
      {{"theme": "AI Server", "score": 0, "reason": "原因"}},
      {{"theme": "CoWoS", "score": 0, "reason": "原因"}},
      {{"theme": "Networking", "score": 0, "reason": "原因"}},
      {{"theme": "Cooling", "score": 0, "reason": "原因"}}
    ],
    "main_theme": "今日AI主線",
    "cycle_risk": "循環最大風險"
  }},
  "capital_flow": {{
    "one_liner": "一句話描述資金正在買什麼",
    "us_leaders": [
      {{"symbol": "標的", "theme": "題材", "reason": "原因"}},
      {{"symbol": "標的", "theme": "題材", "reason": "原因"}},
      {{"symbol": "標的", "theme": "題材", "reason": "原因"}}
    ],
    "tw_leaders": [
      {{"symbol": "代號或名稱", "theme": "題材", "reason": "原因"}},
      {{"symbol": "代號或名稱", "theme": "題材", "reason": "原因"}},
      {{"symbol": "代號或名稱", "theme": "題材", "reason": "原因"}}
    ],
    "weak_or_watchout": [
      "轉弱或需留意標的/族群1",
      "轉弱或需留意標的/族群2",
      "轉弱或需留意標的/族群3"
    ]
  }},
  "supply_chain": [
    {{"segment": "GPU", "status": "偏多 / 觀望 / 偏空", "summary": "一句重點", "leaders": "代表標的"}},
    {{"segment": "HBM", "status": "偏多 / 觀望 / 偏空", "summary": "一句重點", "leaders": "代表標的"}},
    {{"segment": "ASIC", "status": "偏多 / 觀望 / 偏空", "summary": "一句重點", "leaders": "代表標的"}},
    {{"segment": "Networking", "status": "偏多 / 觀望 / 偏空", "summary": "一句重點", "leaders": "代表標的"}},
    {{"segment": "CoWoS", "status": "偏多 / 觀望 / 偏空", "summary": "一句重點", "leaders": "代表標的"}},
    {{"segment": "AI Server", "status": "偏多 / 觀望 / 偏空", "summary": "一句重點", "leaders": "代表標的"}}
  ],
  "discovery_watchlist": {{
    "new_stocks": [
      {{"name": "新浮現標的", "theme": "題材", "reason": "原因"}},
      {{"name": "新浮現標的", "theme": "題材", "reason": "原因"}},
      {{"name": "新浮現標的", "theme": "題材", "reason": "原因"}}
    ],
    "new_themes": [
      {{"theme": "新浮現題材", "reason": "原因"}},
      {{"theme": "新浮現題材", "reason": "原因"}},
      {{"theme": "新浮現題材", "reason": "原因"}}
    ],
    "event_watch": [
      "重大事件1",
      "重大事件2",
      "重大事件3"
    ],
    "watch_next": [
      "接下來觀察1",
      "接下來觀察2",
      "接下來觀察3"
    ],
    "noise_or_signal": "判斷哪些是訊號，哪些可能只是雜訊"
  }},
  "final_view": "今日總結：偏多、偏空或觀望，並說明原因"
}}

限制：
- 所有欄位都要精簡，適合 LINE Flex Card 閱讀。
- theme_heat score 請用 0~100，不要用五把火。
- capital_flow 必須是「今天從資料裡挑出來的代表標的」，不是固定 watchlist。
- 若資料不足請寫「觀察中」或「資料不足」，不要硬湊。
- 請用繁體中文。

原始資料：
{json.dumps(data, ensure_ascii=False, indent=2)}
    """


def ensure_list(value):
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def ensure_dict(value):
    return value if isinstance(value, dict) else {}


def coerce_score(value, default=50):
    try:
        score = int(float(value))
    except Exception:
        score = default
    return max(0, min(100, score))


def validate_intel_payload(intel):
    if not isinstance(intel, dict):
        raise ValueError("Claude JSON root must be an object")

    market = ensure_dict(intel.get("market_view"))
    market["status"] = market.get("status") or "Neutral"
    market["score"] = coerce_score(market.get("score"), 50)
    market["one_liner"] = market.get("one_liner") or "資料不足，維持觀察。"
    market["us_bias"] = market.get("us_bias") or "觀望"
    market["tw_bias"] = market.get("tw_bias") or "觀望"
    market["key_drivers"] = ensure_list(market.get("key_drivers"))
    market["key_risks"] = ensure_list(market.get("key_risks"))
    intel["market_view"] = market

    cycle = ensure_dict(intel.get("ai_cycle_radar"))
    cycle["cycle_status"] = cycle.get("cycle_status") or "觀察中"
    cycle["one_liner"] = cycle.get("one_liner") or "資料不足，觀察中。"
    cycle["main_theme"] = cycle.get("main_theme") or "觀察中"
    cycle["cycle_risk"] = cycle.get("cycle_risk") or "資料不足"
    memory = ensure_dict(cycle.get("memory_cycle"))
    memory["status"] = memory.get("status") or "資料不足"
    memory["summary"] = memory.get("summary") or "資料不足"
    memory["confidence"] = coerce_score(memory.get("confidence"), 0)
    cycle["memory_cycle"] = memory
    cycle["theme_heat"] = [
        {
            "theme": ensure_dict(item).get("theme", "觀察中"),
            "score": coerce_score(ensure_dict(item).get("score"), 0),
            "reason": ensure_dict(item).get("reason", "資料不足"),
        }
        for item in ensure_list(cycle.get("theme_heat"))
        if isinstance(item, dict)
    ]
    intel["ai_cycle_radar"] = cycle

    flow = ensure_dict(intel.get("capital_flow"))
    flow["one_liner"] = flow.get("one_liner") or "資料不足，觀察中。"
    flow["us_leaders"] = [ensure_dict(item) for item in ensure_list(flow.get("us_leaders")) if isinstance(item, dict)]
    flow["tw_leaders"] = [ensure_dict(item) for item in ensure_list(flow.get("tw_leaders")) if isinstance(item, dict)]
    flow["weak_or_watchout"] = ensure_list(flow.get("weak_or_watchout"))
    intel["capital_flow"] = flow

    intel["supply_chain"] = [ensure_dict(item) for item in ensure_list(intel.get("supply_chain")) if isinstance(item, dict)]

    discovery = ensure_dict(intel.get("discovery_watchlist"))
    discovery["new_stocks"] = [ensure_dict(item) for item in ensure_list(discovery.get("new_stocks")) if isinstance(item, dict)]
    discovery["new_themes"] = [ensure_dict(item) for item in ensure_list(discovery.get("new_themes")) if isinstance(item, dict)]
    discovery["event_watch"] = ensure_list(discovery.get("event_watch"))
    discovery["watch_next"] = ensure_list(discovery.get("watch_next"))
    discovery["noise_or_signal"] = discovery.get("noise_or_signal") or "資料不足，觀察中。"
    intel["discovery_watchlist"] = discovery
    intel["final_view"] = intel.get("final_view") or "資料不足，維持觀察。"

    return intel


def ask_claude_json(prompt):
    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4200,
        messages=[{"role": "user", "content": prompt}],
    )

    text = message.content[0].text.strip()

    try:
        return validate_intel_payload(json.loads(text)), text
    except Exception:
        match = re.search(r"\{.*\}", text, re.S)
        if match:
            return validate_intel_payload(json.loads(match.group())), text
        raise ValueError("Claude 回傳不是有效 JSON")


def validate_line_message(message):
    if not isinstance(message, dict):
        raise ValueError("LINE message must be a dict")

    msg_type = message.get("type")
    if msg_type == "text":
        text = message.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("LINE text message requires non-empty text")
        if len(text) > 5000:
            raise ValueError("LINE text message exceeds 5000 characters")
        return message

    if msg_type != "flex":
        raise ValueError(f"Unsupported LINE message type: {msg_type}")

    alt_text = message.get("altText")
    if not isinstance(alt_text, str) or not alt_text.strip():
        raise ValueError("LINE flex message requires non-empty altText")

    contents = message.get("contents")
    if not isinstance(contents, dict):
        raise ValueError("LINE flex message requires contents object")

    if contents.get("type") == "carousel":
        bubbles = contents.get("contents")
        if not isinstance(bubbles, list) or not bubbles:
            raise ValueError("LINE carousel requires non-empty contents list")
        if len(bubbles) > 12:
            raise ValueError("LINE carousel supports at most 12 bubbles")
        for bubble in bubbles:
            if not isinstance(bubble, dict) or bubble.get("type") != "bubble":
                raise ValueError("LINE carousel contents must be bubble objects")
        return message

    if contents.get("type") == "bubble":
        return message

    raise ValueError("LINE flex contents must be a bubble or carousel")


# =====================
# LINE Flex UI helpers
# =====================

def status_color(status):
    if not status:
        return "#6B7280"
    if "偏多" in status or "Risk ON" in status or "升溫" in status or "延續" in status:
        return "#16A34A"
    if "偏空" in status or "Risk OFF" in status or "降溫" in status:
        return "#DC2626"
    return "#6B7280"


def score_color(score):
    try:
        score = int(score)
    except Exception:
        score = 50
    if score >= 75:
        return "#16A34A"
    if score <= 40:
        return "#DC2626"
    return "#B45309"


def make_text(text, size="sm", color="#111827", weight=None, wrap=True, margin=None):
    obj = {
        "type": "text",
        "text": str(text),
        "size": size,
        "color": color,
        "wrap": wrap,
    }
    if weight:
        obj["weight"] = weight
    if margin:
        obj["margin"] = margin
    return obj


def make_header(title, subtitle):
    return {
        "type": "box",
        "layout": "vertical",
        "backgroundColor": "#0B1220",
        "paddingAll": "18px",
        "contents": [
            make_text(title, size="xl", color="#FFFFFF", weight="bold"),
            make_text(subtitle, size="xs", color="#A7B4C8", margin="sm"),
        ],
    }


def make_bubble(title, subtitle, body_contents):
    return {
        "type": "bubble",
        "size": "giga",
        "header": make_header(title, subtitle),
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "paddingAll": "18px",
            "contents": body_contents,
        },
    }


def section_title(text):
    return make_text(text, size="md", color="#0F172A", weight="bold")


def add_separator(contents):
    contents.append({"type": "separator", "margin": "sm"})


def fmt_quote_num(v, digits=2):
    if v is None:
        return "N/A"
    try:
        return f"{float(v):,.{digits}f}"
    except Exception:
        return "N/A"


def fmt_quote_pct(v):
    if v is None:
        return "N/A"
    try:
        return f"{float(v):+.2f}%"
    except Exception:
        return "N/A"


def fmt_quote_change(v):
    if v is None:
        return "N/A"
    try:
        return f"{float(v):+.2f}"
    except Exception:
        return "N/A"


def build_market_radar_card(input_data, intel):
    radar = input_data.get("market_radar", {})
    quotes = radar.get("quotes", {})
    risk = radar.get("risk", {})

    market_view = intel.get("market_view", {})
    mood = market_view.get("status") or risk.get("mood", "Neutral")
    score = market_view.get("score") or risk.get("score", 50)
    emoji = risk.get("emoji", "🟡")

    def qline(key, label):
        q = quotes.get(key, {})
        if q.get("status") != "OK":
            return make_text(f"{label}：資料暫缺", size="sm", color="#64748B")
        return make_text(
            f"{label}：{fmt_quote_num(q.get('price'))}｜{fmt_quote_change(q.get('change'))}｜{fmt_quote_pct(q.get('change_pct'))}",
            size="sm",
            color="#334155",
        )

    contents = [
        make_text(f"{emoji} {mood}", size="xl", color=status_color(mood), weight="bold"),
        make_text(f"Risk Score：{score}/100", size="sm", color="#475569", weight="bold"),
        make_text(market_view.get("one_liner", ""), size="sm", color="#334155"),
        {"type": "separator", "margin": "md"},
        qline("txf", "台指期盤後/近月"),
        qline("nasdaq_fut", "Nasdaq期貨"),
        qline("sp500_fut", "S&P期貨"),
        qline("vix", "VIX"),
        qline("dxy", "美元指數"),
        qline("us10y", "美債10Y"),
    ]

    drivers = market_view.get("key_drivers", []) or risk.get("reasons", [])
    risks = market_view.get("key_risks", [])

    if drivers:
        contents.append({"type": "separator", "margin": "md"})
        contents.append(section_title("📌 盤勢驅動"))
        for d in drivers[:3]:
            contents.append(make_text(f"• {d}", size="sm", color="#111827"))

    if risks:
        contents.append(section_title("⚠️ 風險"))
        for r in risks[:2]:
            contents.append(make_text(f"• {r}", size="sm", color="#B45309"))

    contents.append(make_text("原則：TXF 抓不到或辨識不到就顯示資料暫缺，不以台股現貨指數替代。", size="xs", color="#64748B"))

    return make_bubble(
        "🌙 Market Radar",
        radar.get("generated_at", datetime.now().strftime("%Y-%m-%d %H:%M")),
        contents,
    )


def build_ai_cycle_card(intel):
    cycle = intel.get("ai_cycle_radar", {})
    memory = cycle.get("memory_cycle", {})
    heat = cycle.get("theme_heat", [])

    contents = [
        make_text(cycle.get("cycle_status", "觀察中"), size="xl", color=status_color(cycle.get("cycle_status", "")), weight="bold"),
        make_text(cycle.get("one_liner", ""), size="sm", color="#334155"),
        make_text(f"主線：{cycle.get('main_theme', '觀察中')}", size="sm", color="#2563EB", weight="bold"),
        make_text(f"循環風險：{cycle.get('cycle_risk', '觀察中')}", size="sm", color="#B45309"),
        {"type": "separator", "margin": "md"},
        section_title("💾 Memory Cycle"),
        make_text(f"{memory.get('status', '資料不足')}｜Confidence {memory.get('confidence', 0)}/100", size="sm", color=status_color(memory.get("status", "")), weight="bold"),
        make_text(memory.get("summary", "觀察中"), size="sm", color="#334155"),
        {"type": "separator", "margin": "md"},
        section_title("🔥 Theme Heat"),
    ]

    for item in heat[:6]:
        theme = item.get("theme", "-")
        score = item.get("score", 0)
        reason = item.get("reason", "")
        contents.append(make_text(f"{theme}｜{score}/100", size="sm", color=score_color(score), weight="bold"))
        contents.append(make_text(reason, size="xs", color="#64748B"))

    return make_bubble("🧠 AI Cycle Radar", "Memory・HBM・ASIC・CoWoS・AI主線", contents[:26])


def build_capital_flow_card(intel):
    flow = intel.get("capital_flow", {})
    us = flow.get("us_leaders", [])
    tw = flow.get("tw_leaders", [])
    weak = flow.get("weak_or_watchout", [])

    contents = [
        make_text(flow.get("one_liner", "觀察中"), size="sm", color="#334155", weight="bold"),
        {"type": "separator", "margin": "md"},
        section_title("🇺🇸 US Leaders"),
    ]

    for item in us[:4]:
        contents.append(make_text(f"{item.get('symbol', '-')}｜{item.get('theme', '-')}", size="sm", color="#2563EB", weight="bold"))
        contents.append(make_text(item.get("reason", ""), size="xs", color="#64748B"))

    contents.append(section_title("🇹🇼 Taiwan Leaders"))
    for item in tw[:4]:
        contents.append(make_text(f"{item.get('symbol', '-')}｜{item.get('theme', '-')}", size="sm", color="#16A34A", weight="bold"))
        contents.append(make_text(item.get("reason", ""), size="xs", color="#64748B"))

    if weak:
        contents.append(section_title("⚠️ Watchout"))
        for w in weak[:3]:
            contents.append(make_text(f"• {w}", size="sm", color="#B45309"))

    return make_bubble("🏆 AI Capital Flow", "美股・台股・資金流向", contents[:28])


def build_supply_chain_card(intel):
    chain = intel.get("supply_chain", [])
    contents = []

    for item in chain[:7]:
        status = item.get("status", "觀望")
        contents.append(make_text(f"{item.get('segment', '-')}｜{status}", size="md", color=status_color(status), weight="bold"))
        contents.append(make_text(item.get("summary", ""), size="sm", color="#334155"))
        contents.append(make_text(item.get("leaders", ""), size="xs", color="#64748B"))
        add_separator(contents)

    return make_bubble(
        "🔗 AI Supply Chain",
        "GPU・HBM・ASIC・Networking・CoWoS・AI Server",
        contents[:25],
    )


def build_discovery_card(intel):
    disc = intel.get("discovery_watchlist", {})
    stocks = disc.get("new_stocks", [])
    themes = disc.get("new_themes", [])
    events = disc.get("event_watch", [])
    watch_next = disc.get("watch_next", [])

    contents = [section_title("🛰 新浮現標的")]

    for item in stocks[:3]:
        contents.append(make_text(f"{item.get('name', '-')}｜{item.get('theme', '-')}", size="sm", color="#2563EB", weight="bold"))
        contents.append(make_text(item.get("reason", ""), size="xs", color="#64748B"))

    contents.append(section_title("🌊 新浮現題材"))
    for item in themes[:3]:
        contents.append(make_text(f"{item.get('theme', '-')}", size="sm", color="#16A34A", weight="bold"))
        contents.append(make_text(item.get("reason", ""), size="xs", color="#64748B"))

    contents.append(section_title("🚨 Event Watch"))
    for e in events[:3]:
        contents.append(make_text(f"• {e}", size="sm", color="#334155"))

    contents.append(section_title("✅ Next Watch"))
    for w in watch_next[:3]:
        contents.append(make_text(f"• {w}", size="sm", color="#111827"))

    contents.append({"type": "separator", "margin": "md"})
    contents.append(make_text(disc.get("noise_or_signal", "觀察中"), size="sm", color="#B45309", weight="bold"))
    contents.append(make_text(intel.get("final_view", ""), size="sm", color="#0F172A", weight="bold"))

    return make_bubble("🛰 Discovery & Watchlist", "新標的・新題材・事件・下一步", contents[:30])


def build_flex_carousel(intel, input_data):
    return {
        "type": "flex",
        "altText": "AI Intel Bot V6 今日市場情報",
        "contents": {
            "type": "carousel",
            "contents": [
                build_market_radar_card(input_data, intel),
                build_ai_cycle_card(intel),
                build_capital_flow_card(intel),
                build_supply_chain_card(intel),
                build_discovery_card(intel),
            ],
        },
    }


def build_plain_text(intel, input_data=None):
    lines = []

    if input_data and input_data.get("market_radar"):
        try:
            lines.append(format_market_radar_text(input_data["market_radar"]))
            lines.append("")
        except Exception as e:
            lines.append(f"🌙 Market Radar\n資料暫缺：{e}")
            lines.append("")

    market = intel.get("market_view", {})
    cycle = intel.get("ai_cycle_radar", {})
    flow = intel.get("capital_flow", {})
    disc = intel.get("discovery_watchlist", {})

    lines += [
        "🚀 AI Intel Bot V6",
        f"市場狀態：{market.get('status', 'Neutral')}｜{market.get('score', 50)}/100",
        market.get("one_liner", ""),
        "",
        "🧠 AI Cycle",
        f"{cycle.get('cycle_status', '觀察中')}｜{cycle.get('main_theme', '觀察中')}",
        cycle.get("one_liner", ""),
        "",
        "🏆 Capital Flow",
        flow.get("one_liner", "觀察中"),
        "",
        "🛰 Discovery",
    ]

    for s in disc.get("new_stocks", [])[:3]:
        if isinstance(s, dict):
            lines.append(f"• {s.get('name', '-')}｜{s.get('theme', '-')}: {s.get('reason', '')}")
        else:
            lines.append(f"• {s}")

    lines.append("")
    lines.append("📌 Final View")
    lines.append(intel.get("final_view", ""))

    return "\n".join(lines)


def send_line_message(message):
    if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_USER_ID:
        print("LINE 尚未設定，略過推播。")
        return None

    validate_line_message(message)

    url = "https://api.line.me/v2/bot/message/push"

    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    payload = {
        "to": LINE_USER_ID,
        "messages": [message],
    }

    r = requests.post(url, headers=headers, json=payload, timeout=20)
    print("LINE status:", r.status_code, r.text)
    logger.info("LINE status: %s %s", r.status_code, r.text)
    return r


def parse_args():
    parser = argparse.ArgumentParser(description="AI Intel Bot V6 report runner")
    parser.add_argument("--dry-run", action="store_true", help="只抓資料與產生 prompt，不呼叫 Claude，也不推播 LINE")
    parser.add_argument("--no-line", action="store_true", help="呼叫 Claude 並產出報告，但不推播 LINE")
    parser.add_argument("--collect-only", action="store_true", help="只抓資料並輸出 latest_input_compact.json，不產生 prompt / Claude / LINE")
    parser.add_argument("--use-cache", help="使用既有 input JSON，略過即時資料抓取")
    return parser.parse_args()


def main(args=None):
    args = args or parse_args()
    setup_logging()
    logger.info(
        "AI Intel Bot started dry_run=%s no_line=%s collect_only=%s use_cache=%s",
        args.dry_run,
        args.no_line,
        args.collect_only,
        args.use_cache,
    )

    if args.use_cache:
        if not os.path.exists(args.use_cache):
            raise FileNotFoundError(f"找不到快取資料檔案：{args.use_cache}")
        print(f"使用快取資料：{args.use_cache}")
        with open(args.use_cache, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        print("開始抓取資料...")
        data = build_input_data()

    with open("latest_input_compact.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    if args.collect_only:
        logger.info("Collect-only completed: latest_input_compact.json written")
        print("Collect-only 完成，已輸出 latest_input_compact.json，未產生 prompt / Claude / LINE。")
        return

    if args.dry_run:
        prompt = build_prompt(data)
        with open("latest_prompt.txt", "w", encoding="utf-8") as f:
            f.write(prompt)
        logger.info("Dry run completed: latest_input_compact.json and latest_prompt.txt written")
        print("Dry run 完成，已輸出 latest_input_compact.json 與 latest_prompt.txt，未呼叫 Claude / LINE。")
        return

    print("資料抓取完成，送 Claude 分析...")

    prompt = build_prompt(data)
    intel, raw_text = ask_claude_json(prompt)

    with open("latest_report.json", "w", encoding="utf-8") as f:
        json.dump(intel, f, ensure_ascii=False, indent=2)

    with open("latest_report_raw.txt", "w", encoding="utf-8") as f:
        f.write(raw_text)

    print(json.dumps(intel, ensure_ascii=False, indent=2))

    if args.no_line:
        logger.info("No-line mode completed: report files written without LINE push")
        print("No-line 模式：已產出報告，略過 LINE 推播。")
        return

    try:
        flex = validate_line_message(build_flex_carousel(intel, input_data=data))
        r = send_line_message(flex)
    except Exception as e:
        logger.exception("Flex payload validation/send failed: %s", e)
        r = None

    if not r or r.status_code != 200:
        print("Flex 失敗，改傳純文字")
        text_msg = {
            "type": "text",
            "text": build_plain_text(intel, input_data=data)[:4800],
        }
        send_line_message(validate_line_message(text_msg))


if __name__ == "__main__":
    main()
