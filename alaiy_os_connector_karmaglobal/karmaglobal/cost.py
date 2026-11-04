# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt

"""
`supplier_cost_lookup` hook: Karma Global's current B2B price, for Alaiy Commerce's price runs.

A price run with "refresh cost" asks every connector for the cost of each supplier's products before it
prices them. This one answers for the Supplier named in Karma Global Connector Settings with Karma's
`billing_price` for each size, the price Karma bills Alaiy, read from `get_inventory` filtered by
`karma_skus`, so only the sizes asked about are read.

Return contract (alaiy_os_commerce.price_runs.refresh_costs):
- another Supplier, or the connector is switched off: None
- otherwise {karma_sku: {"cost": billing_price, "currency": currency}} for each size asked about that Karma
  prices. A size Karma does not list, or bills at 0 (no price yet), is left out, and Commerce keeps its
  stored cost.
- Karma cannot be read: raise. Commerce logs it, flags those products and keeps their stored cost.
"""

import json

from frappe.utils import flt

from alaiy_os_connector_karmaglobal.karmaglobal.client import KarmaClient
from alaiy_os_connector_karmaglobal.karmaglobal.orders import _serves

# Sizes per get_inventory call. The SKUs travel in the query string, so keep the URL short.
SKU_BATCH = 100


def lookup(supplier, supplier_product_ids):
    if not _serves(supplier):
        return None

    skus = sorted(set(supplier_product_ids))
    costs = {}
    if not skus:
        return costs

    client = KarmaClient()
    for i in range(0, len(skus), SKU_BATCH):
        batch = skus[i : i + SKU_BATCH]
        # With karma_skus, Karma returns every size asked for in one page.
        page = client.call("get_inventory", {"karma_skus": json.dumps(batch)})
        for item in page["items"]:
            if item["karma_sku"] in batch and flt(item["billing_price"]) > 0:
                costs[item["karma_sku"]] = {"cost": flt(item["billing_price"]), "currency": page["currency"]}
    return costs
