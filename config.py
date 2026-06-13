# =========================
# RSS FEEDS
# =========================

RSS_FEEDS = {
    "AI產業消息": [
        "https://venturebeat.com/category/ai/feed/",
        "https://techcrunch.com/category/artificial-intelligence/feed/",
        "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml",
    ],

    "半導體新聞": [
        "https://www.anandtech.com/rss/",
        "https://www.techpowerup.com/rss/news",
        "https://www.tomshardware.com/feeds/all",
    ],

    "HBM消息": [
        "https://www.anandtech.com/rss/",
        "https://www.techpowerup.com/rss/news",
    ],

    "Tesla_SpaceX_Elon": [
        "https://electrek.co/feed/",
        "https://www.teslarati.com/feed/",
        "https://spaceflightnow.com/feed/",
    ],

    "總體市場": [
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=%5EGSPC&region=US&lang=en-US",
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=%5ETwitter=US&lang=en-US",
    ],
}


# =========================
# 固定觀察美股
# =========================

STOCK_SYMBOLS = [
    "MU",
    "NVDA",
    "TSM",
    "AMD",
    "ARM",
    "MRVL",
    "AVGO",
    "SMCI",
    "DELL",
    "VRT",
    "ANET",
    "TSLA",
]


# =========================
# Reddit Subreddits
# =========================

REDDIT_SUBREDDITS = [
    "stocks",
    "wallstreetbets",
    "hardware",
    "singularity",
    "LocalLLaMA",
    "teslamotors",
    "spacex",
    "investing",
]


# =========================
# 關鍵字（主要）
# =========================

KEYWORDS = [
    # AI / 半導體
    "AI",
    "artificial intelligence",
    "semiconductor",
    "HBM",
    "HBM3E",
    "HBM4",
    "DRAM",
    "DDR5",
    "CoWoS",
    "ASIC",
    "GPU",
    "Blackwell",
    "data center",
    "AI server",
    "networking",
    "cooling",
    "power",

    # 美股科技
    "Micron",
    "MU",
    "NVIDIA",
    "NVDA",
    "Broadcom",
    "AVGO",
    "Marvell",
    "MRVL",
    "TSMC",
    "TSM",
    "AMD",
    "ARM",

    # Elon ecosystem
    "Tesla",
    "TSLA",
    "Robotaxi",
    "FSD",
    "Optimus",
    "xAI",
    "Grok",
    "SpaceX",
    "Starlink",
    "Starship",
]


# =========================
# 動態探索關鍵字
# =========================

DISCOVERY_KEYWORDS = [
    "AI",
    "HBM",
    "HBM4",
    "CoWoS",
    "ASIC",
    "Robotaxi",
    "FSD",
    "Blackwell",
    "data center",
    "AI infrastructure",
    "AI server",
    "silicon photonics",
    "CPO",
    "DDR5",
    "LPDDR",
    "power",
    "cooling",
    "PCB",
    "CCL",
    "glass substrate",
]


# =========================
# AI Supply Chain
# =========================

AI_SUPPLY_CHAIN = {
    "AI晶片/GPU": [
        "NVDA",
        "AMD",
        "ARM",
    ],

    "ASIC/客製化晶片": [
        "AVGO",
        "MRVL",
        "TSM",
    ],

    "記憶體/HBM": [
        "MU",
        "Samsung",
        "SK hynix",
    ],

    "晶圓代工": [
        "TSM",
    ],

    "先進封裝/CoWoS": [
        "TSM",
        "ASE",
        "AMKR",
    ],

    "AI伺服器": [
        "SMCI",
        "DELL",
        "HPE",
    ],

    "網通/交換器": [
        "ANET",
        "MRVL",
        "CSCO",
    ],

    "電源/散熱/資料中心基建": [
        "VRT",
        "ETN",
        "PWR",
    ],
}


# =========================
# 台股題材觀察
# =========================

TAIWAN_THEMES = {
    "記憶體": [
        "南亞科",
        "華邦電",
        "威剛",
        "群聯",
        "十銓",
    ],

    "PCB/CCL": [
        "金居",
        "台光電",
        "聯茂",
        "尖點",
        "臻鼎-KY",
    ],

    "AI伺服器": [
        "廣達",
        "緯創",
        "緯穎",
        "技嘉",
        "英業達",
    ],

    "散熱": [
        "奇鋐",
        "雙鴻",
        "建準",
        "健策",
    ],

    "電源": [
        "台達電",
        "光寶科",
        "群電",
    ],

    "先進封裝/測試": [
        "日月光投控",
        "京元電",
        "辛耘",
        "弘塑",
    ],

    "玻纖/材料": [
        "台玻",
        "富喬",
        "南亞",
    ],

    "矽光子/CPO": [
        "聯亞",
        "波若威",
        "華星光",
        "上詮",
    ],
}


# =========================
# 台股 AI 關聯字
# Dynamic Discovery 會用
# =========================

TAIWAN_AI_KEYWORDS = [
    "AI",
    "半導體",
    "記憶體",
    "HBM",
    "伺服器",
    "散熱",
    "PCB",
    "CCL",
    "光通訊",
    "矽光子",
    "CoWoS",
    "封裝",
    "測試",
    "資料中心",
]


# =========================
# Elon ecosystem
# =========================

ELON_ECOSYSTEM = {
    "Tesla/Robotaxi/FSD": [
        "Tesla",
        "TSLA",
        "Robotaxi",
        "FSD",
        "Optimus",
    ],

    "SpaceX/Starlink": [
        "SpaceX",
        "Starlink",
        "Falcon",
        "Starship",
    ],

    "xAI/Grok": [
        "xAI",
        "Grok",
    ],

    "能源/儲能": [
        "Megapack",
        "Powerwall",
        "energy storage",
    ],
}


# =========================
# 動態探索限制
# 省 token 成本用
# =========================

DISCOVERY_LIMITS = {
    "rss_per_feed": 3,
    "reddit_posts": 6,
    "twse_top_stocks": 25,
    "dynamic_candidates": 10,
}


# =========================
# Claude Prompt 限制
# 省 token
# =========================

PROMPT_LIMITS = {
    "max_rss_items": 20,
    "max_reddit_items": 15,
    "max_dynamic_items": 10,
}