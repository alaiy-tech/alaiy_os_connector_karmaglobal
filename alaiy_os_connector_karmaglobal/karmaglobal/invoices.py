# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt

"""
Karma Global's invoices and payments, carried onto Alaiy Commerce's Purchase Orders.

Karma bills each order the connector placed with `receive_order`. Karma's `get_order_status` says, per PO
name, which invoices Karma raised and how much of each is still owed. For each open Karma PO the
invoice sync:

1. Checks that Karma's invoices add up to the order's Karma cost: each line's Supplier Product
   `cost_price` (Karma's `billing_price`, in Karma's currency) x qty. When they don't, the PO is flagged
   with a comment and nothing is recorded, so a wrong invoice never marks an order paid.
2. Makes the PO's Purchase Invoice once Karma has invoiced it, with Karma's invoice numbers as the
   Supplier Invoice No. The portal reads it as the supplier's invoice and what Alaiy owes.
3. Records a Payment Entry when Karma records a payment, for the same share of our invoice that Karma
   shows as paid.

Our Purchase Invoice is in the PO's currency at the PO's rates, the cost Alaiy recorded. Karma bills in
its own currency (EUR), so only the paid share is carried across, never an amount.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

from alaiy_os_connector_karmaglobal.karmaglobal.client import SETTINGS

# Karma answers at most this many PO names per get_order_status call.
STATUS_BATCH = 200
# How far Karma's invoice total may be from the order's Karma cost (rounding, a small price change).
TOLERANCE = 0.01


def sync(log, client):
    """Invoice sync worker: read Karma's status of every open Karma PO and carry it across."""
    settings = frappe.get_single(SETTINGS)
    names = open_orders(settings.kg_supplier)
    for i in range(0, len(names), STATUS_BATCH):
        batch = names[i : i + STATUS_BATCH]
        answer = client.call("get_order_status", body={"order_ids": batch})
        for status in answer["orders"]:
            if status["order_id"] not in batch:
                continue
            log.items_processed += 1
            try:
                outcome = sync_order(status["order_id"], status["invoices"] or [], settings.kg_payment_account)
                frappe.db.commit()
            except Exception:
                frappe.db.rollback()
                outcome = ("failed", frappe.get_traceback().strip().splitlines()[-1])
            _count(log, status["order_id"], *outcome)


def open_orders(supplier):
    """Submitted Karma POs that Karma accepted and that are not yet fully paid on our side."""
    names = frappe.get_all(
        "Purchase Order",
        filters={"supplier": supplier, "docstatus": 1, "status": ("!=", "Closed"), "order_confirmation_no": ("is", "set")},
        pluck="name",
        order_by="creation asc",
    )
    if not names:
        return []
    owed = {}
    for po, _pi, outstanding in frappe.db.sql(
        """select distinct pii.purchase_order, pi.name, pi.outstanding_amount
        from `tabPurchase Invoice Item` pii join `tabPurchase Invoice` pi on pi.name = pii.parent
        where pi.docstatus = 1 and pii.purchase_order in %s""",
        [names],
    ):
        owed[po] = owed.get(po, 0) + flt(outstanding)
    return [name for name in names if name not in owed or owed[name] > 0]


def sync_order(po_name, invoices, payment_account=None):
    """Carry Karma's invoices of one PO across. Returns (outcome, message) for the sync log."""
    if not invoices:
        return ("waiting", None)

    po = frappe.get_doc("Purchase Order", po_name)
    problem = mismatch(invoices, karma_cost(po))
    if problem:
        _flag(po, problem)
        return ("flagged", problem)

    existing = frappe.get_all(
        "Purchase Invoice Item",
        filters={"purchase_order": po.name, "docstatus": ("<", 2)},
        fields=["parent", "docstatus"],
        distinct=True,
    )
    if any(row.docstatus == 0 for row in existing) or len(existing) > 1:
        return ("skipped", _("Has a draft or several Purchase Invoices; left for a person to finish."))

    created = not existing
    pi = make_invoice(po, invoices) if created else frappe.get_doc("Purchase Invoice", existing[0].parent)
    paid = pay(pi, paid_share(invoices), invoices, payment_account)
    if created:
        return ("created", _("Purchase Invoice {0} made from Karma's {1}").format(pi.name, pi.bill_no))
    if paid:
        return ("updated", _("Paid {0} {1} on {2}").format(paid.paid_amount, paid.paid_from_account_currency, pi.name))
    return ("unchanged", None)


