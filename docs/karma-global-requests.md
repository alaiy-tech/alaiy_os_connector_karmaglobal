# What Alaiy needs from Karma Global

Alaiy Commerce reads Karma Global through Karma's supplier API (`alaiy_os_thealtomoda.api.karma_b2b`),
using this connector. This note lists what we need from that API, and the questions only Karma can answer.
Each item says what it unblocks.

## What we use today

| Call | What we read | Used for |
|---|---|---|
| `get_catalogue` | Per product: brand, category, color, country of origin, currency, description, gender, images, Karma SKU, title, attributes, modified. Per size: barcode, `billing_price`, Karma SKU, size, `stock_qty` | Supplier Products (one per size), and Alaiy's daily full pull of the whole catalogue |
| `get_inventory` | Per size: `billing_price`, `stock_qty`, plus the page currency | The 15-minute inventory sync, and refreshing cost before a price run |
| `check_stock` (live) | Per size: `available_qty` | Refusing an order Karma can't cover, and Alaiy's hourly stock sync |
| `receive_order` | Karma's Sales Order name | Placing Alaiy's Purchase Orders with Karma |

Alaiy prices Karma products starting from `billing_price`: Alaiy's rule adds only Alaiy's margin and
rounding. The questions in section 1 about that price are therefore the most important.

## 1. Questions about `billing_price`

1. **What is in it?** We read it as Karma's B2B price to Alaiy, landed in India: Karma's cost from The
   Corner, plus Karma's margin, FX, first-mile freight, insurance and customs duty. Please confirm, and
   say whether anything is left out, such as import IGST.
2. **Which cost does it start from?** The pricing requirements say Karma's cost is CloudStore's
   `sale_price` (equal to `props.buy_price` × 1.2), and that `stock_price` is the retail price. The CloudStore
   connector's own code says buying cost comes from `stock_price`. Please confirm which field
   `billing_price` is built on. If it is `stock_price`, every price built on it is a retail-based figure.
3. **Is it ex-GST?** Alaiy's prices are ex-GST, and GST is added on the invoice.
4. **Currency:** today it is EUR. Can it change per product or per page? We read the currency from each
   page.
5. **When does it change?** Is it recalculated when FX, freight or duty changes, or when the catalogue
   syncs? Is there a date or version we can store with it?
6. **What does 0 mean?** We treat a `billing_price` of 0 as "not priced yet" and keep our stored price.
   Please confirm.

## 2. Data we need added to the API

These matter only when Alaiy's own rule computes duty or freight. While Alaiy starts from Karma's landed
`billing_price`, they are not needed. Without them, though, Alaiy can't check or rebuild that price, or
price these products for a buyer on different terms.

| Field | Where | Notes |
|---|---|---|
| `hs_code` | Per product, or per size if it varies | The CloudStore feed already carries it in `props.hs_code` (for example `6404110000`). 8 digits for Indian customs where known |
| `weight_kg` | Per size | Packed weight if Karma has it, else net weight, and say which |
| `length_cm`, `width_cm`, `height_cm` | Per size | Packed dimensions, for volumetric weight |

When these arrive, the connector sends them as Supplier Product fields, and Alaiy copies them to the
Item.

## 3. API behaviour we need confirmed

1. **The largest `page_length` for `get_catalogue` and `get_inventory`.** Alaiy's full pull asks for 200
   and gets 200 today. The connector now moves on by the number of products returned, so a cap won't
   skip products. We still need to know the limit.
2. **Stable ordering while paging.** If the catalogue changes during a full pull, can a product move
   between pages and be skipped or read twice? A product missing from a full pull gets stock 0 in Alaiy.
   Please confirm the order (for example by Karma SKU), or offer a snapshot or cursor.
3. **Delisted products.** When Karma stops selling a product, does it disappear from `get_catalogue`? Or
   does it stay, with stock 0 or a flag? Either works if we know which.
4. **A cost lookup for specific SKUs.** To refresh cost for a few products, the connector pages through
   all of `get_inventory`. A `skus` filter on `get_inventory`, or a price in `check_stock`'s answer, would
   make that one call.
5. **Rate limits:** the call rate and concurrency Alaiy may use. Today Alaiy runs:
   - a 15-minute inventory sync;
   - an hourly live stock check for curated products, in batches of 25;
   - a daily full catalogue pull;
   - a live stock check per order.

## 4. Where Karma's own pricing runs

Alaiy's pricing engine can also run Karma's steps (margin, FX, freight, insurance, duty by HS code) and
show the full breakdown per product. If Karma runs that engine on its own site, `billing_price` would come
from it, with the breakdown available for review. Please say:

- where `billing_price` is calculated today;
- who maintains Karma's margin, FX, freight rate card and duty rates;
- whether Karma wants to use the engine for this.

## Contact

Send answers to the Alaiy pricing team. Changes to the API calls above need a matching connector
release, so please give notice before changing a field name or a response shape.
