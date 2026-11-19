"""The inventory sync writes one record per size, even when get_inventory lists a size twice. Runs without a bench."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from alaiy_os_connector_karmaglobal.tests.test_finish_run import _load, _restore


def _page(items, currency="EUR"):
    return {"currency": currency, "items": [{"karma_sku": s, "stock_qty": q, "billing_price": p} for s, q, p in items]}


class TestInventorySync(unittest.TestCase):
    def setUp(self):
        self.sync, saved = _load()
        self.addCleanup(_restore, saved)
        self.log = SimpleNamespace(
            status="", error_message=None, items_processed=0, items_created=0, items_updated=0, items_failed=0,
            pages_done=0, log_messages=None,
        )
        self.sync.get_or_create_log = lambda *a, **k: self.log
        self.sync._save = lambda log: None
        self.sync.MAX_BATCH = 100
        self.written = []

        def upsert(supplier, batch):
            self.written.extend(batch)
            ids = [r["supplier_product_id"] for r in batch]
            repeats = {i for i in ids if ids.count(i) > 1}
            return {"added": [], "updated": ids, "errors": [{"supplier_product_id": i, "error": "repeats"} for i in repeats]}

        self.sync.upsert_supplier_products = upsert

    def run_sync(self, pages, known):
        client = MagicMock(supplier="Supplier")
        client.call.side_effect = pages
        self.sync.KarmaClient = lambda: client
        self.sync.get_existing_names = lambda supplier: set(known)
        self.sync.run_inventory_sync("manual")
        return {r["supplier_product_id"]: r for r in self.written}

    def test_a_size_listed_twice_is_one_record_with_the_stock_added_up(self):
        written = self.run_sync([_page([("KG-1", 1, 621.0), ("KG-1", 0, 621.0), ("KG-2", 3, 10.0)])], ["KG-1", "KG-2"])
        self.assertEqual(len(self.written), 2)
        self.assertEqual(written["KG-1"]["supplier_stock"], 1)
        self.assertEqual(written["KG-1"]["cost_price"], 621.0)
        self.assertEqual(written["KG-2"]["supplier_stock"], 3)
        self.assertEqual((self.log.items_failed, self.log.items_processed, self.log.status), (0, 2, "success"))

    def test_the_order_of_the_rows_does_not_change_the_stock(self):
        written = self.run_sync([_page([("KG-1", 0, 621.0), ("KG-1", 1, 621.0)])], ["KG-1"])
        self.assertEqual(len(self.written), 1)
        self.assertEqual(written["KG-1"]["supplier_stock"], 1)

    def test_a_size_repeated_on_the_next_page_is_still_one_record(self):
        self.sync.INVENTORY_PAGE = 2
        pages = [_page([("KG-1", 1, 5.0), ("KG-2", 2, 6.0)]), _page([("KG-1", 0, 5.0)])]
        written = self.run_sync(pages, ["KG-1", "KG-2"])
        self.assertEqual(len(self.written), 2)
        self.assertEqual(written["KG-1"]["supplier_stock"], 1)
        self.assertEqual(self.log.pages_done, 2)

    def test_a_price_of_0_in_one_row_does_not_hide_the_other_rows_price(self):
        written = self.run_sync([_page([("KG-1", 0, 0), ("KG-1", 1, 40.0)])], ["KG-1"])
        self.assertEqual(written["KG-1"]["cost_price"], 40.0)

    def test_a_size_with_no_price_in_any_row_keeps_its_stored_price(self):
        written = self.run_sync([_page([("KG-1", 2, 0)])], ["KG-1"])
        self.assertNotIn("cost_price", written["KG-1"])

    def test_sizes_not_pulled_yet_are_left_out(self):
        written = self.run_sync([_page([("KG-1", 1, 5.0), ("KG-9", 4, 5.0)])], ["KG-1"])
        self.assertEqual(list(written), ["KG-1"])


if __name__ == "__main__":
    unittest.main()