def karma_cost(po):
    """What Karma should bill for the PO: (total, currency) from the Supplier Products, or None."""
    costs = {
        row.item: row
        for row in frappe.get_all(
            "Supplier Product",
            filters={"supplier": po.supplier, "item": ("in", [d.item_code for d in po.items] or [""])},
            fields=["item", "cost_price", "currency"],
        )
    }
    total, currencies = 0.0, set()
    for d in po.items:
        row = costs.get(d.item_code)
        if not row or not flt(row.cost_price):
            return None
        total += flt(row.cost_price) * flt(d.stock_qty)
        currencies.add(row.currency)
    if len(currencies) != 1:
        return None
    return round(total, 2), currencies.pop()


def mismatch(invoices, expected):
    """Why Karma's invoices can't be taken as this order's bill, or None when they add up."""
    currencies = {inv["currency"] for inv in invoices}
    billed = round(sum(flt(inv["grand_total"]) for inv in invoices), 2)
    names = ", ".join(inv["invoice"] for inv in invoices)
    if not expected:
        return _("Karma invoiced {0} for {1} {2}, but this order has no Karma cost to check it against.").format(
            names, billed, "/".join(sorted(currencies))
        )
    cost, currency = expected
    if currencies != {currency}:
        return _("Karma invoiced {0} in {1}, but this order's Karma cost is in {2}.").format(
            names, "/".join(sorted(currencies)), currency
        )
    if abs(billed - cost) > TOLERANCE * cost:
        return _("Karma invoiced {0} for {1} {2}, but this order's Karma cost is {3} {2}.").format(
            names, billed, currency, cost
        )
    return None


def paid_share(invoices):
    """How much of Karma's bill Karma shows as paid, from 0 to 1."""
    billed = sum(flt(inv["grand_total"]) for inv in invoices)
    owed = sum(flt(inv["outstanding_amount"]) for inv in invoices)
    if billed <= 0:
        return 0.0
    return min(max(1 - owed / billed, 0.0), 1.0)


def amount_to_pay(total, outstanding, share):
    """What to pay now so our invoice is paid in the same share as Karma's. 0 when nothing is due."""
    outstanding = round(flt(outstanding), 2)
    if share >= 1:
        return outstanding
    due = round(flt(total) * share - (flt(total) - outstanding), 2)
    return max(min(due, outstanding), 0.0)


def make_invoice(po, invoices):
    from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_invoice

    pi = make_purchase_invoice(po.name)
    pi.bill_no = ", ".join(inv["invoice"] for inv in invoices)[:140]
    dates = [getdate(inv["posting_date"]) for inv in invoices if inv.get("posting_date")]
    pi.bill_date = min(dates) if dates else nowdate()
    pi.remarks = _("Karma Global invoice {0}: {1} {2}.").format(
        pi.bill_no, round(sum(flt(inv["grand_total"]) for inv in invoices), 2), invoices[0]["currency"]
    )
    pi.insert(ignore_permissions=True)
    pi.submit()
    return pi


def pay(pi, share, invoices, payment_account=None):
    """Record the part of `pi` Karma shows as paid that we haven't recorded yet. Returns the entry or None."""
    from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

    pi.reload()
    amount = amount_to_pay(flt(pi.rounded_total or pi.grand_total), flt(pi.outstanding_amount), share)
    if amount <= 0:
        return None
    pe = get_payment_entry("Purchase Invoice", pi.name, party_amount=amount, bank_account=payment_account or None)
    pe.reference_no = pi.bill_no
    pe.reference_date = nowdate()
    pe.custom_remarks = 1
    pe.remarks = _("Karma Global shows {0} as {1}.").format(
        pi.bill_no, ", ".join(sorted({inv["status"] for inv in invoices}))
    )
    pe.insert(ignore_permissions=True)
    pe.submit()
    return pe


def _flag(po, message):
    """Leave the mismatch on the PO once, so the buying team sees it where they work."""
    if frappe.db.exists("Comment", {"reference_doctype": "Purchase Order", "reference_name": po.name, "content": message}):
        return
    po.add_comment("Comment", message)


def _count(log, po_name, outcome, message=None):
    if outcome == "created":
        log.items_created += 1
    elif outcome == "updated":
        log.items_updated += 1
    elif outcome in ("flagged", "failed"):
        log.items_failed += 1
    if message:
        log.log_messages = (log.log_messages or "") + f"{po_name}: {message}\n"
