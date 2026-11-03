# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt

import unittest
from unittest.mock import MagicMock, patch

from alaiy_os_connector_karmaglobal.karmaglobal import cost


def _page(rows, currency="INR"):
    return {
        "currency": currency,
        "items": [{"karma_sku": sku, "billing_price": price, "stock_qty": 1} for sku, price in rows],
    }


class TestCostLookup(unittest.TestCase):
    def _run(self, ids, pages=None, serves=True, page_size=None):
        client = MagicMock()
        if pages is not None:
            client.call.side_effect = pages
        patches = [
            patch.object(cost, "_serves", return_value=serves),
            patch.object(cost, "KarmaClient", return_value=client),
        ]
        if page_size:
            patches.append(patch.object(cost, "INVENTORY_PAGE", page_size))
        for p in patches:
            p.start()
        try:
            return cost.lookup("Karma Global", ids), client
        finally:
            for p in patches:
                p.stop()

    def test_another_supplier_gets_none_and_nothing_is_read(self):
        result, client = self._run(["KG-1"], serves=False)
        self.assertIsNone(result)
        client.call.assert_not_called()

    def test_returns_billing_price_and_currency_for_the_sizes_asked(self):
        result, _ = self._run(["KG-1", "KG-3"], pages=[_page([("KG-1", 100), ("KG-2", 50), ("KG-3", 75.5)], "EUR")])
        self.assertEqual(
            result,
            {"KG-1": {"cost": 100.0, "currency": "EUR"}, "KG-3": {"cost": 75.5, "currency": "EUR"}},
        )

    def test_a_size_billed_at_zero_or_not_listed_is_left_out(self):
        result, _ = self._run(["KG-1", "KG-2", "KG-9"], pages=[_page([("KG-1", 0), ("KG-2", 40)])])
        self.assertEqual(result, {"KG-2": {"cost": 40.0, "currency": "INR"}})

    def test_reads_further_pages_until_every_size_is_found(self):
        pages = [_page([("KG-1", 10), ("KG-2", 20)]), _page([("KG-3", 30)])]
        result, client = self._run(["KG-1", "KG-3"], pages=pages, page_size=2)
        self.assertEqual(set(result), {"KG-1", "KG-3"})
        self.assertEqual([c.args[1]["start"] for c in client.call.call_args_list], [0, 2])
        self.assertTrue(all(c.args[0] == "get_inventory" for c in client.call.call_args_list))

    def test_stops_as_soon_as_every_size_is_found(self):
        pages = [_page([("KG-1", 10), ("KG-2", 20)]), _page([("KG-3", 30)])]
        result, client = self._run(["KG-1"], pages=pages, page_size=2)
        self.assertEqual(result, {"KG-1": {"cost": 10.0, "currency": "INR"}})
        self.assertEqual(client.call.call_count, 1)

    def test_nothing_asked_reads_nothing(self):
        result, client = self._run([])
        self.assertEqual(result, {})
        client.call.assert_not_called()

    def test_a_karma_failure_is_raised(self):
        with self.assertRaises(RuntimeError):
            self._run(["KG-1"], pages=[RuntimeError("HTTP 500")])


if __name__ == "__main__":
    unittest.main()
