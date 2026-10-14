import pandas as pd

from signalforge.models import late_delivery as ld


def test_features_exclude_post_outcome_columns():
    banned = {
        "delivered_at",
        "carrier_at",
        "delivery_days",
        "delay_days",
        "review_score",
        "approved_at",
        "order_status",
        "is_late",
    }
    assert banned.isdisjoint(ld.FEATURES)
    for column in banned - {"is_late"}:
        assert column not in ld.FEATURE_SQL.split("FROM")[0], column


def test_split_is_chronological(con):
    df = ld.load_dataset(con)
    train, val, test = ld.chronological_split(df, ld.TrainSettings())
    assert train["purchased_at"].max() <= val["purchased_at"].min()
    assert val["purchased_at"].max() <= test["purchased_at"].min()
    assert len(train) + len(val) + len(test) == len(df)


def test_train_evaluate_and_baseline(con, tmp_path):
    model, meta, scored = ld.train_and_evaluate(ld.load_dataset(con))
    rep = meta["report"]
    assert rep["chosen_model"] != "baseline_prior"
    assert 0 <= rep["test"][rep["chosen_model"]]["pr_auc"] <= 1
    # the baseline's PR-AUC equals the base rate; reported so the model is judged against it
    assert abs(rep["test"]["baseline_prior"]["pr_auc"] - rep["split"]["test"]["late_rate"]) < 1e-9
    assert {"risk", "is_late"} <= set(scored.columns) and scored["risk"].between(0, 1).all()
    paths = ld.save_artifacts(model, meta, scored, tmp_path, "synthetic-demo")
    assert all(p.exists() for p in paths.values())
    assert pd.read_parquet(paths["scored_test"]).shape[0] == len(scored)


def test_too_little_data_is_rejected(con):
    import pytest

    with pytest.raises(ValueError, match="not enough"):
        ld.train_and_evaluate(ld.load_dataset(con).head(40))
