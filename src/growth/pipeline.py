"""Reproducible source audit, SQLite mart, uncertainty estimates, and exports.

Run with `PYTHONPATH=src python -m growth.pipeline`. Raw CSVs are not shipped.
All monetary values are Brazilian reais (BRL), item price only, not profit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd


RAW_FILES = {
    "leads": "olist_marketing_qualified_leads_dataset.csv",
    "wins": "olist_closed_deals_dataset.csv",
    "items": "olist_order_items_dataset.csv",
    "orders": "olist_orders_dataset.csv",
}
ORDER_CUTOFF = pd.Timestamp("2018-08-31 23:59:59")
WIN_OBSERVATION_END = pd.Timestamp("2018-11-14 23:59:59")
CHANNELS = [
    "organic_search", "paid_search", "social", "direct_traffic", "email",
    "referral", "display", "other_publicities", "other", "unknown", "missing",
]


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total <= 0:
        return (0.0, 0.0)
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    half = z * np.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return float(max(0, center - half)), float(min(1, center + half))


def bootstrap_mean(values: np.ndarray, seed: int = 20260916, draws: int = 2000) -> tuple[float, float]:
    """Percentile interval for a descriptive mean, not a causal effect."""
    if not len(values):
        return (0.0, 0.0)
    rng = np.random.default_rng(seed)
    means = np.empty(draws)
    for i in range(draws):
        means[i] = rng.choice(values, size=len(values), replace=True).mean()
    return tuple(float(x) for x in np.quantile(means, [0.025, 0.975]))


def audit_and_load(raw_dir: Path) -> tuple[dict[str, pd.DataFrame], dict]:
    missing = [name for name in RAW_FILES.values() if not (raw_dir / name).is_file()]
    if missing:
        raise FileNotFoundError("Missing source CSVs: " + ", ".join(missing))

    tables = {key: pd.read_csv(raw_dir / filename, low_memory=False) for key, filename in RAW_FILES.items()}
    leads, wins, items, orders = (tables[x] for x in ("leads", "wins", "items", "orders"))
    for key, columns in {
        "leads": ["mql_id", "first_contact_date", "origin"],
        "wins": ["mql_id", "seller_id", "won_date"],
        "items": ["order_id", "order_item_id", "seller_id", "price"],
        "orders": ["order_id", "order_status", "order_purchase_timestamp"],
    }.items():
        absent = sorted(set(columns) - set(tables[key].columns))
        if absent:
            raise ValueError(f"{key} missing columns: {absent}")

    issues = {
        "duplicate_lead_ids": int(leads.mql_id.duplicated().sum()),
        "duplicate_win_lead_ids": int(wins.mql_id.duplicated().sum()),
        "duplicate_win_seller_ids": int(wins.seller_id.duplicated().sum()),
        "duplicate_order_ids": int(orders.order_id.duplicated().sum()),
        "duplicate_item_keys": int(items.duplicated(["order_id", "order_item_id"]).sum()),
        "win_ids_not_in_leads": int((~wins.mql_id.isin(leads.mql_id)).sum()),
        "items_without_orders": int((~items.order_id.isin(orders.order_id)).sum()),
        "negative_item_prices": int((items.price < 0).sum()),
    }
    fatal = [k for k in issues if issues[k] and k not in {"items_without_orders"}]
    if fatal:
        raise ValueError(f"Source integrity failed: {[(k, issues[k]) for k in fatal]}")

    leads["first_contact_date"] = pd.to_datetime(leads.first_contact_date, errors="coerce")
    wins["won_date"] = pd.to_datetime(wins.won_date, errors="coerce")
    orders["order_purchase_timestamp"] = pd.to_datetime(orders.order_purchase_timestamp, errors="coerce")
    if leads.first_contact_date.isna().any() or wins.won_date.isna().any() or orders.order_purchase_timestamp.isna().any():
        raise ValueError("Source has unparseable core dates")

    leads["origin"] = leads.origin.fillna("missing").astype(str)
    leads.loc[~leads.origin.isin(CHANNELS), "origin"] = "other"
    orders["order_status"] = orders.order_status.astype(str)
    items["price"] = pd.to_numeric(items.price, errors="coerce")
    if items.price.isna().any():
        raise ValueError("Unparseable item price")
    chronology = wins[["mql_id", "won_date"]].merge(
        leads[["mql_id", "first_contact_date"]], on="mql_id", validate="one_to_one"
    )
    issues["win_before_first_contact"] = int((
        chronology.won_date < chronology.first_contact_date
    ).sum())

    hashes = {key: hashlib.sha256((raw_dir / filename).read_bytes()).hexdigest() for key, filename in RAW_FILES.items()}
    counts = {key: len(table) for key, table in tables.items()}
    return tables, {"source_rows": counts, "sha256": hashes, "integrity": issues,
                    "order_cutoff": str(ORDER_CUTOFF), "win_observation_end": str(WIN_OBSERVATION_END)}


def build_mart(tables: dict[str, pd.DataFrame], warehouse_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    warehouse_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(warehouse_path) as connection:
        for key in RAW_FILES:
            tables[key].to_sql(key, connection, if_exists="replace", index=False, chunksize=10000)
        connection.executescript("""
            CREATE UNIQUE INDEX IF NOT EXISTS ix_lead_id ON leads(mql_id);
            CREATE UNIQUE INDEX IF NOT EXISTS ix_win_mql ON wins(mql_id);
            CREATE UNIQUE INDEX IF NOT EXISTS ix_win_seller ON wins(seller_id);
            CREATE UNIQUE INDEX IF NOT EXISTS ix_order_id ON orders(order_id);
            CREATE INDEX IF NOT EXISTS ix_item_order ON items(order_id);
            CREATE INDEX IF NOT EXISTS ix_item_seller ON items(seller_id);
        """)
        # One row per qualified lead, including leads that did not close within 90 days.
        leads = pd.read_sql_query("""
            SELECT l.mql_id, l.origin, l.first_contact_date, w.seller_id, w.won_date,
                   CAST(julianday(w.won_date) - julianday(l.first_contact_date) AS REAL) AS days_to_win
            FROM leads l LEFT JOIN wins w ON w.mql_id = l.mql_id
        """, connection, parse_dates=["first_contact_date", "won_date"])
        # Price is at order-item grain. Joining seller directly to orders without the
        # items table would silently attribute multi-seller orders to the wrong seller.
        item_orders = pd.read_sql_query("""
            SELECT i.seller_id, i.order_id, i.order_item_id, i.price,
                   o.order_purchase_timestamp AS purchase_date
            FROM items i INNER JOIN orders o ON o.order_id = i.order_id
            WHERE o.order_status = 'delivered'
              AND o.order_purchase_timestamp <= '2018-08-31 23:59:59'
        """, connection, parse_dates=["purchase_date"])
    return leads, item_orders


def compute_metrics(leads: pd.DataFrame, item_orders: pd.DataFrame, audit: dict) -> tuple[dict, dict[str, pd.DataFrame]]:
    lead_eligible = leads[leads.first_contact_date <= WIN_OBSERVATION_END - pd.Timedelta(days=90)].copy()
    lead_eligible["converted_90d"] = (
        lead_eligible.won_date.notna()
        & lead_eligible.days_to_win.between(0, 90, inclusive="both")
        & (lead_eligible.won_date <= WIN_OBSERVATION_END)
    )
    lead_metrics = lead_eligible.groupby("origin", as_index=False).agg(
        eligible_leads=("mql_id", "size"), wins_90d=("converted_90d", "sum")
    )
    lead_metrics["conversion_90d"] = lead_metrics.wins_90d / lead_metrics.eligible_leads
    intervals = [wilson_interval(int(row.wins_90d), int(row.eligible_leads)) for row in lead_metrics.itertuples()]
    lead_metrics["ci_low"] = [x[0] for x in intervals]
    lead_metrics["ci_high"] = [x[1] for x in intervals]

    # Keep the SAME lead outcome the scenario uses: a win within 90 days of
    # first contact. Late wins have different funnel eligibility; combining
    # them with the conversion numerator would misalign the planning model.
    matured_outside_90d_win_window = int((
        leads.seller_id.notna()
        & (leads.won_date <= ORDER_CUTOFF - pd.Timedelta(days=90))
        & ~leads.days_to_win.between(0, 90, inclusive="both")
    ).sum())
    # Only wins on or before June 2 can have a fully observable 90-day selling period.
    seller_matured = leads[
        leads.seller_id.notna() & (leads.won_date <= ORDER_CUTOFF - pd.Timedelta(days=90))
        & leads.days_to_win.between(0, 90, inclusive="both")
    ][["mql_id", "origin", "seller_id", "won_date"]].copy()
    assert seller_matured.seller_id.is_unique

    item_wins = item_orders.merge(seller_matured[["seller_id", "won_date"]], on="seller_id", how="inner")
    before_win = item_wins[item_wins.purchase_date < item_wins.won_date]
    in_90d = item_wins[
        (item_wins.purchase_date >= item_wins.won_date)
        & (item_wins.purchase_date < item_wins.won_date + pd.Timedelta(days=90))
    ].copy()
    seller_sales = in_90d.groupby("seller_id", as_index=False).agg(
        gmv_90d_brl=("price", "sum"), order_items_90d=("order_item_id", "size"),
        orders_90d=("order_id", "nunique"), first_order=("purchase_date", "min")
    )
    seller_matured = seller_matured.merge(seller_sales, on="seller_id", how="left", validate="one_to_one")
    seller_matured[["gmv_90d_brl", "order_items_90d", "orders_90d"]] = seller_matured[
        ["gmv_90d_brl", "order_items_90d", "orders_90d"]
    ].fillna(0)
    seller_matured["observed_sale_90d"] = seller_matured.orders_90d > 0
    seller_matured["days_first_sale"] = (
        seller_matured.first_order - seller_matured.won_date
    ).dt.total_seconds() / 86400

    seller_metrics = seller_matured.groupby("origin", as_index=False).agg(
        matured_wins=("seller_id", "size"), wins_with_recorded_sales=("observed_sale_90d", "sum"),
        observed_gmv_90d_brl=("gmv_90d_brl", "sum"), mean_gmv_per_win_brl=("gmv_90d_brl", "mean"),
        median_gmv_per_win_brl=("gmv_90d_brl", "median")
    )
    seller_metrics["observed_sale_share"] = seller_metrics.wins_with_recorded_sales / seller_metrics.matured_wins
    ci = [bootstrap_mean(seller_matured.loc[seller_matured.origin == row.origin, "gmv_90d_brl"].to_numpy(),
                         seed=20260916 + i) for i, row in enumerate(seller_metrics.itertuples())]
    seller_metrics["gmv_ci_low_brl"] = [x[0] for x in ci]
    seller_metrics["gmv_ci_high_brl"] = [x[1] for x in ci]

    orders = item_orders.groupby(["seller_id", pd.Grouper(key="purchase_date", freq="MS")], as_index=False).agg(
        item_gmv_brl=("price", "sum"), distinct_orders=("order_id", "nunique")
    )
    orders["month"] = orders.purchase_date.dt.strftime("%Y-%m")
    # Channel-specific order GMV after win, from matched closed-deal sellers only.
    monthly_join = item_orders.merge(leads.loc[leads.seller_id.notna(), ["seller_id", "origin", "won_date"]],
                                     on="seller_id", how="inner")
    monthly_join = monthly_join[monthly_join.purchase_date >= monthly_join.won_date].copy()
    monthly_join["month"] = monthly_join.purchase_date.dt.strftime("%Y-%m")
    monthly_channel = monthly_join.groupby(["month", "origin"], as_index=False).agg(
        observed_gmv_brl=("price", "sum"), item_rows=("price", "size")
    )

    total_gmv = round(float(seller_matured.gmv_90d_brl.sum()), 2)
    overview = {
        "eligible_leads_90d": int(len(lead_eligible)),
        "won_leads_90d": int(lead_eligible.converted_90d.sum()),
        "overall_conversion_90d": float(lead_eligible.converted_90d.mean()),
        "total_closed_deals": int(leads.seller_id.notna().sum()),
        "matured_seller_wins": int(len(seller_matured)),
        "matured_deals_not_won_within_90d": matured_outside_90d_win_window,
        "wins_with_recorded_sale_90d": int(seller_matured.observed_sale_90d.sum()),
        "recorded_seller_gmv_90d_brl": total_gmv,
        "overall_mean_gmv_per_matured_win_brl": float(seller_matured.gmv_90d_brl.mean()),
        "orders_after_extract_cutoff": audit["orders_after_extract_cutoff"],
        "pre_win_item_rows_excluded": int(len(before_win)),
        "item_rows_missing_order_excluded": audit["integrity"]["items_without_orders"],
        "delivered_item_rows_through_cutoff": int(len(item_orders)),
        "matched_deal_sellers_through_cutoff": int(item_orders.loc[
            item_orders.seller_id.isin(leads.seller_id.dropna()), "seller_id"
        ].nunique()),
    }
    return overview, {
        "lead_channel_metrics": lead_metrics, "seller_channel_metrics": seller_metrics,
        "seller_90d": seller_matured, "monthly_channel_gmv": monthly_channel,
        "all_seller_monthly_gmv": orders,
    }


def export(root: Path, audit: dict, overview: dict, frames: dict[str, pd.DataFrame]) -> None:
    output = root / "outputs"
    output.mkdir(exist_ok=True)
    (root / "dashboard").mkdir(exist_ok=True)
    for name, frame in frames.items():
        frame.to_csv(output / f"{name}.csv", index=False, float_format="%.5f")
    (output / "audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    (output / "overview.json").write_text(json.dumps(overview, indent=2), encoding="utf-8")
    dashboard_data = {
        "overview": overview, "audit": {k: audit[k] for k in ("source_rows", "order_cutoff", "win_observation_end")},
        "leads": frames["lead_channel_metrics"].round(4).to_dict(orient="records"),
        "sellers": frames["seller_channel_metrics"].round(2).to_dict(orient="records"),
        "monthly": frames["monthly_channel_gmv"].round(2).to_dict(orient="records"),
    }
    # Static, self-contained dashboard works when opened from disk (no file:// fetch).
    (root / "dashboard" / "data.js").write_text(
        "window.OLIST_DATA = " + json.dumps(dashboard_data, separators=(",", ":")) + ";\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    root = args.root.resolve()
    tables, audit = audit_and_load(root / "data" / "raw")
    audit["orders_after_extract_cutoff"] = int((
        tables["orders"].order_purchase_timestamp > ORDER_CUTOFF
    ).sum())
    leads, item_orders = build_mart(tables, root / "data" / "warehouse" / "olist.sqlite")
    overview, frames = compute_metrics(leads, item_orders, audit)
    export(root, audit, overview, frames)
    print(json.dumps(overview, indent=2))


if __name__ == "__main__":
    main()
