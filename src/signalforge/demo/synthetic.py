"""Seeded synthetic generator that mimics the Olist table layout.

PURPOSE: let tests and the demo run without the real dataset. The data is invented; every
number computed from it describes the generator, not any real business. A marker file is
written next to the CSVs so downstream layers label the data source honestly.
The generator deliberately plants dirty-data cases (duplicate reviews, orders without
reviews, cancelled/undelivered orders, multi-item and split-payment orders, missing
category translations) so the quality and modelling code is exercised.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from signalforge.schema import SYNTHETIC_MARKER

STATES = ["SP", "RJ", "MG", "RS", "PR", "BA", "SC", "PE", "CE", "DF"]
STATE_P = [0.38, 0.14, 0.12, 0.07, 0.07, 0.06, 0.05, 0.04, 0.04, 0.03]
CATEGORIES = {
    "cama_mesa_banho": "bed_bath_table",
    "beleza_saude": "health_beauty",
    "esporte_lazer": "sports_leisure",
    "informatica_acessorios": "computers_accessories",
    "moveis_decoracao": "furniture_decor",
    "utilidades_domesticas": "housewares",
    "relogios_presentes": "watches_gifts",
    "telefonia": "telephony",
    "brinquedos": "toys",
    "ferramentas_jardim": "garden_tools",
    "pc_gamer_novo": "",  # deliberately missing translation
}
FMT = "%Y-%m-%d %H:%M:%S"


def _ts(series: pd.Series) -> pd.Series:
    return series.dt.strftime(FMT)


def generate(out_dir: Path, n_orders: int = 6000, seed: int = 7) -> dict[str, int]:
    """Write nine Olist-style CSVs into ``out_dir``; return row counts."""
    rng = np.random.default_rng(seed)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # --- sellers and products -------------------------------------------------------
    n_sellers, n_products = 120, 900
    seller_state = rng.choice(
        STATES, n_sellers, p=[0.6, 0.08, 0.07, 0.05, 0.06, 0.03, 0.05, 0.02, 0.02, 0.02]
    )
    seller_ids = [f"s{idx:05d}" for idx in range(n_sellers)]
    sellers = pd.DataFrame(
        {
            "seller_id": seller_ids,
            "seller_zip_code_prefix": rng.integers(10000, 99999, n_sellers).astype(str),
            "seller_city": [f"city_{s}" for s in seller_state],
            "seller_state": seller_state,
        }
    )
    seller_risk = rng.normal(0, 0.5, n_sellers)  # latent seller reliability (hidden)
    cats = list(CATEGORIES)
    products = pd.DataFrame(
        {
            "product_id": [f"p{idx:06d}" for idx in range(n_products)],
            "product_category_name": rng.choice(cats, n_products),
            "product_name_lenght": rng.integers(20, 70, n_products),
            "product_description_lenght": rng.integers(100, 2000, n_products),
            "product_photos_qty": rng.integers(1, 8, n_products),
            "product_weight_g": rng.lognormal(6.5, 0.9, n_products).round(),
            "product_length_cm": rng.integers(10, 80, n_products),
            "product_height_cm": rng.integers(2, 50, n_products),
            "product_width_cm": rng.integers(8, 60, n_products),
        }
    )
    products.loc[rng.choice(n_products, 15, replace=False), "product_category_name"] = np.nan
    products.loc[rng.choice(n_products, 5, replace=False), "product_weight_g"] = np.nan
    translation = pd.DataFrame(
        {
            "product_category_name": [k for k, v in CATEGORIES.items() if v],
            "product_category_name_english": [v for v in CATEGORIES.values() if v],
        }
    )

    # --- customers ------------------------------------------------------------------
    n_people = int(n_orders * 0.93)
    person_state = rng.choice(STATES, n_people, p=STATE_P)
    order_person = np.concatenate(
        [np.arange(n_people), rng.integers(0, n_people, n_orders - n_people)]
    )
    rng.shuffle(order_person)
    customers = pd.DataFrame(
        {
            "customer_id": [f"c{idx:07d}" for idx in range(n_orders)],
            "customer_unique_id": [f"u{p:07d}" for p in order_person],
            "customer_zip_code_prefix": rng.integers(10000, 99999, n_orders).astype(str),
            "customer_city": [f"city_{person_state[p]}" for p in order_person],
            "customer_state": person_state[order_person],
        }
    )

    # --- orders and items -----------------------------------------------------------
    start, end = pd.Timestamp("2017-01-01"), pd.Timestamp("2018-08-31")
    span = (end - start).total_seconds()
    # Mild growth over time + a November bump.
    u = rng.beta(1.6, 1.0, n_orders)
    purchase = start + pd.to_timedelta(np.sort(u * span), unit="s")
    purchase = pd.Series(purchase).dt.floor("s")
    n_items = rng.choice([1, 2, 3], n_orders, p=[0.8, 0.14, 0.06])
    item_rows = []
    order_primary_seller = np.empty(n_orders, dtype=int)
    for oid in range(n_orders):
        sel = int(rng.choice(n_sellers, p=None)) if oid else 0
        order_primary_seller[oid] = sel
        for k in range(n_items[oid]):
            sidx = sel if k == 0 or rng.random() < 0.6 else int(rng.integers(n_sellers))
            item_rows.append((oid, k + 1, int(rng.integers(n_products)), sidx))
    items = pd.DataFrame(item_rows, columns=["oid", "order_item_id", "pidx", "sidx"])
    items["price"] = rng.lognormal(4.3, 0.8, len(items)).round(2).clip(5, 3000)
    order_state = customers["customer_state"].to_numpy()
    cross = (seller_state[items["sidx"]] != order_state[items["oid"]]).astype(float)
    items["freight_value"] = (7 + 9 * cross + rng.gamma(2.0, 2.5, len(items))).round(2)
    items["shipping_limit_date"] = _ts(
        purchase[items["oid"]].reset_index(drop=True) + pd.Timedelta(days=4)
    )

    first_item = items[items["order_item_id"] == 1].set_index("oid")
    cross_o = (seller_state[first_item["sidx"].to_numpy()] != order_state).astype(float)
    freight_o = items.groupby("oid")["freight_value"].sum().to_numpy()
    val_o = items.groupby("oid")["price"].sum().to_numpy()
    month = purchase.dt.month.to_numpy()
    est_days = np.round(9 + 8 * cross_o + rng.normal(0, 2.5, n_orders) + 3).clip(5, 60)
    logit = (
        -2.9
        + 1.1 * cross_o
        + 0.04 * (freight_o / np.maximum(val_o, 1) * 10)
        + 0.9 * (month == 11)
        + seller_risk[first_item["sidx"].to_numpy()]
        + rng.normal(0, 0.3, n_orders)
    )
    late = rng.random(n_orders) < 1 / (1 + np.exp(-logit))
    delay = np.where(late, rng.exponential(5, n_orders) + 1, -rng.uniform(1, 9, n_orders))
    approved = purchase + pd.to_timedelta(rng.integers(600, 36000, n_orders), unit="s")
    carrier = approved + pd.to_timedelta(rng.integers(1, 5, n_orders), unit="D")
    estimated = (purchase + pd.to_timedelta(est_days, unit="D")).dt.floor("D")
    delivered = (
        estimated
        + pd.to_timedelta(np.round(delay), unit="D")
        + pd.to_timedelta(rng.integers(0, 20, n_orders), unit="h")
    )
    delivered = delivered.where(delivered > carrier, carrier + pd.Timedelta(days=2))

    status = rng.choice(
        ["delivered", "canceled", "shipped", "unavailable", "invoiced"],
        n_orders,
        p=[0.965, 0.015, 0.01, 0.005, 0.005],
    )
    # Recent orders can still be in flight at the end of the extract.
    status = np.where(delivered > end, "shipped", status)
    is_del = status == "delivered"
    orders = pd.DataFrame(
        {
            "order_id": [f"o{idx:07d}" for idx in range(n_orders)],
            "customer_id": customers["customer_id"],
            "order_status": status,
            "order_purchase_timestamp": _ts(purchase),
            "order_approved_at": _ts(approved),
            "order_delivered_carrier_date": _ts(carrier.where(status != "canceled")),
            "order_delivered_customer_date": _ts(delivered.where(is_del)),
            "order_estimated_delivery_date": _ts(estimated),
        }
    )
    order_items = pd.DataFrame(
        {
            "order_id": orders["order_id"].to_numpy()[items["oid"]],
            "order_item_id": items["order_item_id"],
            "product_id": products["product_id"].to_numpy()[items["pidx"]],
            "seller_id": np.array(seller_ids)[items["sidx"]],
            "shipping_limit_date": items["shipping_limit_date"],
            "price": items["price"],
            "freight_value": items["freight_value"],
        }
    )

    # --- payments -------------------------------------------------------------------
    totals = (val_o + freight_o).round(2)
    pay_rows = []
    for oid in range(n_orders):
        ptype = rng.choice(
            ["credit_card", "boleto", "voucher", "debit_card"], p=[0.74, 0.2, 0.02, 0.04]
        )
        inst = int(rng.choice([1, 2, 3, 5, 10])) if ptype == "credit_card" else 1
        if rng.random() < 0.04:  # split payment: voucher + card
            part = round(float(totals[oid]) * 0.3, 2)
            pay_rows += [
                (oid, 1, "voucher", 1, part),
                (oid, 2, "credit_card", inst, round(float(totals[oid]) - part, 2)),
            ]
        else:
            pay_rows.append((oid, 1, ptype, inst, float(totals[oid])))
    pay = pd.DataFrame(
        pay_rows,
        columns=[
            "oid",
            "payment_sequential",
            "payment_type",
            "payment_installments",
            "payment_value",
        ],
    )
    pay.insert(0, "order_id", orders["order_id"].to_numpy()[pay.pop("oid")])

    # --- reviews --------------------------------------------------------------------
    rev_rows = []
    for oid in np.flatnonzero(is_del):
        if rng.random() < 0.12:
            continue  # no review
        p_low = 0.55 if late[oid] else 0.07
        score = int(
            rng.choice([1, 2])
            if rng.random() < p_low
            else rng.choice([3, 4, 5], p=[0.12, 0.28, 0.6])
        )
        created = delivered[oid].floor("D") + pd.Timedelta(days=int(rng.integers(0, 3)))
        rev_rows.append(
            (
                f"r{len(rev_rows):07d}",
                orders["order_id"][oid],
                score,
                created,
                created + pd.Timedelta(hours=int(rng.integers(1, 72))),
            )
        )
        if rng.random() < 0.02:  # second review for the same order
            rev_rows.append(
                (
                    f"r{len(rev_rows):07d}",
                    orders["order_id"][oid],
                    int(rng.integers(1, 6)),
                    created + pd.Timedelta(days=5),
                    created + pd.Timedelta(days=6),
                )
            )
    reviews = pd.DataFrame(
        rev_rows,
        columns=[
            "review_id",
            "order_id",
            "review_score",
            "review_creation_date",
            "review_answer_timestamp",
        ],
    )
    reviews["review_comment_title"] = np.nan
    reviews["review_comment_message"] = np.nan
    reviews["review_creation_date"] = _ts(reviews["review_creation_date"])
    reviews["review_answer_timestamp"] = _ts(reviews["review_answer_timestamp"])
    reviews = reviews[
        [
            "review_id",
            "order_id",
            "review_score",
            "review_comment_title",
            "review_comment_message",
            "review_creation_date",
            "review_answer_timestamp",
        ]
    ]

    files = {
        "olist_orders_dataset.csv": orders,
        "olist_order_items_dataset.csv": order_items,
        "olist_order_payments_dataset.csv": pay,
        "olist_order_reviews_dataset.csv": reviews,
        "olist_customers_dataset.csv": customers,
        "olist_sellers_dataset.csv": sellers,
        "olist_products_dataset.csv": products,
        "product_category_name_translation.csv": translation,
    }
    for name, frame in files.items():
        frame.to_csv(out_dir / name, index=False)
    (out_dir / SYNTHETIC_MARKER).write_text(
        "Synthetic data generated by signalforge.demo.synthetic. Not real business data.\n",
        encoding="utf-8",
    )
    return {name: len(frame) for name, frame in files.items()}
