# Dataset setup

## Candidate dataset

**Brazilian E-Commerce Public Dataset by Olist**, published on Kaggle: <https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce>.

Verified from public descriptions:

- Shared by Olist, a Brazilian marketplace platform.
- About 100 thousand orders placed between 2016 and 2018 at multiple marketplaces in Brazil.
- Real commercial data, anonymised; company and partner names in review text are replaced.
- Nine CSV files.

### Expected files

| File | Content |
|---|---|
| `olist_orders_dataset.csv` | Core order table |
| `olist_order_items_dataset.csv` | Items in each order, with price and freight |
| `olist_order_payments_dataset.csv` | Payment records per order |
| `olist_order_reviews_dataset.csv` | Customer reviews and scores |
| `olist_customers_dataset.csv` | Customers and location |
| `olist_sellers_dataset.csv` | Sellers and location |
| `olist_products_dataset.csv` | Product attributes |
| `olist_geolocation_dataset.csv` | Postal-code prefixes with coordinates |
| `product_category_name_translation.csv` | Category names translated to English |

Column-level schemas are **not** asserted here. They are confirmed and recorded during milestone 2 by reading the downloaded files.

## Attribution and licence

- **Dataset:** Brazilian E-Commerce Public Dataset by Olist, <https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce>.
- **Licence:** CC BY-NC-SA 4.0, as stated by the project owner. It was not independently confirmed from this environment (Kaggle was unreachable); read the licence on the Kaggle page.
- **Consequences:** attribution to Olist is required; **non-commercial use only** (CC BY-NC-SA does not permit commercial use); derivatives must be shared under the same licence. Any commercial deployment needs permission from Olist or a commercially licensed alternative dataset. The MIT licence of this repository covers code only and transfers no dataset rights. Raw data and rows are never committed.

## Required files (all checked by `signalforge verify-raw`)

`olist_orders_dataset.csv`, `olist_order_items_dataset.csv`, `olist_order_payments_dataset.csv`, `olist_order_reviews_dataset.csv`, `olist_customers_dataset.csv`, `olist_sellers_dataset.csv`, `olist_products_dataset.csv`, `product_category_name_translation.csv`. The ninth file, `olist_geolocation_dataset.csv`, is optional and currently unused. Required columns are listed in `src/signalforge/schema.py`; they follow the public description and are **unconfirmed against the real headers** until a real load is done.

## Status

**Real data has not been loaded.** Attempts to reach kaggle.com failed (HTTP 403 from the environment's egress policy) and no Kaggle CLI or credentials exist in the workspace. All runs so far use the seeded synthetic generator (`signalforge demo-data`), which writes `data/raw/_SYNTHETIC_DEMO.txt` so every output is labelled synthetic.

## Acquire the real data (manual)

1. In the cloud environment settings, allow outbound access to `kaggle.com` (Network access > Allowed domains), and add `KAGGLE_USERNAME` / `KAGGLE_KEY` as environment secrets (never paste them in chat). Alternatively download the archive on your own machine.
2. Use a **separate data directory** so synthetic and real data never mix: `export SIGNALFORGE_DATA_DIR=/path/to/real-data`.
3. `pip install kaggle && kaggle datasets download -d olistbr/brazilian-ecommerce -p $SIGNALFORGE_DATA_DIR/raw --unzip` (or unzip the manually downloaded archive there).
4. `signalforge verify-raw` - checks the files, rejects the synthetic marker, writes SHA-256 hashes and row counts to `<data_dir>/interim/raw_provenance.json`.
5. `signalforge build && signalforge reconcile && signalforge report && signalforge train`.
6. Expect to fix schema or check failures on first real load; do not relax a check without recording the business reason in `docs/EXECUTION_STATUS.md`.

`signalforge demo-data` refuses to write into a directory that holds non-synthetic dataset files (unless `--force`).
