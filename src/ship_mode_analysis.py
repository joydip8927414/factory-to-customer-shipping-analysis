"""
ship_mode_analysis.py
=====================
Phase 7 — Ship Mode Analysis for the Nassau Candy Distributor Shipping Analysis.

Compares shipping modes across lead time, delay rate, revenue, profit,
units, and cost trade-offs, generating data ready for dashboard charts.

Usage (standalone):
    python src/ship_mode_analysis.py

Usage (as module):
    from src.ship_mode_analysis import ShipModeAnalyzer
    analyzer = ShipModeAnalyzer(df)
    summary = analyzer.mode_summary()

Author: Nassau Candy Analytics Team
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils import (
    FEATURED_DATA_FILE,
    SHIP_MODES_ORDERED,
    get_logger,
    load_data,
)

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# SHIP MODE ANALYZER CLASS
# ─────────────────────────────────────────────────────────────────────────────

class ShipModeAnalyzer:
    """
    Compares all shipping modes on performance, cost, and logistics KPIs.

    Attributes:
        df:     Featured DataFrame (output of Phase 2).
        logger: Module-level logger.

    Example:
        >>> analyzer = ShipModeAnalyzer(df)
        >>> print(analyzer.mode_summary())
    """

    def __init__(self, df: pd.DataFrame) -> None:
        self.df = df.copy()
        self.logger = get_logger(self.__class__.__name__)

    # ── Core Summary ──────────────────────────────────────────────────────────

    def mode_summary(self, df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """
        Compute a comprehensive per-mode summary table.

        Args:
            df: Optional filtered DataFrame.

        Returns:
            DataFrame with one row per ship mode, ordered slowest→fastest:
            Ship Mode, shipments, total_sales, total_profit, total_units,
            avg_lead_time, median_lead_time, std_lead_time, min_lead_time,
            max_lead_time, delay_rate_pct, avg_cost, profit_per_shipment,
            sales_share_pct, volume_share_pct.
        """
        d = df if df is not None else self.df
        agg = d.groupby("Ship Mode").agg(
            shipments=("Row ID", "count"),
            total_sales=("Sales", "sum"),
            total_profit=("Gross Profit", "sum"),
            total_units=("Units", "sum"),
            avg_lead_time=("Shipping Lead Time", "mean"),
            median_lead_time=("Shipping Lead Time", "median"),
            std_lead_time=("Shipping Lead Time", "std"),
            min_lead_time=("Shipping Lead Time", "min"),
            max_lead_time=("Shipping Lead Time", "max"),
            delay_rate=("Delay Flag", "mean"),
            avg_cost=("Cost", "mean"),
            total_cost=("Cost", "sum"),
        ).reset_index()

        agg["delay_rate_pct"]       = (agg["delay_rate"] * 100).round(2)
        agg["profit_per_shipment"]  = (agg["total_profit"] / agg["shipments"]).round(2)
        agg["sales_per_shipment"]   = (agg["total_sales"] / agg["shipments"]).round(2)
        agg["profit_margin_pct"]    = (
            agg["total_profit"] / agg["total_sales"].replace(0, np.nan) * 100
        ).fillna(0).round(2)

        total_shipments = agg["shipments"].sum()
        total_sales = agg["total_sales"].sum()
        agg["volume_share_pct"] = (agg["shipments"] / total_shipments * 100).round(2)
        agg["sales_share_pct"]  = (agg["total_sales"] / total_sales * 100).round(2)

        for col in ["avg_lead_time", "median_lead_time", "std_lead_time",
                    "avg_cost", "total_cost"]:
            agg[col] = agg[col].round(2)

        # Order by speed (slowest first per SHIP_MODES_ORDERED)
        mode_order = {m: i for i, m in enumerate(SHIP_MODES_ORDERED)}
        agg["_order"] = agg["Ship Mode"].map(mode_order).fillna(99)
        agg = agg.sort_values("_order").drop(columns=["_order"]).reset_index(drop=True)
        return agg

    # ── Lead Time Distribution ────────────────────────────────────────────────

    def lead_time_distribution(
        self, df: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Return raw lead time values per ship mode (for box/violin plots).

        Args:
            df: Optional filtered DataFrame.

        Returns:
            DataFrame with columns: Ship Mode, Shipping Lead Time.
        """
        d = df if df is not None else self.df
        return d[["Ship Mode", "Shipping Lead Time"]].copy()

    # ── Monthly Mode Trend ────────────────────────────────────────────────────

    def monthly_mode_trend(
        self, df: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Compute monthly shipment volume per ship mode.

        Args:
            df: Optional filtered DataFrame.

        Returns:
            DataFrame with columns: Shipment Year, Shipment Month,
            Ship Mode, shipments, total_sales, avg_lead_time.
        """
        d = df if df is not None else self.df
        agg = d.groupby(["Shipment Year", "Shipment Month", "Ship Mode"]).agg(
            shipments=("Row ID", "count"),
            total_sales=("Sales", "sum"),
            avg_lead_time=("Shipping Lead Time", "mean"),
            delay_rate=("Delay Flag", "mean"),
        ).reset_index()
        agg["delay_rate_pct"] = (agg["delay_rate"] * 100).round(2)
        agg["avg_lead_time"] = agg["avg_lead_time"].round(2)
        return agg.sort_values(["Shipment Year", "Shipment Month"]).reset_index(drop=True)

    # ── Mode × Factory Breakdown ──────────────────────────────────────────────

    def mode_factory_breakdown(
        self, df: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Cross-tabulate ship mode and factory for shipment counts.

        Args:
            df: Optional filtered DataFrame.

        Returns:
            Pivot DataFrame (factories as rows, ship modes as columns).
        """
        d = df if df is not None else self.df
        pivot = d.pivot_table(
            index="Factory",
            columns="Ship Mode",
            values="Row ID",
            aggfunc="count",
            fill_value=0,
        ).reset_index()
        return pivot

    # ── Mode × Region Breakdown ───────────────────────────────────────────────

    def mode_region_breakdown(
        self, df: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Cross-tabulate ship mode and region for shipment counts.

        Args:
            df: Optional filtered DataFrame.

        Returns:
            Pivot DataFrame (regions as rows, ship modes as columns).
        """
        d = df if df is not None else self.df
        pivot = d.pivot_table(
            index="Region",
            columns="Ship Mode",
            values="Row ID",
            aggfunc="count",
            fill_value=0,
        ).reset_index()
        return pivot

    # ── Cost-Time Trade-off ────────────────────────────────────────────────────

    def cost_time_tradeoff(
        self, df: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Build a cost vs. lead time summary for scatter chart analysis.

        Args:
            df: Optional filtered DataFrame.

        Returns:
            DataFrame with Ship Mode, avg_cost, avg_lead_time,
            delay_rate_pct, profit_margin_pct, shipments.
        """
        summary = self.mode_summary(df)
        return summary[[
            "Ship Mode", "avg_cost", "avg_lead_time",
            "delay_rate_pct", "profit_margin_pct", "shipments",
            "volume_share_pct", "sales_share_pct",
        ]]

    # ── Delay Analysis ────────────────────────────────────────────────────────

    def delay_by_mode_and_region(
        self, df: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Compute delay rates broken down by ship mode and region.

        Args:
            df: Optional filtered DataFrame.

        Returns:
            DataFrame with Ship Mode, Region, delay_rate_pct, shipments.
        """
        d = df if df is not None else self.df
        agg = d.groupby(["Ship Mode", "Region"]).agg(
            shipments=("Row ID", "count"),
            delay_rate=("Delay Flag", "mean"),
        ).reset_index()
        agg["delay_rate_pct"] = (agg["delay_rate"] * 100).round(2)
        return agg.sort_values(["Ship Mode", "delay_rate_pct"], ascending=[True, False])

    def on_time_vs_delayed(
        self, df: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Return on-time vs. delayed counts per ship mode for stacked bars.

        Args:
            df: Optional filtered DataFrame.

        Returns:
            DataFrame with Ship Mode, on_time, delayed, total.
        """
        d = df if df is not None else self.df
        agg = d.groupby(["Ship Mode", "Delay Flag"]).size().unstack(fill_value=0)
        agg.columns = [("delayed" if c else "on_time") for c in agg.columns]
        if "delayed" not in agg.columns:
            agg["delayed"] = 0
        if "on_time" not in agg.columns:
            agg["on_time"] = 0
        agg["total"] = agg["delayed"] + agg["on_time"]
        agg = agg.reset_index()

        # Order by speed
        mode_order = {m: i for i, m in enumerate(SHIP_MODES_ORDERED)}
        agg["_order"] = agg["Ship Mode"].map(mode_order).fillna(99)
        return agg.sort_values("_order").drop(columns=["_order"]).reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# STANDALONE ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    """Run ship mode analysis and print results."""
    from src.utils import ensure_dirs
    ensure_dirs()

    df = load_data(FEATURED_DATA_FILE, date_cols=["Order Date", "Ship Date"])
    analyzer = ShipModeAnalyzer(df)

    print("\n=== SHIP MODE SUMMARY ===")
    summary = analyzer.mode_summary()
    print(summary[[
        "Ship Mode", "shipments", "avg_lead_time", "delay_rate_pct",
        "profit_per_shipment", "volume_share_pct"
    ]].to_string(index=False))

    print("\n=== COST vs TIME TRADE-OFF ===")
    print(analyzer.cost_time_tradeoff().to_string(index=False))

    print("\n=== ON-TIME vs DELAYED per MODE ===")
    print(analyzer.on_time_vs_delayed().to_string(index=False))


if __name__ == "__main__":
    main()
