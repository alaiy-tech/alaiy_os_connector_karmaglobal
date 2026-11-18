# Columns of Karma Global Sync Log, named the way the Connector Health page reads them.
_LOG_FIELDS = {
    "processed": "items_processed",
    "changed": ["items_created", "items_updated"],
    "failed": "items_failed",
    "error": "error_message",
}


def _health(key, label, sync_type, interval_setting, expects_rows=True):
    return {
        "key": key,
        "label": label,
        "direction": "pull",
        "log_doctype": "Karma Global Sync Log",
        "log_filter": {"sync_type": sync_type},
        "fields": _LOG_FIELDS,
        "interval_setting": interval_setting,
        "scheduled": True,
        "expects_rows": expects_rows,
    }


connector_meta = {
    "connector_id": "karmaglobal",
    "connector_name": "Karma Global",
    "connector_app": "alaiy_os_connector_karmaglobal",
    "connector_type": "supplier",
    "description": "Pulls Karma Global's catalogue and stock into Supplier Products, checks live stock, places drop-ship orders and records Karma's invoices and payments against them.",
    "icon": "shirt",
    "icon_url": "",
    "settings_doctype": "Karma Global Connector Settings",
    "test_method": "alaiy_os_connector_karmaglobal.api.test_connection.test_connection",
    "sync_categories_method": "alaiy_os_connector_karmaglobal.api.sync.trigger_catalogue_sync",
    "sync_items_method": "alaiy_os_connector_karmaglobal.api.sync.trigger_inventory_sync",
    "sync_status_method": "alaiy_os_connector_karmaglobal.api.sync.get_sync_status",
    "sync_categories_label": "Catalogue",
    "sync_items_label": "Inventory",
    "is_enabled": 0,
    "connection_status": "untested",
    "health": [
        _health("catalogue", "Catalogue sync", "catalogue", "kg_catalogue_sync_interval"),
        _health("inventory", "Inventory sync", "inventory", "kg_inventory_sync_interval"),
        # No open Karma orders is a normal run with nothing to read.
        _health("invoices", "Invoice sync", "invoices", "kg_invoice_sync_interval", expects_rows=False),
    ],
}
