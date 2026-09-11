"""
feature_engineering.py
======================
Phase 2 — Feature Engineering for the Nassau Candy Distributor Shipping Analysis.

Responsibilities:
    1. Map Product Name → Factory
    2. Add Factory latitude / longitude
    3. Compute Shipping Lead Time (days)
    4. Compute Delay Flag (lead time > median per ship mode)
    5. Build Route IDs: Factory → State, Factory → Region
    6. Add temporal features: Month, Year, Week, Day, Quarter
    7. Compute Route Efficiency Score
    8. Save featured dataset to ``data/processed/featured_data.csv``

Usage (standalone):
    python src/feature_engineering.py

Usage (as module):
    from src.feature_engineering import FeatureEngineer
    engineer = FeatureEngineer()
    df_feat = engineer.run()

Author: Nassau Candy Analytics Team
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils import (
    CLEANED_DATA_FILE,
    FACTORY_COORDINATES,
    FEATURED_DATA_FILE,
    PRODUCT_FACTORY_MAP,
    get_logger,
    load_data,
    save_data,
    compute_efficiency_score,
)

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

#: Multiplier window for the delay flag:
#: shipment is "delayed" if lead time > DELAY_MULTIPLIER × median(lead_time | ship_mode)
DELAY_MULTIPLIER: float = 1.0  # i.e., above-median = delayed


# ─────────────────────────────────────────────────────────────────────────────
# FEATURE ENGINEER CLASS
# ─────────────────────────────────────────────────────────────────────────────

class FeatureEngineer:
    """
    Builds all derived features needed for downstream analysis and modelling.

    Attributes:
        input_path:  Path to the cleaned CSV file.
        output_path: Path where the featured CSV will be saved.
        logger:      Module-level logger.

    Example:
        >>> engineer = FeatureEngineer()
        >>> df_feat = engineer.run()
        >>> print(df_feat.columns.tolist())
    """

    def __init__(
        self,
        input_path: Path = CLEANED_DATA_FILE,
        output_path: Path = FEATURED_DATA_FILE,
    ) -> None:
        self.input_path = input_path
        self.output_path = output_path
        self.logger = get_logger(self.__class__.__name__)

    # ── Public API ────────────────────────────────────────────────────────────

    def run(self) -> pd.DataFrame:
        """
        Execute the full feature-engineering pipeline.

        Steps:
            1. Load cleaned data
            2. Add factory assignment
            3. Add factory coordinates
            4. Compute lead time
            5. Compute delay flag
            6. Build route identifiers
            7. Add temporal features
            8. Compute route efficiency scores
            9. Save

        Returns:
            Enriched :class:`pandas.DataFrame`.
        """
        self.logger.info("=" * 60)
        self.logger.info("PHASE 2 — Feature Engineering Pipeline Started")
        self.logger.info("=" * 60)

        df = load_data(self.input_path, date_cols=["Order Date", "Ship Date"])
        df = self._add_factory(df)
        df = self._add_factory_coordinates(df)
        df = self._compute_lead_time(df)
        df = self._compute_delay_flag(df)
        df = self._build_route_ids(df)
        df = self._add_temporal_features(df)
        df = self._compute_route_efficiency(df)

        save_data(df, self.output_path)
        self._log_feature_summary(df)

        self.logger.info("=" * 60)
        self.logger.info("Feature engineering complete. Output: %s", self.output_path)
        self.logger.info("=" * 60)
        return df

    # ── Private Pipeline Steps ────────────────────────────────────────────────

    def _add_factory(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Map each row's Product Name to its originating Factory.

        Unknown products are mapped to ``"Unknown Factory"``.

        Args:
            df: Cleaned DataFrame.

        Returns:
            DataFrame with a new ``Factory`` column.
        """
        self.logger.info("Mapping products to factories...")
        df["Factory"] = df["Product Name"].map(PRODUCT_FACTORY_MAP).fillna("Unknown Factory")
        unmapped = (df["Factory"] == "Unknown Factory").sum()
        if unmapped:
            self.logger.warning("%d rows could not be mapped to a factory.", unmapped)
        self.logger.info(
            "Factory distribution:\n%s",
            df["Factory"].value_counts().to_string()
        )
        return df

    def _add_factory_coordinates(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add Factory Latitude and Factory Longitude columns.

        Args:
            df: DataFrame with ``Factory`` column.

        Returns:
            DataFrame with ``Factory Latitude`` and ``Factory Longitude``.
        """
        self.logger.info("Adding factory coordinates...")
        df["Factory Latitude"] = df["Factory"].map(
            {name: coords[0] for name, coords in FACTORY_COORDINATES.items()}
        )
        df["Factory Longitude"] = df["Factory"].map(
            {name: coords[1] for name, coords in FACTORY_COORDINATES.items()}
        )
        return df

    def _compute_lead_time(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute shipping lead time in days (Ship Date − Order Date).

        Args:
            df: DataFrame with ``Order Date`` and ``Ship Date`` columns.

        Returns:
            DataFrame with a new ``Shipping Lead Time`` column.
        """
        self.logger.info("Computing Shipping Lead Time...")
        df["Shipping Lead Time"] = (df["Ship Date"] - df["Order Date"]).dt.days
        self.logger.info(
            "Lead time stats → min: %d, median: %.1f, max: %d",
            df["Shipping Lead Time"].min(),
            df["Shipping Lead Time"].median(),
            df["Shipping Lead Time"].max(),
        )
        return df

    def _compute_delay_flag(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Flag a shipment as delayed if its lead time exceeds the median lead
        time for its ship mode (data-driven, relative threshold).

        Args:
            df: DataFrame with ``Shipping Lead Time`` and ``Ship Mode``.

        Returns:
            DataFrame with a boolean ``Delay Flag`` column.
        """
        self.logger.info("Computing Delay Flag (above-median lead time per ship mode)...")
        mode_medians: Dict[str, float] = (
            df.groupby("Ship Mode")["Shipping Lead Time"].median().to_dict()
        )
        self.logger.info("Median lead times by ship mode: %s", mode_medians)

        df["Delay Flag"] = df.apply(
            lambda row: row["Shipping Lead Time"] > mode_medians.get(row["Ship Mode"], float("inf")),
            axis=1,
        )
        delay_pct = df["Delay Flag"].mean() * 100
        self.logger.info("Overall delay rate: %.1f%%", delay_pct)
        return df

    def _build_route_ids(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Build route identifier columns.

        Creates:
            - ``Factory → State Route``: e.g. ``"Lot's O' Nuts → Texas"``
            - ``Factory → Region Route``: e.g. ``"Lot's O' Nuts → Gulf"``
            - ``Route ID``: URL-safe slug for the state-level route

        Args:
            df: DataFrame with ``Factory``, ``State/Province``, ``Region``.

        Returns:
            DataFrame with route columns.
        """
        self.logger.info("Building route identifiers...")
        df["Factory → State Route"] = df["Factory"] + " → " + df["State/Province"]
        df["Factory → Region Route"] = df["Factory"] + " → " + df["Region"]
        df["Route ID"] = (
            df["Factory"].str.replace(r"[^A-Za-z0-9]", "_", regex=True)
            + "_to_"
            + df["State/Province"].str.replace(r"[^A-Za-z0-9]", "_", regex=True)
        )
        n_state_routes = df["Factory → State Route"].nunique()
        n_region_routes = df["Factory → Region Route"].nunique()
        self.logger.info(
            "Unique routes — State: %d, Region: %d", n_state_routes, n_region_routes
        )
        return df

    def _add_temporal_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Extract temporal features from the Ship Date.

        Created columns:
            - ``Shipment Year``
            - ``Shipment Month`` (1–12)
            - ``Shipment Month Name`` (Jan, Feb, ...)
            - ``Shipment Quarter`` (1–4)
            - ``Shipment Week`` (ISO week number)
            - ``Shipment Day`` (day of month)
            - ``Shipment Day of Week`` (Monday=0 … Sunday=6)

        Args:
            df: DataFrame with ``Ship Date``.

        Returns:
            DataFrame with temporal feature columns.
        """
        self.logger.info("Adding temporal features from Ship Date and Order Date...")
        sd = df["Ship Date"]
        od = df["Order Date"]
        df["Shipment Year"]        = sd.dt.year
        df["Shipment Month"]       = sd.dt.month
        df["Shipment Month Name"]  = sd.dt.strftime("%b")
        df["Shipment Quarter"]     = sd.dt.quarter
        df["Shipment Week"]        = sd.dt.isocalendar().week.astype(int)
        df["Shipment Day"]         = sd.dt.day
        df["Shipment Day of Week"] = sd.dt.dayofweek  # 0=Mon, 6=Sun

        # Order temporal features
        df["Order Year"]           = od.dt.year
        df["Order Month"]          = od.dt.month
        df["Order Month Name"]     = od.dt.strftime("%b")
        df["Order Day"]            = od.dt.day
        df["Order Day of Week"]    = od.dt.dayofweek
        return df

    def _compute_route_efficiency(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute per-route efficiency scores and merge back onto the main DataFrame.

        The Route Efficiency Score (0–1, higher = better) is computed as::

            efficiency = 1 - (0.6 × delay_rate + 0.4 × normalised_avg_lead_time)

        Both components are normalised across all state-level routes.

        Args:
            df: DataFrame with route and delay columns.

        Returns:
            DataFrame with ``Route Efficiency Score`` column.
        """
        self.logger.info("Computing Route Efficiency Scores...")
        route_col = "Factory → State Route"

        # Aggregate per route
        route_agg = df.groupby(route_col).agg(
            delay_rate=("Delay Flag", "mean"),
            avg_lead_time=("Shipping Lead Time", "mean"),
        ).reset_index()

        # Normalise both components to [0, 1]
        lt_min, lt_max = route_agg["avg_lead_time"].min(), route_agg["avg_lead_time"].max()
        if lt_max > lt_min:
            route_agg["norm_lead_time"] = (
                (route_agg["avg_lead_time"] - lt_min) / (lt_max - lt_min)
            )
        else:
            route_agg["norm_lead_time"] = 0.0

        route_agg["Route Efficiency Score"] = compute_efficiency_score(
            delay_rate=route_agg["delay_rate"],
            normalised_lead_time=route_agg["norm_lead_time"],
        )

        # Merge back
        df = df.merge(
            route_agg[[route_col, "Route Efficiency Score"]],
            on=route_col,
            how="left",
        )
        self.logger.info(
            "Route Efficiency Score — min: %.3f, median: %.3f, max: %.3f",
            df["Route Efficiency Score"].min(),
            df["Route Efficiency Score"].median(),
            df["Route Efficiency Score"].max(),
        )
        return df

    def _log_feature_summary(self, df: pd.DataFrame) -> None:
        """Log a summary of all generated features."""
        new_cols = [
            "Factory", "Factory Latitude", "Factory Longitude",
            "Shipping Lead Time", "Delay Flag",
            "Factory → State Route", "Factory → Region Route", "Route ID",
            "Shipment Year", "Shipment Month", "Shipment Month Name",
            "Shipment Quarter", "Shipment Week", "Shipment Day",
            "Shipment Day of Week", "Route Efficiency Score",
        ]
        self.logger.info("-" * 60)
        self.logger.info("FEATURE SUMMARY")
        self.logger.info("-" * 60)
        for col in new_cols:
            if col in df.columns:
                self.logger.info("  ✓ %-35s dtype: %s", col, df[col].dtype)
            else:
                self.logger.warning("  ✗ MISSING: %s", col)
        self.logger.info("  Final shape: %d rows × %d columns", *df.shape)
        self.logger.info("-" * 60)


# ─────────────────────────────────────────────────────────────────────────────
# STANDALONE ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    """Run the feature engineering pipeline as a standalone script."""
    from src.utils import ensure_dirs
    ensure_dirs()
    engineer = FeatureEngineer()
    df = engineer.run()
    print("\nNew feature columns:")
    new_cols = [c for c in df.columns if c not in [
        "Row ID", "Order ID", "Order Date", "Ship Date", "Ship Mode",
        "Customer ID", "Country/Region", "City", "State/Province",
        "Postal Code", "Division", "Region", "Product ID", "Product Name",
        "Sales", "Units", "Gross Profit", "Cost",
    ]]
    for col in new_cols:
        col_display = col.replace("\u2192", "->")
        print(f"  {col_display}: {df[col].dtype}")


if __name__ == "__main__":
    main()
