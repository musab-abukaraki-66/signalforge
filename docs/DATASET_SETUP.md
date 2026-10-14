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

## Status in this repository

The real files were **not downloaded** in the build session: the sandbox egress proxy refused `kaggle.com` (HTTP 403). The pipeline was therefore developed and tested against a seeded synthetic generator that reproduces the table layout (`signalforge demo-data`). Synthetic runs write a marker file (`data/raw/_SYNTHETIC_DEMO.txt`) so the warehouse, report and dashboard label themselves as synthetic.

## Licensing (must be checked before use)

Read the licence on the Kaggle dataset page yourself before using or redistributing anything derived from the data. See the note at the end of this file for what research could and could not confirm. Do not commit the data or publish raw rows. This repository's MIT licence covers the code only and does not transfer any dataset rights.

## Reproducible setup

1. Create a free Kaggle account and accept the dataset terms.
2. Download the archive from the page above (or `kaggle datasets download -d olistbr/brazilian-ecommerce -p data/raw --unzip`, with the API token kept outside the repository).
3. Place the CSV files in `data/raw/` (git-ignored). The geolocation file is optional and currently unused.
4. Remove `data/raw/_SYNTHETIC_DEMO.txt` if it exists, then run `signalforge build`. The build records file hashes, sizes and row counts in `data/interim/bronze_manifest.json`.

No synthetic demo yet? `signalforge demo-data` writes invented data with the same layout.

## Research note (licence and schema)

A bounded search could not reach kaggle.com, so the **licence is unverified**: no primary source was read, and no secondhand source quoted a licence field. Treat the dataset as "terms unknown until you read the Kaggle page". Secondhand sources list nine files and the misspelt column `product_name_lenght`; neither was confirmed against real headers (ingestion checks them on first real load). Olist describes the data as real, anonymised commercial data (about 100k orders, 2016-2018).
