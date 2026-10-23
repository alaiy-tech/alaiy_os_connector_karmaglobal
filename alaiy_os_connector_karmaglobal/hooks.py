app_name = "alaiy_os_connector_karmaglobal"
app_title = "Alaiy Os Connector Karmaglobal"
app_publisher = "Alaiy"
app_description = "Karma Global supplier connector for AlaiyOS"
app_email = "mail@alaiy.com"
app_license = "agpl-3.0"

required_apps = ["alaiy_os", "erpnext", "alaiy_os_commerce"]

after_install = ["alaiy_os_connector_karmaglobal.setup.install.after_install"]
after_migrate = ["alaiy_os_connector_karmaglobal.setup.install.sync_connector_registry"]

alaiy_os_sidebar_log_items = [
    {
        "link_type": "DocType",
        "link_to": "Karma Global Sync Log",
        "label": "Karma Global Logs",
        "icon": "activity",
    }
]

scheduler_events = {
    "cron": {
        "* * * * *": ["alaiy_os_connector_karmaglobal.karmaglobal.sync_jobs.check_and_enqueue"]
    }
}

# Asked by alaiy_os_commerce before it takes an order with Karma Global drop-ship lines.
supplier_stock_lookup = ["alaiy_os_connector_karmaglobal.karmaglobal.orders.get_stock"]

doc_events = {
    "Purchase Order": {
        "on_submit": "alaiy_os_connector_karmaglobal.karmaglobal.orders.place_order",
    },
}
