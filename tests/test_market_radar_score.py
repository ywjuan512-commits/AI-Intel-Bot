import unittest

from modules.market_radar import Quote, calculate_risk_score


class MarketRadarScoreTest(unittest.TestCase):
    def test_risk_on_when_growth_assets_strong_and_vix_down(self):
        quotes = {
            "txf": Quote("TXF", "台指期", "test", "OK", change_pct=1.0),
            "nasdaq_fut": Quote("NQ=F", "Nasdaq", "test", "OK", change_pct=1.0),
            "sp500_fut": Quote("ES=F", "S&P", "test", "OK", change_pct=1.0),
            "vix": Quote("^VIX", "VIX", "test", "OK", change_pct=-2.0),
        }
        result = calculate_risk_score(quotes)
        self.assertEqual(result["mood"], "Risk ON")
        self.assertGreaterEqual(result["score"], 70)

    def test_risk_off_when_growth_assets_weak_and_vix_up(self):
        quotes = {
            "txf": Quote("TXF", "台指期", "test", "OK", change_pct=-1.0),
            "nasdaq_fut": Quote("NQ=F", "Nasdaq", "test", "OK", change_pct=-1.0),
            "sp500_fut": Quote("ES=F", "S&P", "test", "OK", change_pct=-1.0),
            "vix": Quote("^VIX", "VIX", "test", "OK", change_pct=2.0),
        }
        result = calculate_risk_score(quotes)
        self.assertEqual(result["mood"], "Risk OFF")
        self.assertLessEqual(result["score"], 35)


if __name__ == "__main__":
    unittest.main()
