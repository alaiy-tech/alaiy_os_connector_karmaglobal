# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt

"""
`supplier_catalogue_pull` hook: Alaiy Commerce's daily Full Pull of the Karma Global catalogue.

Commerce asks every connector whether it serves a Supplier. This one answers for the Supplier named in
Karma Global Connector Settings and returns the whole catalogue, one record per size, built by the same
`size_records` the connector's own catalogue sync uses.

Return contract (alaiy_os_commerce.catalogue_pull):
- another Supplier, or the connector is switched off: None
- dry_run: [] without reading anything (Commerce calls this whenever a supplier opens their settings)
- otherwise every product. Commerce sets the stock of a product that is missing from the answer to 0, so
  the answer is always the whole catalogue, never a changed-since slice.
- Karma cannot be read: raise. Commerce logs it, writes nothing and tries again the next day.
"""

import frappe

from alaiy_os_connector_karmaglobal.karmaglobal.client import SETTINGS, KarmaClient
from alaiy_os_connector_karmaglobal.karmaglobal.sync import size_records

# Karma's largest page for get_catalogue; the whole catalogue (about 3,800 sizes) is a handful of reads.
PULL_PAGE = 200


def pull(supplier, dry_run=False):
    settings = frappe.get_cached_doc(SETTINGS)
    if not settings.is_enabled or supplier != settings.kg_supplier:
        return None
    if dry_run:
        return []

    client = KarmaClient()
    records = []
    start = 0
    while True:
        page = client.call("get_catalogue", {"page_length": PULL_PAGE, "start": start})
        for product in page["products"]:
            records.extend(size_records(product))
        start += PULL_PAGE
        if not page["products"] or start >= page["total"]:
            return records
