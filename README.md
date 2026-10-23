# Alaiy OS Connector: Karma Global

Connects Alaiy Commerce to Karma Global as a drop-ship supplier, through Karma's supplier API
(`alaiy_os_thealtomoda.api.karma_b2b`).

| What | How |
|---|---|
| Catalogue | `get_catalogue` (incremental on `modified_since`) → one Supplier Product per size, keyed on the size's Karma SKU |
| Inventory | `get_inventory` → stock and price of every size already pulled |
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

Requires `alaiy_os`, `erpnext` and `alaiy_os_commerce`.
