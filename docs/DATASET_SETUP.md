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

## Licensing (must be checked before use)

The licence is shown on the Kaggle dataset page and **was not verified when this document was written**. Before using or redistributing anything derived from the data:

1. Open the dataset page and read the stated licence and terms.
2. Respect any non-commercial, attribution or share-alike conditions.
3. Do not commit the data or publish raw rows. This repository's MIT licence applies to the code only.

## Reproducible setup

1. Create a free Kaggle account and accept the dataset terms.
2. Download the dataset archive from the page above.
3. Unzip the nine CSV files into `data/raw/` (git-ignored).
4. Record the file names, sizes and SHA-256 hashes in a local manifest. Ingestion (milestone 2) will automate this.
5. Never commit files from `data/`.

Using the Kaggle CLI instead (needs an API token stored outside the repository, never in git):

```bash
kaggle datasets download -d olistbr/brazilian-ecommerce -p data/raw --unzip
```

## Known caveats to investigate in milestone 2

- Customer identifiers: confirm which id is per order and which identifies a returning customer.
- Orders can have multiple payment rows and multiple reviews.
- Order status values and missing delivery dates for non-delivered orders.
- The dataset has no cost, commission or profit data (see [BUSINESS_METRICS.md](BUSINESS_METRICS.md)).
