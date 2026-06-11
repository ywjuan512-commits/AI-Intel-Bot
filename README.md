AI Intel Bot

Personal Bloomberg Terminal for AI Infrastructure Investing

⸻

Overview

AI Intel Bot 是一套部署於 Synology NAS 的個人 AI 情報終端系統。

目標不是新聞摘要，而是透過自動化資料收集、AI 分析與 LINE 推播，提供每日可執行的市場情報。

核心關注領域：

* AI Infrastructure
* Memory Cycle
* Capital Flow
* Supply Chain Rotation
* Taiwan AI Ecosystem
* Global AI Market

⸻

Current Version

Version: V6

Status: Production Testing

⸻

Architecture

Page 1 - Market Radar

盤前市場風險監控

Coverage:

* TXF Night Session
* Nasdaq Futures
* S&P Futures
* VIX
* DXY
* US10Y

Output:

* Risk Score
* Risk ON / Neutral / Risk OFF
* Key Drivers
* Key Risks

⸻

Page 2 - AI Cycle Radar

AI 產業循環監控

Coverage:

* HBM
* ASIC
* AI Server
* Networking
* CoWoS
* Cooling

Output:

* Theme Heat Ranking
* Memory Cycle
* Main Theme
* Cycle Risk

⸻

Page 3 - AI Capital Flow

資金流向分析

Principle:

Industry → Capital Flow → Company

Output:

* US Leaders
* Taiwan Leaders
* Weak / Watchout

⸻

Page 4 - AI Supply Chain

Coverage:

* GPU
* HBM
* ASIC
* Networking
* CoWoS
* AI Server

Output:

* Status
* Summary
* Leaders

⸻

Page 5 - Discovery & Watchlist

Coverage:

* New Stocks
* New Themes
* Event Watch
* Watch Next

Output:

* Signal vs Noise
* Emerging Opportunities

⸻

Technology Stack

Infrastructure

* Synology DS220+
* Container Manager
* code-server

AI

* Claude API
* Anthropic Haiku

Notification

* LINE Messaging API

Data Sources

* RSS
* Reddit
* TWSE
* Yahoo Finance
* Market Radar Module

⸻

Design Principles

Industry First

Analysis Flow

Industry
→ Supply Chain
→ Company

No Permanent Heroes

不固定分析：

* MU
* NVDA
* TSM
* AVGO
* MRVL
* TSLA

優先找出：

* 最強產業
* 最強資金流
* 最強供應鏈

No Fake Data

若資料不存在：

Data Unavailable

禁止：

* 猜測
* 補值
* 使用替代資料

例如：

若 TXF Night Session 抓取失敗，不得使用台股加權指數代替。

⸻

Current Modules

market_radar.py

Coverage

* TXF Night Session
* Nasdaq Futures
* S&P Futures
* VIX
* DXY
* US10Y

Output

* Risk Score
* Market Mood

⸻

Roadmap

V6.1

TrendForce Memory Radar

* DDR4 Spot
* DDR5 Spot
* NAND
* HBM

Priority: ★★★★★

V6.5

AI Capital Flow Ranking

* Strongest Stocks
* Strongest Themes
* Capital Rotation

Priority: ★★★★★

V7

Historical Database

daily_reports/YYYY-MM-DD.json

Capabilities:

* 7 Day Trend
* 30 Day Trend
* Theme Momentum
* Heat Map Trend

Priority: ★★★★☆

⸻

Workflow

Scheduler
↓
Collect Data
↓
Claude Analysis
↓
Generate Intelligence
↓
LINE Push Notification

⸻

Long-Term Vision

Market
↓
Cycle
↓
Capital
↓
Supply Chain
↓
Opportunity
↓
Risk

將資訊轉換為決策情報，而非新聞摘要。
