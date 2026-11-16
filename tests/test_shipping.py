import unittest
from src.services.shipping import estimate_shipping

class ShippingTests(unittest.TestCase):
    def test_paid_shipping_and_normalized_postcode(self):
        quote = estimate_shipping('01001000', 5890)
        self.assertEqual(quote.postal_code, '01001-000')
        self.assertEqual(quote.cost_cents, 1290)
        self.assertEqual((quote.minimum_days, quote.maximum_days), (3, 5))

    def test_free_shipping_recomputed_after_cart_changes(self):
        self.assertEqual(estimate_shipping('01001-000', 9900).cost_cents, 1290)
        self.assertEqual(estimate_shipping('01001-000', 9901).cost_cents, 0)
        self.assertEqual(estimate_shipping('01001-000', 5000).cost_cents, 1290)

    def test_invalid_postcodes(self):
        for value in ('', '123', '00000-000', 'abc01001000', '01001--000'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                estimate_shipping(value, 5890)

if __name__ == '__main__':
    unittest.main()
