# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt

import frappe

from alaiy_os_connector_karmaglobal.karmaglobal.sync import LOG, get_or_create_log


def _trigger(sync_type):
    frappe.only_for("System Manager")
    log = get_or_create_log(sync_type, "manual")
    frappe.enqueue(
        f"alaiy_os_connector_karmaglobal.karmaglobal.sync.run_{sync_type}_sync",
        queue="long",
        timeout=3600,
        trigger="manual",
        log_name=log.name,
    )
    return {"queued": True, "log_name": log.name}


@frappe.whitelist()
def trigger_catalogue_sync():
    return _trigger("catalogue")


@frappe.whitelist()
def trigger_inventory_sync():
    return _trigger("inventory")


@frappe.whitelist()
def get_sync_status(sync_type=None):
    """Latest logs; the connector card passes its slot name ("categories" / "items")."""
    filters = {}
    if sync_type:
        filters["sync_type"] = {"categories": "catalogue", "items": "inventory"}.get(sync_type, sync_type)
    return frappe.get_all(
        LOG,
        filters=filters,
        fields=[
            "name", "sync_type", "trigger", "status",
            "started_at", "finished_at",
            "items_processed", "items_created", "items_updated", "items_failed",
            "pages_total", "pages_done",
            "error_message",
        ],
        order_by="started_at desc",
        limit=5,
    )
