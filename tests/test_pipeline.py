import pandas as pd
import tempfile
import unittest
from pathlib import Path

from growth.pipeline import ORDER_CUTOFF, bootstrap_mean, build_mart, compute_metrics, wilson_interval


def test_wilson_small_samples_and_zeros():
    low, high = wilson_interval(0, 10)
    assert low == 0 and 0 < high < 0.5
    assert wilson_interval(0, 0) == (0, 0)
    assert abs(wilson_interval(100, 100)[1] - 1) < 1e-10


def test_bootstrap_is_deterministic():
    values = __import__("numpy").array([0, 0, 100, 200])
    assert bootstrap_mean(values) == bootstrap_mean(values)


def test_lead_and_seller_grains_windows_and_multi_seller_orders(tmp_path):
    tables = {
        "leads": pd.DataFrame({
            "mql_id": ["L1", "L2", "L3", "L4"],
            "first_contact_date": pd.to_datetime(["2018-02-01", "2018-02-01", "2018-02-01", "2018-05-01"]),
            "origin": ["paid_search", "paid_search", "social", "social"],
        }),
        "wins": pd.DataFrame({
            "mql_id": ["L1", "L3", "L4"], "seller_id": ["S1", "S3", "S4"],
            "won_date": pd.to_datetime(["2018-02-20", "2018-06-03", "2018-05-20"]),
        }),
        "items": pd.DataFrame({
            "order_id": ["O1", "O1", "O2", "O3", "O4", "O5"],
            "order_item_id": [1, 2, 1, 1, 1, 1],
            "seller_id": ["S1", "S9", "S1", "S3", "S1", "S1"],
            "price": [100, 200, 25, 90, 50, 1000],
        }),
        "orders": pd.DataFrame({
            "order_id": ["O1", "O2", "O3", "O4", "O5"],
            "order_status": ["delivered", "delivered", "delivered", "delivered", "canceled"],
            "order_purchase_timestamp": pd.to_datetime([
                "2018-03-01", "2018-02-01", "2018-07-01", "2018-09-01", "2018-03-01",
            ]),
        }),
    }
    leads, item_orders = build_mart(tables, tmp_path / "db.sqlite")
    audit = {"integrity": {"items_without_orders": 0}, "orders_after_extract_cutoff": 1}
    overview, frames = compute_metrics(leads, item_orders, audit)
    paid = frames["lead_channel_metrics"].set_index("origin").loc["paid_search"]
    assert paid.eligible_leads == 2 and paid.wins_90d == 1
    assert frames["seller_90d"].seller_id.tolist() == ["S1", "S4"]
    s1 = frames["seller_90d"].set_index("seller_id").loc["S1"]
    assert s1.gmv_90d_brl == 100  # O1's other seller, pre-win O2, late O4, canceled O5 excluded
    assert s1.orders_90d == 1
    assert overview["recorded_seller_gmv_90d_brl"] == 100
    assert overview["orders_after_extract_cutoff"] == 1
    assert overview["pre_win_item_rows_excluded"] == 1
    assert ORDER_CUTOFF.month == 8


def test_win_90_days_later_does_not_count_as_conversion():
    # The fixed 90-day definition is based on exact dates, not month labels.
    leads = pd.DataFrame({
        "mql_id": ["L1"], "origin": ["direct_traffic"],
        "first_contact_date": pd.to_datetime(["2018-01-01"]), "seller_id": ["S1"],
        "won_date": pd.to_datetime(["2018-04-05"]), "days_to_win": [94.0],
    })
    item_orders = pd.DataFrame({"seller_id": ["S1"], "order_id": ["O1"], "order_item_id": [1],
                                "price": [10], "purchase_date": pd.to_datetime(["2018-04-10"])})
    audit = {"integrity": {"items_without_orders": 0}, "orders_after_extract_cutoff": 0}
    _, frames = compute_metrics(leads, item_orders, audit)
    assert frames["lead_channel_metrics"].wins_90d.iloc[0] == 0


class PipelineTests(unittest.TestCase):
    def test_intervals(self):
        test_wilson_small_samples_and_zeros()
        test_bootstrap_is_deterministic()

    def test_source_grain_and_boundaries(self):
        with tempfile.TemporaryDirectory() as temporary:
            test_lead_and_seller_grains_windows_and_multi_seller_orders(Path(temporary))

    def test_fixed_lead_window(self):
        test_win_90_days_later_does_not_count_as_conversion()
