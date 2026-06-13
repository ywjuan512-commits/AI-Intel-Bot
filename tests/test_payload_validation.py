import unittest

from ai_intel_report import validate_intel_payload


class PayloadValidationTest(unittest.TestCase):
    def test_fills_required_sections_and_clamps_scores(self):
        payload = validate_intel_payload({"market_view": {"score": "120"}})
        self.assertEqual(payload["market_view"]["score"], 100)
        self.assertEqual(payload["market_view"]["status"], "Neutral")
        self.assertIn("ai_cycle_radar", payload)
        self.assertIn("capital_flow", payload)
        self.assertIn("discovery_watchlist", payload)

    def test_converts_scalar_watchout_to_list(self):
        payload = validate_intel_payload({"capital_flow": {"weak_or_watchout": "risk"}})
        self.assertEqual(payload["capital_flow"]["weak_or_watchout"], ["risk"])

    def test_rejects_non_object_root(self):
        with self.assertRaises(ValueError):
            validate_intel_payload([])


if __name__ == "__main__":
    unittest.main()
