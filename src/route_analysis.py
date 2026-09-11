"""
route_analysis.py
=================
Phase 5 — Route Analysis for the Nassau Candy Distributor Shipping Analysis.

Provides comprehensive Factory -> Customer State / Region route analytics:
    - Per-route shipment counts, lead times, delay rates
    - Route ranking and efficiency scoring
    - Top / bottom route identification
    - Consistency and variability analysis

Usage (standalone):
    python src/route_analysis.py

Usage (as module):
    from src.route_analysis import RouteAnalyzer
    analyzer = RouteAnalyzer(df)
    best_routes = analyzer.top_routes(n=10)

Author: Nassau Candy Analytics Team
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal, Optional

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils import (
    FEATURED_DATA_FILE,
    get_logger,
    load_data,
)

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE ANALYZER CLASS
# ─────────────────────────────────────────────────────────────────────────────

class RouteAnalyzer:
    """
    Performs all route-level aggregations and rankings.

    Attributes:
        df:     Featured DataFrame (output of Phase 2).
        logger: Module-level logger.

    Example:
        >>> analyzer = RouteAnalyzer(df)
        >>> print(analyzer.route_summary("state").head())
    """

    def __init__(self, df: pd.DataFrame) -> None:
        self.df = df.copy()
        self.logger = get_logger(self.__class__.__name__)

    # ── Core Aggregations ─────────────────────────────────────────────────────

    def route_summary(
        self,
        level: Literal["state", "region"] = "state",
        df: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """
        Aggregate shipment statistics per route.

        Args:
            level: ``"state"`` for Factory->State routes, ``"region"`` for
                   Factory->Region routes.
            df:    Optional filtered DataFrame. Defaults to ``self.df``.

        Returns:
            DataFrame with one row per route, columns:
            route, factory, destination, shipments, total_sales, total_profit,
            avg_lead_time, median_lead_time, std_lead_time, min_lead_time,
            max_lead_time, delay_rate_pct, lead_time_cv,
            avg_efficiency_score, rank.
        """
        d = df if df is not None else self.df
        route_col = "Factory -> State Route" if level == "state" else "Factory -> Region Route"

        # Rename arrow column for safe printing
        d = d.copy()
        src_col = "Factory \u2192 State Route" if level == "state" else "Factory \u2192 Region Route"
        if src_col in d.columns:
            d[route_col] = d[src_col]
        elif "Route" in d.columns and level == "state":
            d[route_col] = d["Route"]
        elif "Factory" in d.columns and ("State/Province" in d.columns or "Region" in d.columns):
            dest_target = "State/Province" if level == "state" else "Region"
            if dest_target in d.columns:
                d[route_col] = d["Factory"].astype(str) + " -> " + d[dest_target].astype(str)

        # Determine destination column
        dest_col = "State/Province" if level == "state" else "Region"

        agg = d.groupby([route_col, "Factory", dest_col]).agg(
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
            avg_efficiency_score=("Route Efficiency Score", "mean"),
        ).reset_index()

        agg.rename(columns={route_col: "route", dest_col: "destination"}, inplace=True)

        # Derived metrics
        agg["delay_rate_pct"] = (agg["delay_rate"] * 100).round(2)
        agg["lead_time_cv"] = (
            agg["std_lead_time"] / agg["avg_lead_time"].replace(0, np.nan)
        ).fillna(0)

        for col in ["avg_lead_time", "median_lead_time", "std_lead_time",
                    "min_lead_time", "max_lead_time", "avg_efficiency_score",
                    "lead_time_cv", "total_sales", "total_profit"]:
            agg[col] = agg[col].round(2)

        # Route ranking (1 = best efficiency)
        agg["rank"] = agg["avg_efficiency_score"].rank(
            ascending=False, method="min"
        ).astype(int)

        return agg.sort_values("avg_efficiency_score", ascending=False).reset_index(drop=True)

    # ── Rankings ──────────────────────────────────────────────────────────────

    def top_routes(
        self,
        n: int = 10,
        level: Literal["state", "region"] = "state",
        df: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """
        Return the top-N most efficient routes.

        Args:
            n:     Number of routes to return.
            level: Route granularity level.
            df:    Optional filtered DataFrame.

        Returns:
            DataFrame of top-N routes sorted by efficiency (descending).
        """
        summary = self.route_summary(level=level, df=df)
        return summary.head(n).reset_index(drop=True)

    def worst_routes(
        self,
        n: int = 10,
        level: Literal["state", "region"] = "state",
        df: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """
        Return the bottom-N (worst) routes by efficiency score.

        Args:
            n:     Number of routes to return.
            level: Route granularity level.
            df:    Optional filtered DataFrame.

        Returns:
            DataFrame of bottom-N routes sorted by efficiency (ascending).
        """
        summary = self.route_summary(level=level, df=df)
        return summary.tail(n).sort_values("avg_efficiency_score").reset_index(drop=True)

    def most_consistent_routes(
        self,
        n: int = 10,
        min_shipments: int = 5,
        level: Literal["state", "region"] = "state",
        df: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """
        Return the N routes with the lowest lead time variability (CV).

        Only routes with at least ``min_shipments`` shipments are considered.

        Args:
            n:              Number of routes to return.
            min_shipments:  Minimum shipment count to qualify.
            level:          Route granularity level.
            df:             Optional filtered DataFrame.

        Returns:
            DataFrame of most consistent routes.
        """
        summary = self.route_summary(level=level, df=df)
        filtered = summary[summary["shipments"] >= min_shipments]
        return filtered.sort_values("lead_time_cv").head(n).reset_index(drop=True)

    def most_variable_routes(
        self,
        n: int = 10,
        min_shipments: int = 5,
        level: Literal["state", "region"] = "state",
        df: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """
        Return the N routes with the highest lead time variability (CV).

        Only routes with at least ``min_shipments`` shipments are considered.

        Args:
            n:              Number of routes to return.
            min_shipments:  Minimum shipment count to qualify.
            level:          Route granularity level.
            df:             Optional filtered DataFrame.

        Returns:
            DataFrame of most variable routes.
        """
        summary = self.route_summary(level=level, df=df)
        filtered = summary[summary["shipments"] >= min_shipments]
        return filtered.sort_values("lead_time_cv", ascending=False).head(n).reset_index(drop=True)

    def high_volume_routes(
        self,
        n: int = 10,
        level: Literal["state", "region"] = "state",
        df: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """
        Return the N routes with the highest shipment volume.

        Args:
            n:     Number of routes to return.
            level: Route granularity level.
            df:    Optional filtered DataFrame.

        Returns:
            DataFrame sorted by shipment count (descending).
        """
        summary = self.route_summary(level=level, df=df)
        return summary.sort_values("shipments", ascending=False).head(n).reset_index(drop=True)

    # ── Factory-Level Route Analysis ──────────────────────────────────────────

    def factory_route_heatmap_data(
        self,
        metric: str = "avg_lead_time",
        df: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """
        Build a factory × destination pivot table for heatmap charts.

        Args:
            metric: Column to use as heatmap values. Must be one of the
                    aggregated route-summary columns.
            df:     Optional filtered DataFrame.

        Returns:
            Pivot DataFrame (factories as rows, states as columns).
        """
        summary = self.route_summary(level="state", df=df)
        pivot = summary.pivot_table(
            index="Factory",
            columns="destination",
            values=metric,
            aggfunc="mean",
        ).fillna(0)
        return pivot

    def route_delay_breakdown(
        self,
        level: Literal["state", "region"] = "state",
        df: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """
        Return delay and on-time counts per route for stacked bar charts.

        Args:
            level: Route granularity level.
            df:    Optional filtered DataFrame.

        Returns:
            DataFrame with columns: route, delayed, on_time, total.
        """
        d = df if df is not None else self.df
        route_col_src = "Factory \u2192 State Route" if level == "state" else "Factory \u2192 Region Route"
        route_col = "route"
        d = d.copy()
        d[route_col] = d[route_col_src]

        agg = d.groupby([route_col, "Delay Flag"]).size().unstack(fill_value=0)
        agg.columns = [("delayed" if c else "on_time") for c in agg.columns]
        if "delayed" not in agg.columns:
            agg["delayed"] = 0
        if "on_time" not in agg.columns:
            agg["on_time"] = 0
        agg["total"] = agg["delayed"] + agg["on_time"]
        return agg.reset_index()

    # ── Bottleneck Detection ───────────────────────────────────────────────────

    def bottleneck_routes(
        self,
        delay_threshold: float = 50.0,
        min_shipments: int = 10,
        df: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """
        Identify routes with delay rates above a threshold.

        Args:
            delay_threshold: Delay rate (%) above which a route is a bottleneck.
            min_shipments:   Minimum shipments for a route to qualify.
            df:              Optional filtered DataFrame.

        Returns:
            DataFrame of bottleneck routes sorted by delay rate (descending).
        """
        summary = self.route_summary(level="state", df=df)
        bottlenecks = summary[
            (summary["delay_rate_pct"] >= delay_threshold) &
            (summary["shipments"] >= min_shipments)
        ].sort_values("delay_rate_pct", ascending=False)
        self.logger.info(
            "Found %d bottleneck routes (delay >= %.0f%%, min %d shipments)",
            len(bottlenecks), delay_threshold, min_shipments
        )
        return bottlenecks.reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# STANDALONE ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    """Run route analysis and print key results."""
    from src.utils import ensure_dirs
    ensure_dirs()

    df = load_data(FEATURED_DATA_FILE, date_cols=["Order Date", "Ship Date"])
    analyzer = RouteAnalyzer(df)

    print("\n=== TOP 10 BEST ROUTES (State Level) ===")
    top = analyzer.top_routes(10)
    print(top[["route", "shipments", "avg_lead_time", "delay_rate_pct",
               "avg_efficiency_score", "rank"]].to_string(index=False))

    print("\n=== TOP 10 WORST ROUTES ===")
    worst = analyzer.worst_routes(10)
    print(worst[["route", "shipments", "avg_lead_time", "delay_rate_pct",
                 "avg_efficiency_score", "rank"]].to_string(index=False))

    print("\n=== MOST CONSISTENT ROUTES (Lowest Lead Time CV) ===")
    consistent = analyzer.most_consistent_routes(10)
    print(consistent[["route", "shipments", "std_lead_time", "lead_time_cv"]].to_string(index=False))

    print("\n=== BOTTLENECK ROUTES (Delay >= 50%) ===")
    bottlenecks = analyzer.bottleneck_routes(delay_threshold=50.0)
    print(bottlenecks[["route", "shipments", "delay_rate_pct"]].head(10).to_string(index=False))


if __name__ == "__main__":
    main()
