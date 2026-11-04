# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt

import unittest

from alaiy_os_connector_karmaglobal.karmaglobal.sync import size_records


def _product(**extra):
    return {
        "karma_sku": "KG-P",
        "title": "Sneaker",
        "currency": "EUR",
        "attributes": [],
        "variants": [{"karma_sku": "KG-P-40", "size": "40", "stock_qty": 2, "billing_price": 100}],
        **extra,
    }


class TestSizeRecordsHsCode(unittest.TestCase):
    def test_hs_code_is_sent_as_digits_on_every_size(self):
        product = _product(hs_code="6404.11.00 00")
        product["variants"].append({"karma_sku": "KG-P-41", "size": "41", "stock_qty": 1, "billing_price": 100})
        records = size_records(product)
        self.assertEqual([r["hs_code"] for r in records], ["6404110000", "6404110000"])

    def test_missing_or_unusable_hs_code_is_not_sent(self):
        for value in (None, "", "64", "n/a"):
            with self.subTest(hs_code=value):
                self.assertNotIn("hs_code", size_records(_product(hs_code=value))[0])

    def test_hs_code_attribute_is_not_repeated_in_specs(self):
        product = _product(hs_code="6404110000", attributes=[{"label": "HS Code", "value": "6404110000"}])
        self.assertNotIn("HS Code", size_records(product)[0]["specs"])


if __name__ == "__main__":
    unittest.main()
