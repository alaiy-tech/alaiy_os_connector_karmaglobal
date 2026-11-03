# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from alaiy_os_connector_karmaglobal.karmaglobal import catalogue

SERVES = SimpleNamespace(is_enabled=1, kg_supplier="Karma Global")


def _page(skus, total):
    return {"total": total, "products": [{"variants": [{"karma_sku": s}]} for s in skus]}


class TestCataloguePull(unittest.TestCase):
    def _run(self, supplier="Karma Global", dry_run=False, settings=SERVES, pages=None, client=None):
        client = client or MagicMock()
        if pages is not None:
            client.call.side_effect = pages
        with patch.object(catalogue.frappe, "get_cached_doc", return_value=settings), patch.object(
            catalogue, "KarmaClient", return_value=client
        ) as karma, patch.object(
            catalogue, "size_records", side_effect=lambda p: [{"supplier_product_id": v["karma_sku"]} for v in p["variants"]]
        ):
            return catalogue.pull(supplier, dry_run=dry_run), client, karma

    def test_other_supplier_gets_none(self):
        result, _, karma = self._run(supplier="Someone Else")
        self.assertIsNone(result)
        karma.assert_not_called()

    def test_switched_off_connector_gets_none(self):
        result, _, _ = self._run(settings=SimpleNamespace(is_enabled=0, kg_supplier="Karma Global"))
        self.assertIsNone(result)

    def test_dry_run_returns_empty_and_reads_nothing(self):
        result, client, karma = self._run(dry_run=True)
        self.assertEqual(result, [])
        karma.assert_not_called()
        client.call.assert_not_called()

    def test_reads_every_page_and_returns_one_record_per_size(self):
        pages = [_page(["KG-1", "KG-2"], 3), _page(["KG-3"], 3)]
        with patch.object(catalogue, "PULL_PAGE", 2):
            result, client, _ = self._run(pages=pages)
        self.assertEqual([r["supplier_product_id"] for r in result], ["KG-1", "KG-2", "KG-3"])
        self.assertEqual([c.args[1]["start"] for c in client.call.call_args_list], [0, 2])
        self.assertTrue(all(c.args[0] == "get_catalogue" for c in client.call.call_args_list))

    def test_an_empty_catalogue_is_an_empty_answer_not_none(self):
        result, _, _ = self._run(pages=[_page([], 0)])
        self.assertEqual(result, [])

    def test_a_karma_failure_is_raised_so_commerce_writes_nothing(self):
        with self.assertRaises(RuntimeError):
            self._run(pages=[RuntimeError("HTTP 500")])


if __name__ == "__main__":
    unittest.main()
