# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt

from alaiy_os_connector_karmaglobal.karmaglobal.client import SETTINGS, KarmaClient

# Karma looks up at most this many sizes live per check_stock call.
LIVE_BATCH = 25


def _serves(supplier):
    settings = frappe.get_cached_doc(SETTINGS)
    return settings.is_enabled and supplier == settings.kg_supplier


def get_stock(supplier, supplier_product_ids):
    """`supplier_stock_lookup` hook: Karma's live stock of each size, or None for another supplier."""
    if not _serves(supplier):
        return None

    client = KarmaClient()
    stock = {}
    for i in range(0, len(supplier_product_ids), LIVE_BATCH):
        skus = supplier_product_ids[i : i + LIVE_BATCH]
        result = client.call(
            "check_stock", body={"items": [{"karma_sku": s, "qty": 1} for s in skus], "live": 1}, timeout=15
        )
        stock.update({line["karma_sku"]: line["available_qty"] for line in result["lines"]})
    return stock


def place_order(doc, method=None):
    """Purchase Order on_submit: place the same lines with Karma, keyed on the PO name."""
    if not _serves(doc.supplier):
        return

    skus = dict(
        frappe.get_all(
            "Supplier Product",
            filters={"supplier": doc.supplier, "item": ("in", [d.item_code for d in doc.items])},
            fields=["item", "supplier_product_id"],
            as_list=True,
        )
    )
    items = []
    for d in doc.items:
        if d.item_code not in skus:
            frappe.throw(_("Row {0}: {1} has no Karma Global SKU.").format(d.idx, d.item_code))
        if not flt(d.stock_qty).is_integer():
            frappe.throw(_("Row {0}: Karma Global takes whole quantities only.").format(d.idx))
        items.append({"karma_sku": skus[d.item_code], "qty": int(d.stock_qty)})

    result = KarmaClient().call(
        "receive_order",
        body={"order": {"order_id": doc.name, "items": items, "delivery_date": str(doc.schedule_date)}},
    )
    doc.db_set("order_confirmation_no", result["sales_order"])
