import unittest
from payload.spintax import SpintaxParser

class TestSpintaxParser(unittest.TestCase):
    def test_simple_spintax(self):
        raw = "{Hello|Hi|Hey} world!"
        spun = SpintaxParser.spin(raw, seed=42)
        self.assertIn(spun, ["Hello world!", "Hi world!", "Hey world!"])

    def test_nested_spintax(self):
        raw = "{Top {notch|tier}|Premium} {service|offering}!"
        for _ in range(20):
            spun = SpintaxParser.spin(raw)
            self.assertTrue(any(prefix in spun for prefix in ["Top notch", "Top tier", "Premium"]))
            self.assertTrue(any(suffix in spun for suffix in ["service!", "offering!"]))

    def test_generate_variations(self):
        raw = "{A|B} {1|2}"
        variants = SpintaxParser.generate_variations(raw, count=4)
        self.assertLessEqual(len(variants), 4)
        for v in variants:
            self.assertIn(v, ["A 1", "A 2", "B 1", "B 2"])

if __name__ == "__main__":
    unittest.main()
