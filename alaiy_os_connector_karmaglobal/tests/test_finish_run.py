"""How a Karma sync run is closed. Runs without a bench."""

import importlib
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

MODULE = "alaiy_os_connector_karmaglobal.karmaglobal.sync"


def _core_run_status(processed, failed, skipped, error=None):
    if processed > 0 and failed >= processed:
        return "failed"
    if processed == 0 and (error or skipped > 0):
        return "failed"
    return "success"


def _load(core=True):
    frappe = types.ModuleType("frappe")
    frappe.db = MagicMock()
    frappe.db.exists.return_value = True
    frappe.db.get_value.return_value = None
    frappe.get_traceback = lambda: "traceback"
    frappe.log_error = MagicMock()
    utils = types.ModuleType("frappe.utils")
    utils.add_to_date = utils.now_datetime = lambda *a, **k: None
    utils.flt = float
    frappe.utils = utils
    stubs = {"frappe": frappe, "frappe.utils": utils}
    for name, attrs in {
        "alaiy_os_commerce": {},
        "alaiy_os_commerce.alaiy_os_commerce": {},
        "alaiy_os_commerce.alaiy_os_commerce.doctype": {},
        "alaiy_os_commerce.alaiy_os_commerce.doctype.supplier_product": {},
        "alaiy_os_commerce.alaiy_os_commerce.doctype.supplier_product.supplier_product": {"get_existing_names": None},
        "alaiy_os_commerce.api": {},
        "alaiy_os_commerce.api.supplier_products": {"MAX_BATCH": 100, "upsert_supplier_products": None},
        "alaiy_os_commerce.pricing_data": {"normalise_hs_code": None},
        "alaiy_os_connector_karmaglobal.karmaglobal.client": {"KarmaClient": MagicMock()},
    }.items():
        mod = types.ModuleType(name)
        mod.__dict__.update(attrs)
        stubs[name] = mod
    stubs["alaiy_os"] = types.ModuleType("alaiy_os")
    stubs["alaiy_os.health"] = types.ModuleType("alaiy_os.health")
    if core:
        runs = types.ModuleType("alaiy_os.health.runs")
        runs.run_status = _core_run_status
        stubs["alaiy_os.health.runs"] = runs
    else:
        stubs["alaiy_os.health.runs"] = None  # makes the import raise ImportError
    sys.modules.pop(MODULE, None)
    saved = {k: sys.modules.get(k) for k in stubs}
    sys.modules.update(stubs)
    try:
        return importlib.import_module(MODULE), saved
    finally:
        pass


def _restore(saved):
    for k, v in saved.items():
        if v is None:
            sys.modules.pop(k, None)
        else:
            sys.modules[k] = v
    sys.modules.pop(MODULE, None)


class TestFinishRun(unittest.TestCase):
    core = True

    def setUp(self):
        self.sync, saved = _load(self.core)
        self.addCleanup(_restore, saved)
        self.log = SimpleNamespace(status="", error_message=None, items_processed=0, items_failed=0)
        self.sync.get_or_create_log = lambda *a, **k: self.log
        self.sync._save = lambda log: None

    def run_with(self, processed, failed, raises=None):
        def worker(log, client, since):
            if raises:
                raise raises
            log.items_processed, log.items_failed = processed, failed

        try:
            self.sync._run("catalogue", "manual", None, worker)
        except Exception:
            pass
        return self.log


class TestWithCore(TestFinishRun):
    def test_every_item_failed(self):
        log = self.run_with(5, 5)
        self.assertEqual(log.status, "failed")
        self.assertEqual(log.error_message, "Every item failed (5); see the log.")

    def test_some_failed_is_success(self):
        log = self.run_with(5, 2)
        self.assertEqual(log.status, "success")
        self.assertFalse(log.error_message)

    def test_nothing_processed_is_success(self):
        self.assertEqual(self.run_with(0, 0).status, "success")

    def test_worker_raises(self):
        log = self.run_with(0, 0, raises=ValueError("boom"))
        self.assertEqual(log.status, "failed")
        self.assertEqual(log.error_message, "traceback")


class TestWithoutCore(TestFinishRun):
    core = False

    def test_fallback_keeps_old_behaviour(self):
        self.assertEqual(self.run_with(5, 5).status, "success")


if __name__ == "__main__":
    unittest.main()
