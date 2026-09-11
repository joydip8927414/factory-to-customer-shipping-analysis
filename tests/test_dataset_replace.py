"""
tests/test_dataset_replace.py
==============================
Unit tests verifying dataset upload, buffer seek handling, and complete
pipeline recalculation for the 10,194-record Nassau Candy dataset.
"""

import io
import unittest
from pathlib import Path
import pandas as pd

from src.admin_manager import recalculate_and_propagate
from src.kpi import KPICalculator
from src.utils import (
    CLEANED_DATA_FILE,
    FEATURED_DATA_FILE,
    RAW_DATA_FILE,
    ensure_dirs,
)


class TestDatasetReplace(unittest.TestCase):

    def setUp(self):
        ensure_dirs()
        self.raw_path = RAW_DATA_FILE
        self.assertTrue(self.raw_path.exists(), f"Raw file missing at {self.raw_path}")
        self.raw_df = pd.read_csv(self.raw_path)
        self.assertEqual(len(self.raw_df), 10194, "Raw dataset should contain exactly 10,194 rows")

    def test_recalculate_and_propagate_10194_records(self):
        """Verify full replacement with the 10,194 record sheet works cleanly."""
        success, msg = recalculate_and_propagate(
            self.raw_df.copy(),
            user="TestAdmin",
            reason="Unit Test Full Replace",
        )
        self.assertTrue(success, f"Recalculate failed: {msg}")
        self.assertIn("10,194", msg)

        # Verify featured_data.csv
        feat_df = pd.read_csv(FEATURED_DATA_FILE, encoding="utf-8")
        self.assertEqual(len(feat_df), 10194)

        # Verify key engineered columns exist
        expected_cols = [
            "Factory",
            "Factory Latitude",
            "Factory Longitude",
            "Shipping Lead Time",
            "Delay Flag",
            "Factory → State Route",
            "Route Efficiency Score",
            "Shipment Year",
            "Shipment Month",
        ]
        for col in expected_cols:
            self.assertIn(col, feat_df.columns, f"Missing expected column: {col}")

        # Verify Wonka Bar product fix (zero Unknown Factory)
        factory_counts = feat_df["Factory"].value_counts()
        self.assertNotIn("Unknown Factory", factory_counts, "All products should map to valid factories")
        self.assertEqual(factory_counts.get("Lot's O' Nuts", 0), 5692)
        self.assertEqual(factory_counts.get("Wicked Choccy's", 0), 4152)

        # Verify cleaned_data.csv is synchronized
        clean_df = pd.read_csv(CLEANED_DATA_FILE, encoding="utf-8")
        self.assertEqual(len(clean_df), 10194)
        self.assertEqual(len(clean_df.columns), 18)

        # Verify KPI summary works seamlessly
        calc = KPICalculator(feat_df)
        summary = calc.get_summary()
        self.assertGreater(summary["total_orders"], 0)
        self.assertGreater(summary["total_sales"], 0)
        self.assertGreater(summary["avg_lead_time"], 0)

    def test_buffer_seek_simulation(self):
        """Simulate Streamlit file buffer depletion and verify seek(0) avoids EmptyDataError."""
        csv_bytes = self.raw_df.head(50).to_csv(index=False).encode("utf-8")
        buf = io.BytesIO(csv_bytes)

        # First read
        df1 = pd.read_csv(buf)
        self.assertEqual(len(df1), 50)

        # Second read without seek fails
        with self.assertRaises(Exception):
            pd.read_csv(buf)

        # Second read with seek succeeds
        buf.seek(0)
        df2 = pd.read_csv(buf)
        self.assertEqual(len(df2), 50)

    def test_dirty_numeric_sanitization(self):
        """Verify dirty strings (currency formatting, commas) in Sales/Cost/Units are sanitized."""
        dirty_df = self.raw_df.head(10).copy()
        dirty_df["Sales"] = ["$1,234.56", "$99.00", "500.25"] + ["$10.00"] * 7
        dirty_df["Units"] = ["1,000", "2,500", "10"] + ["5"] * 7

        success, msg = recalculate_and_propagate(
            dirty_df,
            user="TestAdmin",
            reason="Test Dirty Numeric Sanitization",
        )
        self.assertTrue(success, f"Failed on dirty data: {msg}")

        feat_df = pd.read_csv(FEATURED_DATA_FILE, encoding="utf-8")
        self.assertTrue(pd.api.types.is_float_dtype(feat_df["Sales"]))
        self.assertTrue(pd.api.types.is_integer_dtype(feat_df["Units"]))
        self.assertAlmostEqual(feat_df["Sales"].iloc[0], 1234.56)
        self.assertEqual(feat_df["Units"].iloc[0], 1000)


if __name__ == "__main__":
    unittest.main()
