import unittest

import config


class ConfigImportsTest(unittest.TestCase):
    def test_required_config_names_exist(self):
        required = [
            "RSS_FEEDS",
            "STOCK_SYMBOLS",
            "REDDIT_SUBREDDITS",
            "KEYWORDS",
            "DISCOVERY_KEYWORDS",
            "AI_SUPPLY_CHAIN",
            "TAIWAN_THEMES",
            "TAIWAN_AI_KEYWORDS",
            "ELON_ECOSYSTEM",
            "DISCOVERY_LIMITS",
            "PROMPT_LIMITS",
        ]
        for name in required:
            with self.subTest(name=name):
                self.assertTrue(hasattr(config, name))

    def test_market_feeds_do_not_contain_malformed_twitter_symbol(self):
        market_feeds = config.RSS_FEEDS["總體市場"]
        self.assertFalse(any("Twitter=US" in url for url in market_feeds))
        self.assertTrue(any("s=QQQ" in url for url in market_feeds))
        self.assertTrue(any("s=SMH" in url for url in market_feeds))


if __name__ == "__main__":
    unittest.main()
