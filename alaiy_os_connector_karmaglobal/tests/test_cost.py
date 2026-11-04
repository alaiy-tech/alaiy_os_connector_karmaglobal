# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt

import json
import unittest
from unittest.mock import MagicMock, patch

from alaiy_os_connector_karmaglobal.karmaglobal import cost


def _page(rows, currency="INR"):
    return {
        "currency": currency,
        "items": [{"karma_sku": sku, "billing_price": price, "stock_qty": 1} for sku, price in rows],
    }


class TestCostLookup(unittest.TestCase):
    def _run(self, ids, pages=None, serves=True, batch_size=None):
        client = MagicMock()
        if pages is not None:
            client.call.side_effect = pages
        patches = [
            patch.object(cost, "_serves", return_value=serves),
            patch.object(cost, "KarmaClient", return_value=client),
        ]
        if batch_size:
            patches.append(patch.object(cost, "SKU_BATCH", batch_size))
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

    def test_asks_karma_only_for_the_sizes_wanted(self):
        _, client = self._run(["KG-3", "KG-1", "KG-1"], pages=[_page([("KG-1", 10), ("KG-3", 30)])])
        client.call.assert_called_once()
        method, params = client.call.call_args.args
        self.assertEqual(method, "get_inventory")
        self.assertEqual(json.loads(params["karma_skus"]), ["KG-1", "KG-3"])

    def test_splits_many_sizes_into_batches(self):
        pages = [_page([("KG-1", 10), ("KG-2", 20)]), _page([("KG-3", 30)])]
        result, client = self._run(["KG-1", "KG-2", "KG-3"], pages=pages, batch_size=2)
        self.assertEqual(set(result), {"KG-1", "KG-2", "KG-3"})
        self.assertEqual(
            [json.loads(c.args[1]["karma_skus"]) for c in client.call.call_args_list], [["KG-1", "KG-2"], ["KG-3"]]
        )

    def test_a_size_karma_returns_but_was_not_asked_for_is_left_out(self):
        result, _ = self._run(["KG-1"], pages=[_page([("KG-1", 10), ("KG-2", 20)])])
        self.assertEqual(result, {"KG-1": {"cost": 10.0, "currency": "INR"}})

    def test_nothing_asked_reads_nothing(self):
        result, client = self._run([])
        self.assertEqual(result, {})
        client.call.assert_not_called()

    def test_a_karma_failure_is_raised(self):
        with self.assertRaises(RuntimeError):
            self._run(["KG-1"], pages=[RuntimeError("HTTP 500")])


if __name__ == "__main__":
    unittest.main()
