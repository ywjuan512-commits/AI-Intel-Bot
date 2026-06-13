import unittest

from ai_intel_report import build_flex_carousel, validate_intel_payload, validate_line_message


class LinePayloadShapeTest(unittest.TestCase):
    def test_validates_flex_carousel_shape(self):
        intel = validate_intel_payload({})
        message = build_flex_carousel(intel, {"market_radar": {"quotes": {}, "risk": {}}})
        self.assertIs(validate_line_message(message), message)

    def test_rejects_empty_text_message(self):
        with self.assertRaises(ValueError):
            validate_line_message({"type": "text", "text": ""})

    def test_rejects_carousel_without_bubbles(self):
        with self.assertRaises(ValueError):
            validate_line_message({"type": "flex", "altText": "x", "contents": {"type": "carousel", "contents": []}})


if __name__ == "__main__":
    unittest.main()
