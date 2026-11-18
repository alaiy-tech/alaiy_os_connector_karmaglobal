# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from alaiy_os_connector_karmaglobal.karmaglobal import invoices


def _inv(name="ACC-SINV-1", total=656.88, owed=656.88, currency="EUR", status="Unpaid", posting_date="2026-11-18"):
    return {
        "invoice": name,
        "status": status,
        "grand_total": total,
        "outstanding_amount": owed,
        "currency": currency,
        "due_date": posting_date,
        "posting_date": posting_date,
    }


class TestMismatch(unittest.TestCase):
    def test_invoice_equal_to_the_karma_cost_matches(self):
        self.assertIsNone(invoices.mismatch([_inv(total=656.88)], (656.88, "EUR")))

    def test_two_invoices_adding_up_to_the_cost_match(self):
        self.assertIsNone(invoices.mismatch([_inv("A", 300), _inv("B", 356.88)], (656.88, "EUR")))

    def test_a_cent_of_rounding_is_allowed(self):
        self.assertIsNone(invoices.mismatch([_inv(total=656.89)], (656.88, "EUR")))

    def test_an_invoice_far_below_the_cost_is_flagged(self):
        # PUR-ORD-2026-00002: six lines costing €5,336.46, invoiced as €684.69.
        problem = invoices.mismatch([_inv("ACC-SINV-2026-00007", 684.69)], (5336.46, "EUR"))
        self.assertIn("ACC-SINV-2026-00007", problem)
        self.assertIn("684.69", problem)
        self.assertIn("5336.46", problem)

    def test_an_invoice_in_another_currency_is_flagged(self):
        self.assertIn("INR", invoices.mismatch([_inv(total=656.88, currency="INR")], (656.88, "EUR")))

    def test_an_order_with_no_karma_cost_is_flagged(self):
        self.assertIn("no Karma cost", invoices.mismatch([_inv()], None))


class TestPaidShare(unittest.TestCase):
    def test_unpaid_is_zero(self):
        self.assertEqual(invoices.paid_share([_inv(total=100, owed=100)]), 0.0)

    def test_paid_is_one(self):
        self.assertEqual(invoices.paid_share([_inv(total=100, owed=0, status="Paid")]), 1.0)

    def test_part_paid_across_invoices(self):
        self.assertAlmostEqual(invoices.paid_share([_inv("A", 100, 0), _inv("B", 300, 300)]), 0.25)

    def test_owed_more_than_billed_is_zero(self):
        self.assertEqual(invoices.paid_share([_inv(total=100, owed=120)]), 0.0)


class TestAmountToPay(unittest.TestCase):
    def test_fully_paid_pays_whatever_is_outstanding(self):
        self.assertEqual(invoices.amount_to_pay(67878.0, 67878.0, 1.0), 67878.0)

    def test_nothing_paid_pays_nothing(self):
        self.assertEqual(invoices.amount_to_pay(67878.0, 67878.0, 0.0), 0.0)

    def test_half_paid_pays_half(self):
        self.assertEqual(invoices.amount_to_pay(1000.0, 1000.0, 0.5), 500.0)

    def test_already_recorded_share_is_not_paid_twice(self):
        self.assertEqual(invoices.amount_to_pay(1000.0, 500.0, 0.5), 0.0)
        self.assertEqual(invoices.amount_to_pay(1000.0, 500.0, 0.75), 250.0)

    def test_more_recorded_than_karma_shows_pays_nothing(self):
        self.assertEqual(invoices.amount_to_pay(1000.0, 200.0, 0.5), 0.0)


