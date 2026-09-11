"""
kpi.py
======
Phase 4 — KPI Module for the Nassau Candy Distributor Shipping Analysis.

Calculates all key performance indicators (KPIs) used on the Streamlit
dashboard. All methods accept a pre-filtered DataFrame so that the dashboard
can pass in sidebar-filtered data without any re-loading.

Usage (standalone):
    python src/kpi.py

Usage (as module):
    from src.kpi import KPICalculator
    calc = KPICalculator(df)
    summary = calc.get_summary()

Author: Nassau Candy Analytics Team
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

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
# KPI CALCULATOR CLASS
# ─────────────────────────────────────────────────────────────────────────────

class KPICalculator:
    """
    Computes all KPIs for the Nassau Candy Distributor logistics dashboard.

    All public methods accept an optional ``df`` argument so they can operate
    on any filtered slice. If omitted, the full dataset passed at construction
    is used.

    Attributes:
        df:     The featured DataFrame (output of Phase 2).
        logger: Module-level logger.

    Example:
        >>> calc = KPICalculator(df)
        >>> summary = calc.get_summary()
        >>> print(summary["total_orders"])
    """

    def __init__(self, df: pd.DataFrame) -> None:
        self.df = df.copy()
        self.logger = get_logger(self.__class__.__name__)

    # ── Summary ───────────────────────────────────────────────────────────────

    def get_summary(self, df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Compute a full KPI summary dictionary.

        Returns a dict containing every top-level metric for the Overview page.

        Args:
            df: Optional filtered DataFrame. Defaults to ``self.df``.

        Returns:
            Dictionary with keys matching dashboard KPI cards.
        """
        d = df if df is not None else self.df
        return {
            # Volume
            "total_orders":         self.total_orders(d),
            "total_shipments":      self.total_shipments(d),
            "total_units":          self.total_units(d),
            "avg_units_per_order":  self.avg_units_per_order(d),

            # Financial
            "total_sales":          self.total_sales(d),
            "total_profit":         self.total_profit(d),
            "total_cost":           self.total_cost(d),
            "avg_sales":            self.avg_sales(d),
            "avg_profit":           self.avg_profit(d),
            "avg_cost":             self.avg_cost(d),
            "profit_margin_pct":    self.profit_margin_pct(d),

            # Logistics
            "avg_lead_time":        self.avg_lead_time(d),
            "median_lead_time":     self.median_lead_time(d),
            "min_lead_time":        self.min_lead_time(d),
            "max_lead_time":        self.max_lead_time(d),
            "delay_rate_pct":       self.delay_rate_pct(d),
            "on_time_rate_pct":     self.on_time_rate_pct(d),
            "total_delayed":        self.total_delayed(d),

            # Geo
            "unique_states":        self.unique_states(d),
            "unique_routes":        self.unique_routes(d),
        }

    # ── Volume KPIs ───────────────────────────────────────────────────────────

    def total_orders(self, df: Optional[pd.DataFrame] = None) -> int:
        """Return count of unique Order IDs."""
        d = df if df is not None else self.df
        return int(d["Order ID"].nunique())

    def total_shipments(self, df: Optional[pd.DataFrame] = None) -> int:
        """Return total number of shipment records (rows)."""
        d = df if df is not None else self.df
        return int(len(d))

    def total_units(self, df: Optional[pd.DataFrame] = None) -> int:
        """Return total units shipped."""
        d = df if df is not None else self.df
        return int(d["Units"].sum())

    def avg_units_per_order(self, df: Optional[pd.DataFrame] = None) -> float:
        """Return average units per order."""
        d = df if df is not None else self.df
        return round(d["Units"].mean(), 2)

    # ── Financial KPIs ────────────────────────────────────────────────────────

    def total_sales(self, df: Optional[pd.DataFrame] = None) -> float:
        """Return total sales revenue."""
        d = df if df is not None else self.df
        return round(float(d["Sales"].sum()), 2)

    def total_profit(self, df: Optional[pd.DataFrame] = None) -> float:
        """Return total gross profit."""
        d = df if df is not None else self.df
        return round(float(d["Gross Profit"].sum()), 2)

    def total_cost(self, df: Optional[pd.DataFrame] = None) -> float:
        """Return total cost."""
        d = df if df is not None else self.df
        return round(float(d["Cost"].sum()), 2)

    def avg_sales(self, df: Optional[pd.DataFrame] = None) -> float:
        """Return average sales per shipment."""
        d = df if df is not None else self.df
        return round(float(d["Sales"].mean()), 2)

    def avg_profit(self, df: Optional[pd.DataFrame] = None) -> float:
        """Return average gross profit per shipment."""
        d = df if df is not None else self.df
        return round(float(d["Gross Profit"].mean()), 2)

    def avg_cost(self, df: Optional[pd.DataFrame] = None) -> float:
        """Return average cost per shipment."""
        d = df if df is not None else self.df
        return round(float(d["Cost"].mean()), 2)

    def profit_margin_pct(self, df: Optional[pd.DataFrame] = None) -> float:
        """Return overall gross profit margin as a percentage."""
        d = df if df is not None else self.df
        total_s = d["Sales"].sum()
        if total_s == 0:
            return 0.0
        return round(float(d["Gross Profit"].sum() / total_s * 100), 2)

    # ── Logistics KPIs ────────────────────────────────────────────────────────

    def avg_lead_time(self, df: Optional[pd.DataFrame] = None) -> float:
        """Return average shipping lead time in days."""
        d = df if df is not None else self.df
        return round(float(d["Shipping Lead Time"].mean()), 2)

    def median_lead_time(self, df: Optional[pd.DataFrame] = None) -> float:
        """Return median shipping lead time in days."""
        d = df if df is not None else self.df
        return round(float(d["Shipping Lead Time"].median()), 2)

    def min_lead_time(self, df: Optional[pd.DataFrame] = None) -> int:
        """Return minimum shipping lead time in days."""
        d = df if df is not None else self.df
        return int(d["Shipping Lead Time"].min())

    def max_lead_time(self, df: Optional[pd.DataFrame] = None) -> int:
        """Return maximum shipping lead time in days."""
        d = df if df is not None else self.df
        return int(d["Shipping Lead Time"].max())

    def delay_rate_pct(self, df: Optional[pd.DataFrame] = None) -> float:
        """Return percentage of shipments flagged as delayed."""
        d = df if df is not None else self.df
        if len(d) == 0:
            return 0.0
        return round(float(d["Delay Flag"].mean() * 100), 2)

    def on_time_rate_pct(self, df: Optional[pd.DataFrame] = None) -> float:
        """Return percentage of on-time shipments."""
        return round(100.0 - self.delay_rate_pct(df), 2)

    def total_delayed(self, df: Optional[pd.DataFrame] = None) -> int:
        """Return total count of delayed shipments."""
        d = df if df is not None else self.df
        return int(d["Delay Flag"].sum())

    # ── Geographic KPIs ───────────────────────────────────────────────────────

    def unique_states(self, df: Optional[pd.DataFrame] = None) -> int:
        """Return number of unique destination states/provinces."""
        d = df if df is not None else self.df
        return int(d["State/Province"].nunique())

    def unique_routes(self, df: Optional[pd.DataFrame] = None) -> int:
        """Return number of unique Factory → State routes."""
        d = df if df is not None else self.df
        for col in ["Factory → State Route", "Factory -> State Route", "Route", "Route ID"]:
            if col in d.columns:
                return int(d[col].nunique())
        if "Factory" in d.columns and "State/Province" in d.columns:
            return int((d["Factory"] + " → " + d["State/Province"].astype(str)).nunique())
        return 0

    # ── Factory Performance ───────────────────────────────────────────────────

    def factory_performance(self, df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """
        Compute per-factory performance metrics.

        Args:
            df: Optional filtered DataFrame.

        Returns:
            DataFrame indexed by Factory with columns:
            shipments, total_sales, total_profit, avg_lead_time,
            delay_rate_pct, avg_efficiency_score.
        """
        d = df if df is not None else self.df
        agg = d.groupby("Factory").agg(
            shipments=("Row ID", "count"),
            total_sales=("Sales", "sum"),
            total_profit=("Gross Profit", "sum"),
            total_units=("Units", "sum"),
            avg_lead_time=("Shipping Lead Time", "mean"),
            median_lead_time=("Shipping Lead Time", "median"),
            delay_rate=("Delay Flag", "mean"),
            avg_efficiency_score=("Route Efficiency Score", "mean"),
        ).reset_index()

        agg["delay_rate_pct"] = (agg["delay_rate"] * 100).round(2)
        agg["avg_lead_time"] = agg["avg_lead_time"].round(2)
        agg["median_lead_time"] = agg["median_lead_time"].round(2)
        agg["avg_efficiency_score"] = agg["avg_efficiency_score"].round(4)
        agg["profit_margin_pct"] = (
            (agg["total_profit"] / agg["total_sales"].replace(0, np.nan)) * 100
        ).fillna(0).round(2)

        return agg.sort_values("shipments", ascending=False).reset_index(drop=True)

    # ── Route Performance ─────────────────────────────────────────────────────

    def route_performance(
        self,
        df: Optional[pd.DataFrame] = None,
        route_col: str = "Factory → State Route",
    ) -> pd.DataFrame:
        """
        Compute per-route performance metrics.

        Args:
            df:        Optional filtered DataFrame.
            route_col: Column to group by (state or region level route).

        Returns:
            DataFrame with per-route statistics sorted by efficiency score (desc).
        """
        d = df if df is not None else self.df
        if route_col not in d.columns:
            if "Route" in d.columns:
                route_col = "Route"
            elif "Factory" in d.columns and "State/Province" in d.columns:
                d = d.copy()
                d[route_col] = d["Factory"] + " → " + d["State/Province"].astype(str)
        agg = d.groupby(route_col).agg(
            shipments=("Row ID", "count"),
            total_sales=("Sales", "sum"),
            total_profit=("Gross Profit", "sum"),
            avg_lead_time=("Shipping Lead Time", "mean"),
            median_lead_time=("Shipping Lead Time", "median"),
            std_lead_time=("Shipping Lead Time", "std"),
            min_lead_time=("Shipping Lead Time", "min"),
            max_lead_time=("Shipping Lead Time", "max"),
            delay_rate=("Delay Flag", "mean"),
            avg_efficiency_score=("Route Efficiency Score", "mean"),
        ).reset_index()

        agg["delay_rate_pct"] = (agg["delay_rate"] * 100).round(2)
        agg["lead_time_cv"] = (
            agg["std_lead_time"] / agg["avg_lead_time"].replace(0, np.nan)
        ).fillna(0).round(4)  # Coefficient of variation

        # Round numeric columns
        for col in ["avg_lead_time", "median_lead_time", "std_lead_time",
                    "min_lead_time", "max_lead_time", "avg_efficiency_score"]:
            agg[col] = agg[col].round(2)

        # Rank: 1 = best
        agg["rank"] = agg["avg_efficiency_score"].rank(ascending=False, method="min").astype(int)

        return agg.sort_values("avg_efficiency_score", ascending=False).reset_index(drop=True)

    # ── Ship Mode KPIs ────────────────────────────────────────────────────────

    def ship_mode_performance(self, df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """
        Compute per-ship-mode performance metrics.

        Args:
            df: Optional filtered DataFrame.

        Returns:
            DataFrame with one row per ship mode.
        """
        d = df if df is not None else self.df
        agg = d.groupby("Ship Mode").agg(
            shipments=("Row ID", "count"),
            total_sales=("Sales", "sum"),
            total_profit=("Gross Profit", "sum"),
            total_units=("Units", "sum"),
            avg_lead_time=("Shipping Lead Time", "mean"),
            median_lead_time=("Shipping Lead Time", "median"),
            delay_rate=("Delay Flag", "mean"),
            avg_cost=("Cost", "mean"),
        ).reset_index()

        agg["delay_rate_pct"] = (agg["delay_rate"] * 100).round(2)
        agg["profit_per_shipment"] = (agg["total_profit"] / agg["shipments"]).round(2)
        agg["avg_lead_time"] = agg["avg_lead_time"].round(2)

        # Order by ship mode speed (slowest first)
        mode_order = {m: i for i, m in enumerate(SHIP_MODES_ORDERED)}
        agg["_order"] = agg["Ship Mode"].map(mode_order).fillna(99)
        agg = agg.sort_values("_order").drop(columns=["_order"]).reset_index(drop=True)
        return agg

    # ── Time Series ───────────────────────────────────────────────────────────

    def monthly_trend(self, df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """
        Compute month-level trend data for shipments, sales, profit.

        Args:
            df: Optional filtered DataFrame.

        Returns:
            DataFrame with columns: year, month, shipments, sales, profit,
            avg_lead_time, delay_rate_pct.
        """
        d = df if df is not None else self.df
        agg = d.groupby(["Shipment Year", "Shipment Month", "Shipment Month Name"]).agg(
            shipments=("Row ID", "count"),
            sales=("Sales", "sum"),
            profit=("Gross Profit", "sum"),
            avg_lead_time=("Shipping Lead Time", "mean"),
            delay_rate=("Delay Flag", "mean"),
        ).reset_index()

        agg["delay_rate_pct"] = (agg["delay_rate"] * 100).round(2)
        agg["avg_lead_time"] = agg["avg_lead_time"].round(2)
        agg = agg.sort_values(["Shipment Year", "Shipment Month"]).reset_index(drop=True)
        return agg

    # ── Top / Bottom Products ─────────────────────────────────────────────────

    def top_products(
        self,
        df: Optional[pd.DataFrame] = None,
        n: int = 10,
        metric: str = "sales",
    ) -> pd.DataFrame:
        """
        Return the top-N products by a given metric.

        Args:
            df:     Optional filtered DataFrame.
            n:      Number of products to return.
            metric: One of ``"sales"``, ``"profit"``, ``"units"``, ``"shipments"``.

        Returns:
            DataFrame with top-N products sorted descending by ``metric``.
        """
        d = df if df is not None else self.df
        agg = d.groupby(["Product Name", "Factory"]).agg(
            shipments=("Row ID", "count"),
            sales=("Sales", "sum"),
            profit=("Gross Profit", "sum"),
            units=("Units", "sum"),
        ).reset_index()
        return agg.sort_values(metric, ascending=False).head(n).reset_index(drop=True)

    def bottom_products(
        self,
        df: Optional[pd.DataFrame] = None,
        n: int = 10,
        metric: str = "sales",
    ) -> pd.DataFrame:
        """
        Return the bottom-N products by a given metric.

        Args:
            df:     Optional filtered DataFrame.
            n:      Number of products to return.
            metric: One of ``"sales"``, ``"profit"``, ``"units"``, ``"shipments"``.

        Returns:
            DataFrame with bottom-N products sorted ascending by ``metric``.
        """
        d = df if df is not None else self.df
        agg = d.groupby(["Product Name", "Factory"]).agg(
            shipments=("Row ID", "count"),
            sales=("Sales", "sum"),
            profit=("Gross Profit", "sum"),
            units=("Units", "sum"),
        ).reset_index()
        return agg.sort_values(metric, ascending=True).head(n).reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# STANDALONE ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    """Compute and print all KPIs as a standalone script."""
    from src.utils import ensure_dirs
    ensure_dirs()

    df = load_data(FEATURED_DATA_FILE, date_cols=["Order Date", "Ship Date"])
    calc = KPICalculator(df)
    summary = calc.get_summary()

    print("\n" + "=" * 50)
    print("KPI SUMMARY — Nassau Candy Distributor")
    print("=" * 50)
    for key, val in summary.items():
        print(f"  {key:<25}: {val}")

    print("\n— Factory Performance —")
    print(calc.factory_performance().to_string(index=False))

    print("\n— Ship Mode Performance —")
    print(calc.ship_mode_performance().to_string(index=False))

    print("\n— Top 5 Routes by Efficiency —")
    print(calc.route_performance().head(5).to_string(index=False))


if __name__ == "__main__":
    main()
