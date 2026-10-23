# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt

import math

import frappe
from alaiy_os_commerce.alaiy_os_commerce.doctype.supplier_product.supplier_product import get_existing_names
from alaiy_os_commerce.api.supplier_products import MAX_BATCH, upsert_supplier_products
from frappe.utils import add_to_date, flt, now_datetime

from alaiy_os_connector_karmaglobal.karmaglobal.client import KarmaClient

LOG = "Karma Global Sync Log"
CATALOGUE_PAGE = 50
INVENTORY_PAGE = 1000
# Karma's clock may run in another time zone; re-reading a day is cheap since unchanged rows are skipped.
MODIFIED_OVERLAP_HOURS = 24
# Cloudstore's internal labels, or already sent as real fields.
EXCLUDED_SPECS = {"Season", "Colors", "Interlem Description", "Size Scale"}


def get_or_create_log(sync_type, trigger, log_name=None):
    if log_name and frappe.db.exists(LOG, log_name):
        return frappe.get_doc(LOG, log_name)

    log = frappe.new_doc(LOG)
    log.sync_type = sync_type
    log.trigger = trigger
    log.status = "queued"
    log.insert(ignore_permissions=True)
    frappe.db.commit()
    return log


def last_started(sync_type, status):
    return frappe.db.get_value(
        LOG, {"sync_type": sync_type, "status": status}, "started_at", order_by="started_at desc"
    )


def _save(log):
    log.save(ignore_permissions=True)
    frappe.db.commit()


def _run(sync_type, trigger, log_name, worker):
    log = get_or_create_log(sync_type, trigger, log_name)
    since = last_started(sync_type, "success")
    log.status = "running"
    log.started_at = now_datetime()
    _save(log)
    try:
        worker(log, KarmaClient(), since)
        log.status = "success"
    except Exception:
        log.status = "failed"
        log.error_message = frappe.get_traceback()[:2000]
        frappe.log_error(title=f"Karma Global: {sync_type} sync failed")
        raise
    finally:
        log.finished_at = now_datetime()
        _save(log)


def run_catalogue_sync(trigger="scheduled", log_name=None):
    """Karma products changed since the last success, one Supplier Product per size."""

    def worker(log, client, since):
        params = {"page_length": CATALOGUE_PAGE}
        if since:
            params["modified_since"] = str(add_to_date(since, hours=-MODIFIED_OVERLAP_HOURS))
        start = 0
        while True:
            page = client.call("get_catalogue", {**params, "start": start})
            _upsert(log, client.supplier, [r for p in page["products"] for r in size_records(p)])
            log.pages_total = math.ceil(page["total"] / CATALOGUE_PAGE)
            log.pages_done += 1
            _save(log)
            start += CATALOGUE_PAGE
            if not page["products"] or start >= page["total"]:
                break

    _run("catalogue", trigger, log_name, worker)


def run_inventory_sync(trigger="scheduled", log_name=None):
    """Stock and price of every size already pulled by the catalogue sync."""

    def worker(log, client, since):
        known = get_existing_names(client.supplier)
        start = 0
        while True:
            page = client.call("get_inventory", {"start": start, "page_length": INVENTORY_PAGE})
            _upsert(
                log,
                client.supplier,
                [
                    _priced({"supplier_product_id": i["karma_sku"], "supplier_stock": flt(i["stock_qty"])}, i, page["currency"])
                    for i in page["items"]
                    if i["karma_sku"] in known
                ],
            )
            log.pages_done += 1
            _save(log)
            if len(page["items"]) < INVENTORY_PAGE:
                break
            start += INVENTORY_PAGE

    _run("inventory", trigger, log_name, worker)


def size_records(product):
    specs = {"Parent SKU": product["karma_sku"]}
    for key, label in (("color", "Color"), ("country_of_origin", "Country of Origin"), ("description", "Description")):
        if product.get(key):
            specs[label] = product[key]
    for a in product.get("attributes") or []:
        if a.get("value") and a.get("label") not in EXCLUDED_SPECS:
            specs.setdefault(a["label"], a["value"])
    season = next((a["value"] for a in product.get("attributes") or [] if a.get("label") == "Season"), None)

    records = []
    for v in product["variants"]:
        record = {
            "supplier_product_id": v["karma_sku"],
            "supplier_offer_id": product["karma_sku"],
            "title": product["title"],
            "brand": product.get("brand"),
            "category": product.get("category"),
            "season": season,
            "gender": product.get("gender"),
            "fulfilment": "Drop Ship",
            "supplier_stock": flt(v["stock_qty"]),
            "specs": {**specs, **{k: val for k, val in (("Size", v.get("size")), ("Barcode", v.get("barcode"))) if val}},
            "images": product.get("images") or None,
        }
        records.append(_priced(record, v, product["currency"]))
    return records


def _priced(record, row, currency):
    """Karma bills 0 for a size it has no price for yet; leave the stored price alone then."""
    record["currency"] = currency
    if flt(row["billing_price"]) > 0:
        record["cost_price"] = flt(row["billing_price"])
    return record


def _upsert(log, supplier, records):
    for i in range(0, len(records), MAX_BATCH):
        batch = records[i : i + MAX_BATCH]
        result = upsert_supplier_products(supplier, batch)
        frappe.db.commit()
        log.items_processed += len(batch)
        log.items_created += len(result["added"])
        log.items_updated += len(result["updated"])
        log.items_failed += len(result["errors"])
        if result["errors"]:
            log.log_messages = (log.log_messages or "") + "".join(
                f"{e['supplier_product_id']}: {e['error']}\n" for e in result["errors"]
            )
