# Alaiy OS Connector: Karma Global

Connects Alaiy Commerce to Karma Global as a drop-ship supplier, through Karma's supplier API
(`alaiy_os_thealtomoda.api.karma_b2b`).

| What | How |
|---|---|
| Catalogue | `get_catalogue` (incremental on `modified_since`) → one Supplier Product per size, keyed on the size's Karma SKU |
| Full Pull | `supplier_catalogue_pull` hook → the whole catalogue (`get_catalogue`, every page) for Commerce's daily pull, one record per size. Answers only for the Supplier named in the settings; a dry run reads nothing |
| Inventory | `get_inventory` → stock and price of every size already pulled |
| Cost refresh | `supplier_cost_lookup` hook → Karma's current `billing_price` per size from `get_inventory`, for Commerce price runs that refresh cost |
| Stock check | `supplier_stock_lookup` hook → live `check_stock`, so Commerce refuses an order Karma can't cover |
| Orders | Submitting a Purchase Order to the Karma supplier calls `receive_order` (idempotent on the PO name); Karma's Sales Order lands in *Order Confirmation No* |

## Setup

```bash
bench get-app alaiy_os_connector_karmaglobal <repo>
bench --site <site> install-app alaiy_os_connector_karmaglobal
```

Open **Karma Global Connector Settings**: API URL, the API key/secret Karma issued (a *Karma Integration* user
linked to the buyer Customer), and the Supplier to file products and orders under. Enable, Test Connection,
then run Sync Catalogue.

With the Supplier on **Full Pull** the connector's own catalogue push is redundant (both write through the same upsert, so
running both is safe), and its 15-minute inventory sync overlaps Commerce's hourly stock sync. Either can be turned off in
the settings, no code needed.

Requires `alaiy_os`, `erpnext` and `alaiy_os_commerce`.

## Pricing engine

Alaiy Commerce prices Karma Global products from Karma's B2B price, which this connector already writes:
each size's `billing_price` becomes the Supplier Product's cost, and so the Item's buying price.
Karma's own steps (its margin, FX, freight, insurance and duty) run on Karma's side and produce that
price; Commerce's rule only adds Alaiy's margin and rounding.

| Commerce needs | From this connector |
|---|---|
| Fresh cost before a price run | `supplier_cost_lookup` (above). A size Karma doesn't list or bills at 0 keeps its stored cost |
| HS code per product | **Not available.** Karma's `get_catalogue` sends no HS code |
| Weight and dimensions | **Not available.** Karma's API sends no weight or dimensions |

HS code, weight and dimensions only matter to Commerce when Commerce's own rule has a Customs duty or
Freight step. While Alaiy's rule starts from Karma's landed B2B price, it doesn't need them.

**Requested of Karma's API**, for when Commerce's rule computes duty or freight itself:

- `hs_code` per product or size in `get_catalogue`. The CloudStore feed Karma reads already carries it
  in `props.hs_code`.
- `weight_kg` and packed `length_cm`, `width_cm`, `height_cm` per size, where Karma has them.

When they exist, `size_records` should send them as the Supplier Product fields `hs_code`, `weight`,
`length`, `width` and `height`, which Commerce copies to the Item.
