# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt

import frappe

from alaiy_os_connector_karmaglobal.connector_meta import connector_meta

SETTINGS = connector_meta["settings_doctype"]
# Owned by the running system, never overwritten from connector_meta.
RUNTIME_FIELDS = {"connection_status", "last_tested_at"}


def after_install():
    # A Password stored under another site's encryption key fails to decrypt on first load.
    frappe.db.set_single_value(SETTINGS, "kg_api_secret", "")
    frappe.db.commit()


def sync_connector_registry():
    """after_migrate: upsert this connector's OS Connector Registry row. Idempotent."""
    if not frappe.db.exists("DocType", "OS Connector Registry"):
        return

    connector_id = connector_meta["connector_id"]
    is_new = not frappe.db.exists("OS Connector Registry", connector_id)
    doc = frappe.new_doc("OS Connector Registry") if is_new else frappe.get_doc("OS Connector Registry", connector_id)
    for key, val in connector_meta.items():
        if (is_new or key not in RUNTIME_FIELDS) and hasattr(doc, key):
            doc.set(key, val)
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    _update_alaiy_os_sidebar()


def _update_alaiy_os_sidebar():
    """Show this connector's Logs link and card now, not after the next full migrate."""
    try:
        from alaiy_os.setup.install import (
            create_or_update_os_settings_workspace,
            create_or_update_os_settings_workspace_sidebar,
            create_or_update_workspace_sidebar,
        )

        create_or_update_workspace_sidebar()
        create_or_update_os_settings_workspace()
        create_or_update_os_settings_workspace_sidebar()
        frappe.db.commit()
    except Exception:
        frappe.log_error(title="Karma Global connector: sidebar update failed")
