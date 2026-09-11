"""
tests/test_analytics.py
=======================
Automated test suite verifying the core data and analytics pipeline for Nassau Candy.
"""

from __future__ import annotations

import unittest
from pathlib import Path
import pandas as pd
import numpy as np

from src.utils import (
    FEATURED_DATA_FILE,
    CLEANED_DATA_FILE,
    compute_efficiency_score,
    ensure_dirs,
)
from src.kpi import KPICalculator
from src.route_analysis import RouteAnalyzer
from src.ship_mode_analysis import ShipModeAnalyzer
from src.geographic_analysis import GeoAnalyzer


class TestAnalyticsPipeline(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        ensure_dirs()
        cls.df = pd.read_csv(FEATURED_DATA_FILE, parse_dates=["Order Date", "Ship Date"])

    def test_featured_dataset_loaded(self):
        self.assertFalse(self.df.empty, "Featured dataset should not be empty")
        self.assertIn("Shipping Lead Time", self.df.columns)
        self.assertIn("Delay Flag", self.df.columns)
        self.assertIn("Route Efficiency Score", self.df.columns)

    def test_efficiency_score_bounds(self):
        lead_times = pd.Series([1, 3, 5, 7])
        delay_rates = pd.Series([0.0, 0.2, 0.5, 0.8])
        scores = compute_efficiency_score(lead_times, delay_rates)
        self.assertTrue((scores >= 0).all() and (scores <= 1.01).all(), "Scores should be between 0 and 1")

    def test_kpi_calculator_summary(self):
        calc = KPICalculator(self.df)
        summary = calc.get_summary()
        self.assertGreater(summary["total_orders"], 0)
        self.assertGreater(summary["total_sales"], 0)
        self.assertGreater(summary["avg_lead_time"], 0)
        self.assertLessEqual(summary["delay_rate_pct"], 100.0)

    def test_route_analyzer_top_and_worst(self):
        analyzer = RouteAnalyzer(self.df)
        top = analyzer.top_routes(5)
        worst = analyzer.worst_routes(5)
        self.assertEqual(len(top), 5)
        self.assertEqual(len(worst), 5)
        self.assertGreaterEqual(
            top["avg_efficiency_score"].iloc[0],
            worst["avg_efficiency_score"].iloc[0],
            "Top route should have higher or equal efficiency score than worst route"
        )

    def test_ship_mode_analyzer(self):
        analyzer = ShipModeAnalyzer(self.df)
        summary = analyzer.mode_summary()
        self.assertFalse(summary.empty)
        self.assertIn("Ship Mode", summary.columns)
        self.assertIn("avg_lead_time", summary.columns)

    def test_geo_analyzer(self):
        analyzer = GeoAnalyzer(self.df)
        state_perf = analyzer.state_performance()
        self.assertFalse(state_perf.empty)
        self.assertIn("state", state_perf.columns)
        self.assertIn("avg_lead_time", state_perf.columns)

    def test_filter_engine(self):
        from src.filter_engine import compute_quick_stats, get_active_filter_count
        stats = compute_quick_stats(self.df, self.df)
        self.assertEqual(stats["filtered_records"], len(self.df))
        self.assertAlmostEqual(stats["pct_retained"], 100.0)
        self.assertGreater(stats["total_sales"], 0)

        # Active filter count check
        count_zero = get_active_filter_count({}, self.df)
        self.assertEqual(count_zero, 0)
        count_filtered = get_active_filter_count({"delay_only": True}, self.df)
        self.assertEqual(count_filtered, 1)

    def test_admin_assistant_health(self):
        from src.admin_assistant import analyze_dataset_health
        health = analyze_dataset_health(self.df)
        self.assertIn("health_score", health)
        self.assertGreaterEqual(health["health_score"], 50)
        self.assertIn("summary", health)
        self.assertEqual(health["summary"]["total_records"], len(self.df))


if __name__ == "__main__":
    unittest.main()
