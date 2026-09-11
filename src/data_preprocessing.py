"""
data_preprocessing.py
=====================
Phase 1 — Data Cleaning for the Nassau Candy Distributor Shipping Analysis.

Responsibilities:
    1. Schema validation
    2. Missing value analysis and handling
    3. Duplicate removal
    4. Data-type correction
    5. Date parsing (DD-MM-YYYY)
    6. Invalid shipment removal (negative / zero lead times)
    7. Categorical value standardisation
    8. Product-name inconsistency fix
    9. Save cleaned dataset to ``data/processed/cleaned_data.csv``

Usage (standalone):
    python src/data_preprocessing.py

Usage (as module):
    from src.data_preprocessing import DataPreprocessor
    cleaner = DataPreprocessor()
    df_clean = cleaner.run()

Author: Nassau Candy Analytics Team
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# Allow imports when running as a standalone script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils import (
    CLEANED_DATA_FILE,
    RAW_DATA_FILE,
    US_STATES,
    get_logger,
    save_data,
)

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

#: Expected columns and their target dtypes after cleaning
EXPECTED_SCHEMA: Dict[str, str] = {
    "Row ID":         "int64",
    "Order ID":       "object",
    "Order Date":     "datetime64[ns]",
    "Ship Date":      "datetime64[ns]",
    "Ship Mode":      "object",
    "Customer ID":    "object",
    "Country/Region": "object",
    "City":           "object",
    "State/Province": "object",
    "Postal Code":    "object",
    "Division":       "object",
    "Region":         "object",
    "Product ID":     "object",
    "Product Name":   "object",
    "Sales":          "float64",
    "Units":          "int64",
    "Gross Profit":   "float64",
    "Cost":           "float64",
}

#: Date columns to parse (raw format: DD-MM-YYYY)
DATE_COLUMNS: List[str] = ["Order Date", "Ship Date"]

#: Product-name corrections: raw value → canonical value
PRODUCT_NAME_CORRECTIONS: Dict[str, str] = {
    "Wonka Bar -Scrumdiddlyumptious": "Wonka Bar - Scrumdiddlyumptious",
}

#: Valid ship modes (case-insensitive match; stored in Title Case)
VALID_SHIP_MODES: List[str] = [
    "Standard Class",
    "Second Class",
    "First Class",
    "Same Day",
]

#: Valid regions
VALID_REGIONS: List[str] = ["Gulf", "Interior", "Pacific", "Atlantic"]

#: Valid divisions
VALID_DIVISIONS: List[str] = ["Chocolate", "Sugar", "Other"]


# ─────────────────────────────────────────────────────────────────────────────
# PREPROCESSOR CLASS
# ─────────────────────────────────────────────────────────────────────────────

class DataPreprocessor:
    """
    End-to-end data cleaning pipeline for the Nassau Candy shipment dataset.

    Attributes:
        raw_path:    Path to the raw CSV file.
        output_path: Path where the cleaned CSV will be saved.
        logger:      Module-level logger instance.

    Example:
        >>> cleaner = DataPreprocessor()
        >>> df_clean = cleaner.run()
        >>> print(df_clean.shape)
    """

    def __init__(
        self,
        raw_path: Path = RAW_DATA_FILE,
        output_path: Path = CLEANED_DATA_FILE,
    ) -> None:
        self.raw_path = raw_path
        self.output_path = output_path
        self.logger = get_logger(self.__class__.__name__)
        self._report: Dict[str, object] = {}  # collects cleaning stats

    # ── Public API ────────────────────────────────────────────────────────────

    def run(self) -> pd.DataFrame:
        """
        Execute the full cleaning pipeline and return the cleaned DataFrame.

        Steps:
            1. Load raw CSV
            2. Validate schema
            3. Parse dates
            4. Cast numeric columns
            5. Handle missing values
            6. Remove duplicates
            7. Standardise categoricals
            8. Fix product-name inconsistencies
            9. Remove invalid lead times (negative / zero)
            10. Save cleaned data

        Returns:
            Cleaned :class:`pandas.DataFrame`.
        """
        self.logger.info("=" * 60)
        self.logger.info("PHASE 1 — Data Cleaning Pipeline Started")
        self.logger.info("=" * 60)

        df = self._load()
        df = self._validate_schema(df)
        df = self._parse_dates(df)
        df = self._cast_numerics(df)
        df = self._handle_missing(df)
        df = self._remove_duplicates(df)
        df = self._standardise_categoricals(df)
        df = self._fix_product_names(df)
        df = self._remove_invalid_lead_times(df)
        df = self._final_dtype_enforcement(df)

        self._print_report(df)
        save_data(df, self.output_path)

        self.logger.info("=" * 60)
        self.logger.info("Cleaning complete. Output: %s", self.output_path)
        self.logger.info("=" * 60)
        return df

    def get_report(self) -> Dict[str, object]:
        """Return the cleaning summary report dictionary."""
        return self._report

    # ── Private Pipeline Steps ────────────────────────────────────────────────

    def _load(self) -> pd.DataFrame:
        """Load the raw CSV, keeping all columns as strings initially."""
        self.logger.info("Loading raw data from: %s", self.raw_path)
        if not self.raw_path.exists():
            raise FileNotFoundError(f"Raw data file not found: {self.raw_path}")

        df = pd.read_csv(self.raw_path, dtype=str, keep_default_na=True)
        self._report["raw_rows"] = len(df)
        self._report["raw_cols"] = len(df.columns)
        self.logger.info("Raw data shape: %d rows × %d columns", *df.shape)
        return df

    def _validate_schema(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Validate that all expected columns are present.

        Args:
            df: Raw DataFrame.

        Returns:
            DataFrame (unchanged).

        Raises:
            ValueError: If any expected column is missing.
        """
        self.logger.info("Validating schema...")
        missing_cols = [c for c in EXPECTED_SCHEMA if c not in df.columns]
        extra_cols = [c for c in df.columns if c not in EXPECTED_SCHEMA]

        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")
        if extra_cols:
            self.logger.warning("Unexpected extra columns (will be kept): %s", extra_cols)

        self._report["schema_ok"] = True
        self.logger.info("Schema validation passed. All %d expected columns present.", len(EXPECTED_SCHEMA))
        return df

    def _parse_dates(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Parse date columns from DD-MM-YYYY string format.

        Args:
            df: DataFrame with raw string date columns.

        Returns:
            DataFrame with parsed datetime columns.
        """
        self.logger.info("Parsing date columns: %s", DATE_COLUMNS)
        for col in DATE_COLUMNS:
            before_nulls = df[col].isna().sum()
            df[col] = pd.to_datetime(df[col], format="%d-%m-%Y", errors="coerce")
            after_nulls = df[col].isna().sum()
            new_nulls = after_nulls - before_nulls
            if new_nulls > 0:
                self.logger.warning(
                    "Column '%s': %d values could not be parsed → NaT", col, new_nulls
                )
        return df

    def _cast_numerics(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Cast numeric columns to their correct types.

        Args:
            df: DataFrame with string-typed numeric columns.

        Returns:
            DataFrame with correctly typed numeric columns.
        """
        self.logger.info("Casting numeric columns...")
        numeric_float_cols = ["Sales", "Gross Profit", "Cost"]
        numeric_int_cols = ["Row ID", "Units"]

        for col in numeric_float_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        for col in numeric_int_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # Postal Code → string (preserve leading zeros)
        df["Postal Code"] = df["Postal Code"].astype(str).str.strip().str.zfill(5)

        return df

    def _handle_missing(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Analyse and handle missing values.

        Strategy:
            - Numeric columns: fill with column median.
            - Categorical columns: fill with ``"Unknown"``.
            - Date columns: rows with missing dates are dropped.

        Args:
            df: DataFrame after type casting.

        Returns:
            DataFrame with missing values handled.
        """
        self.logger.info("Analysing missing values...")
        missing_summary = df.isna().sum()
        missing_pct = (df.isna().sum() / len(df) * 100).round(2)
        missing_df = pd.DataFrame({
            "missing_count": missing_summary,
            "missing_pct": missing_pct,
        }).query("missing_count > 0")

        if missing_df.empty:
            self.logger.info("No missing values detected.")
        else:
            self.logger.warning("Missing values found:\n%s", missing_df.to_string())

        self._report["missing_before"] = missing_df.to_dict()

        # Drop rows where both dates are missing (unrecoverable)
        rows_before = len(df)
        df = df.dropna(subset=["Order Date", "Ship Date"])
        dropped_date = rows_before - len(df)
        if dropped_date:
            self.logger.warning("Dropped %d rows with missing dates.", dropped_date)

        # Fill numeric columns with median
        for col in ["Sales", "Gross Profit", "Cost"]:
            if df[col].isna().any():
                median_val = df[col].median()
                df[col] = df[col].fillna(median_val)
                self.logger.info("Filled missing '%s' with median %.4f", col, median_val)

        # Fill Units with median (integer)
        if df["Units"].isna().any():
            median_units = int(df["Units"].median())
            df["Units"] = df["Units"].fillna(median_units)

        # Fill categorical columns
        cat_cols = ["Ship Mode", "Country/Region", "City", "State/Province",
                    "Division", "Region", "Product Name", "Customer ID", "Product ID"]
        for col in cat_cols:
            if df[col].isna().any():
                df[col] = df[col].fillna("Unknown")
                self.logger.info("Filled missing '%s' with 'Unknown'", col)

        self._report["rows_dropped_missing_dates"] = dropped_date
        return df

    def _remove_duplicates(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Remove fully duplicated rows.

        Args:
            df: DataFrame.

        Returns:
            De-duplicated DataFrame.
        """
        self.logger.info("Removing duplicates...")
        rows_before = len(df)
        df = df.drop_duplicates()
        removed = rows_before - len(df)
        self._report["duplicates_removed"] = removed
        self.logger.info("Removed %d duplicate row(s). Rows remaining: %d", removed, len(df))
        return df

    def _standardise_categoricals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Standardise categorical column values to Title Case and strip whitespace.

        Args:
            df: DataFrame.

        Returns:
            DataFrame with standardised categoricals.
        """
        self.logger.info("Standardising categorical values...")
        str_cols = [
            "Ship Mode", "Country/Region", "City", "State/Province",
            "Division", "Region", "Product Name",
        ]
        for col in str_cols:
            df[col] = df[col].astype(str).str.strip()

        # Ship Mode: validate against allowed values
        invalid_modes = df.loc[~df["Ship Mode"].isin(VALID_SHIP_MODES), "Ship Mode"].unique()
        if len(invalid_modes):
            self.logger.warning("Unknown Ship Modes found (will be kept): %s", invalid_modes)

        # Region: validate
        invalid_regions = df.loc[~df["Region"].isin(VALID_REGIONS), "Region"].unique()
        if len(invalid_regions):
            self.logger.warning("Unknown Regions found: %s", invalid_regions)

        # Division: validate
        invalid_divs = df.loc[~df["Division"].isin(VALID_DIVISIONS), "Division"].unique()
        if len(invalid_divs):
            self.logger.warning("Unknown Divisions found: %s", invalid_divs)

        return df

    def _fix_product_names(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Correct known product-name inconsistencies in the raw data.

        Args:
            df: DataFrame.

        Returns:
            DataFrame with corrected product names.
        """
        self.logger.info("Fixing product-name inconsistencies...")
        fixes_applied = 0
        for wrong, correct in PRODUCT_NAME_CORRECTIONS.items():
            mask = df["Product Name"] == wrong
            n = mask.sum()
            if n > 0:
                df.loc[mask, "Product Name"] = correct
                self.logger.info("Fixed '%s' -> '%s' (%d rows)", wrong, correct, n)
                fixes_applied += n

        self._report["product_name_fixes"] = fixes_applied
        if fixes_applied == 0:
            self.logger.info("No product-name inconsistencies found.")
        return df

    def _remove_invalid_lead_times(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Remove rows where Ship Date is before or equal to Order Date
        (i.e., lead time <= 0 days).

        Args:
            df: DataFrame with parsed date columns.

        Returns:
            DataFrame with invalid lead-time rows removed.
        """
        self.logger.info("Removing invalid lead times (Ship Date <= Order Date)...")
        rows_before = len(df)
        lead_time = (df["Ship Date"] - df["Order Date"]).dt.days
        df = df[lead_time > 0].copy()
        removed = rows_before - len(df)
        self._report["invalid_lead_times_removed"] = removed
        self.logger.info(
            "Removed %d row(s) with non-positive lead time. Rows remaining: %d",
            removed, len(df)
        )
        return df

    def _final_dtype_enforcement(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Final pass to enforce correct dtypes on key columns.

        Args:
            df: Nearly-cleaned DataFrame.

        Returns:
            DataFrame with enforced dtypes.
        """
        self.logger.info("Enforcing final dtypes...")
        df["Row ID"] = df["Row ID"].astype("int64", errors="ignore")
        df["Units"] = df["Units"].astype("int64", errors="ignore")
        df["Sales"] = df["Sales"].astype("float64")
        df["Gross Profit"] = df["Gross Profit"].astype("float64")
        df["Cost"] = df["Cost"].astype("float64")
        return df

    def _print_report(self, df: pd.DataFrame) -> None:
        """Log a structured cleaning report to the console."""
        self.logger.info("-" * 60)
        self.logger.info("CLEANING REPORT")
        self.logger.info("-" * 60)
        self.logger.info("  Raw rows:                    %d", self._report.get("raw_rows", "?"))
        self.logger.info("  Duplicates removed:          %d", self._report.get("duplicates_removed", 0))
        self.logger.info("  Rows dropped (bad dates):    %d", self._report.get("rows_dropped_missing_dates", 0))
        self.logger.info("  Invalid lead times removed:  %d", self._report.get("invalid_lead_times_removed", 0))
        self.logger.info("  Product name fixes applied:  %d", self._report.get("product_name_fixes", 0))
        self.logger.info("  Final clean rows:            %d", len(df))
        self.logger.info("  Final columns:               %d", len(df.columns))
        self.logger.info("-" * 60)


# ─────────────────────────────────────────────────────────────────────────────
# STANDALONE ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    """Run the data preprocessing pipeline as a standalone script."""
    from src.utils import ensure_dirs
    ensure_dirs()
    preprocessor = DataPreprocessor()
    df = preprocessor.run()
    print("\nSample of cleaned data:")
    print(df.head(3).to_string())
    print(f"\nData types:\n{df.dtypes}")


if __name__ == "__main__":
    main()
