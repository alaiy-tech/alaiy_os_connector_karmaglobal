# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import add_to_date, now_datetime

from alaiy_os_connector_karmaglobal.karmaglobal.sync import LOG, last_started

_INTERVAL_MINUTES = {"5 min": 5, "15 min": 15, "30 min": 30, "60 min": 60, "Daily": 1440}

# A sync "running" longer than this is treated as dead, so a crashed job never blocks the schedule.
_STALE_RUNNING_SECONDS = 1800


def check_and_enqueue():
    if not frappe.db.exists("DocType", LOG):
        return

    settings = frappe.get_single("Karma Global Connector Settings")
    if not settings.is_enabled:
        return

    _maybe_enqueue("catalogue", settings.kg_catalogue_sync_interval)
    _maybe_enqueue("inventory", settings.kg_inventory_sync_interval)


def _maybe_enqueue(sync_type, interval):
    minutes = _INTERVAL_MINUTES.get(interval)
    if not minutes:
        return

    now = now_datetime()
    running = last_started(sync_type, "running")
    if running and (now - running).total_seconds() < _STALE_RUNNING_SECONDS:
        return

    last_success = last_started(sync_type, "success")
    if last_success and now < add_to_date(last_success, minutes=minutes):
        return

    frappe.enqueue(
        f"alaiy_os_connector_karmaglobal.karmaglobal.sync.run_{sync_type}_sync",
        queue="long",
        timeout=3600,
        trigger="scheduled",
    )