class TestSyncOrder(unittest.TestCase):
    """One PO, with the database and ERPNext replaced."""

    def _run(self, invoice_rows, cost=(656.88, "EUR"), existing=(), paid=None):
        po = SimpleNamespace(name="PUR-ORD-2026-00003", supplier="Karma Global", items=[], add_comment=MagicMock())
        pi = SimpleNamespace(name="ACC-PINV-1", bill_no="ACC-SINV-2026-00008")
        frappe = MagicMock()
        frappe.get_doc.side_effect = lambda doctype, name: po if doctype == "Purchase Order" else pi
        frappe.get_all.return_value = [SimpleNamespace(**row) for row in existing]
        frappe.db.exists.return_value = False
        mocks = {
            "make_invoice": MagicMock(return_value=pi),
            "pay": MagicMock(return_value=paid),
            "karma_cost": MagicMock(return_value=cost),
        }
        with patch.object(invoices, "frappe", frappe), patch.multiple(invoices, **mocks):
            outcome = invoices.sync_order(po.name, invoice_rows)
        return outcome, mocks, frappe, po

    def test_not_invoiced_yet_does_nothing(self):
        outcome, mocks, frappe, _ = self._run([])
        self.assertEqual(outcome, ("waiting", None))
        frappe.get_doc.assert_not_called()
        mocks["make_invoice"].assert_not_called()

    def test_a_mismatched_invoice_is_flagged_and_nothing_is_recorded(self):
        outcome, mocks, _, po = self._run([_inv(total=684.69)], cost=(5336.46, "EUR"))
        self.assertEqual(outcome[0], "flagged")
        po.add_comment.assert_called_once_with("Comment", outcome[1])
        mocks["make_invoice"].assert_not_called()
        mocks["pay"].assert_not_called()

    def test_a_matching_invoice_makes_the_purchase_invoice(self):
        rows = [_inv()]
        outcome, mocks, _, po = self._run(rows)
        self.assertEqual(outcome[0], "created")
        mocks["make_invoice"].assert_called_once_with(po, rows)
        mocks["pay"].assert_called_once()
        self.assertEqual(mocks["pay"].call_args.args[1], 0.0)

    def test_an_existing_purchase_invoice_is_paid_when_karma_shows_paid(self):
        rows = [_inv(owed=0, status="Paid")]
        entry = SimpleNamespace(paid_amount=67878.0, paid_from_account_currency="INR")
        outcome, mocks, _, _ = self._run(rows, existing=[{"parent": "ACC-PINV-1", "docstatus": 1}], paid=entry)
        self.assertEqual(outcome[0], "updated")
        mocks["make_invoice"].assert_not_called()
        self.assertEqual(mocks["pay"].call_args.args[1], 1.0)

    def test_nothing_new_on_karma_changes_nothing(self):
        outcome, _, _, _ = self._run([_inv()], existing=[{"parent": "ACC-PINV-1", "docstatus": 1}])
        self.assertEqual(outcome, ("unchanged", None))

    def test_a_draft_purchase_invoice_is_left_for_a_person(self):
        outcome, mocks, _, _ = self._run([_inv()], existing=[{"parent": "ACC-PINV-1", "docstatus": 0}])
        self.assertEqual(outcome[0], "skipped")
        mocks["make_invoice"].assert_not_called()
        mocks["pay"].assert_not_called()


class TestSync(unittest.TestCase):
    def test_asks_karma_in_batches_and_counts_each_outcome(self):
        log = SimpleNamespace(items_processed=0, items_created=0, items_updated=0, items_failed=0, log_messages="")
        client = MagicMock()
        client.call.side_effect = [
            {"orders": [{"order_id": "PO-1", "invoices": [_inv()]}, {"order_id": "PO-2", "invoices": [_inv()]}]},
            {"orders": [{"order_id": "PO-3", "invoices": []}, {"order_id": "PO-X", "invoices": [_inv()]}]},
        ]
        outcomes = {"PO-1": ("created", "made"), "PO-2": ("flagged", "too low"), "PO-3": ("waiting", None)}
        frappe = MagicMock()
        frappe.get_single.return_value = SimpleNamespace(kg_supplier="Karma Global", kg_payment_account=None)
        with (
            patch.object(invoices, "frappe", frappe),
            patch.object(invoices, "STATUS_BATCH", 2),
            patch.object(invoices, "open_orders", return_value=["PO-1", "PO-2", "PO-3"]),
            patch.object(invoices, "sync_order", side_effect=lambda name, rows, account: outcomes[name]),
        ):
            invoices.sync(log, client)

        self.assertEqual([c.kwargs["body"]["order_ids"] for c in client.call.call_args_list], [["PO-1", "PO-2"], ["PO-3"]])
        self.assertEqual((log.items_processed, log.items_created, log.items_failed), (3, 1, 1))
        self.assertEqual(log.log_messages, "PO-1: made\nPO-2: too low\n")

    def test_one_order_failing_does_not_stop_the_others(self):
        log = SimpleNamespace(items_processed=0, items_created=0, items_updated=0, items_failed=0, log_messages="")
        client = MagicMock()
        client.call.return_value = {"orders": [{"order_id": "PO-1", "invoices": [_inv()]}, {"order_id": "PO-2", "invoices": [_inv()]}]}
        frappe = MagicMock()
        frappe.get_single.return_value = SimpleNamespace(kg_supplier="Karma Global", kg_payment_account=None)
        frappe.get_traceback.return_value = "Traceback...\nValidationError: Bill date is wrong"

        def order(name, rows, account):
            if name == "PO-1":
                raise RuntimeError("boom")
            return ("created", "made")

        with (
            patch.object(invoices, "frappe", frappe),
            patch.object(invoices, "open_orders", return_value=["PO-1", "PO-2"]),
            patch.object(invoices, "sync_order", side_effect=order),
        ):
            invoices.sync(log, client)

        frappe.db.rollback.assert_called_once()
        self.assertEqual((log.items_processed, log.items_created, log.items_failed), (2, 1, 1))
        self.assertIn("PO-1: ValidationError: Bill date is wrong", log.log_messages)
