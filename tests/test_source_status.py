import unittest

from ai_intel_report import build_source_status


class SourceStatusTest(unittest.TestCase):
    def test_summarizes_error_sources(self):
        status = build_source_status(
            {"error": "market failed"},
            {"status": {"AI產業消息": [{"status": "ERROR"}]}},
            {"MU": [{"title": "ok"}]},
            {"stocks": [{"title": "Reddit r/stocks 讀取失敗"}]},
            [{"error": "twse failed"}],
        )
        self.assertEqual(status["market_radar"], "ERROR")
        self.assertEqual(status["stock_news"]["MU"], "OK")
        self.assertEqual(status["reddit"]["stocks"], "ERROR")
        self.assertEqual(status["twse"], "ERROR")


if __name__ == "__main__":
    unittest.main()
