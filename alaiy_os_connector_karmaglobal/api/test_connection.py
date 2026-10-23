# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt

import frappe

from alaiy_os_connector_karmaglobal.karmaglobal.client import KarmaClient


@frappe.whitelist()
def test_connection():
    """Always {"success": bool, "message": str}; never raises."""
    try:
        result = KarmaClient().call("get_inventory", {"page_length": 1}, timeout=10)
        return {"success": True, "message": f"Connected (prices in {result['currency']})"}
    except Exception as e:
        return {"success": False, "message": str(e)[:200]}
