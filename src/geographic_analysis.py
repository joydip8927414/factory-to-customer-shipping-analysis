"""
geographic_analysis.py
======================
Phase 6 — Geographic Analysis for the Nassau Candy Distributor Shipping Analysis.

Provides:
    - State-level performance metrics
    - Regional performance metrics
    - Factory coverage maps
    - Shipping density analysis
    - Bottleneck state identification
    - High-delay region detection
    - Interactive US map data (Plotly choropleth + scattergeo)

Usage (standalone):
    python src/geographic_analysis.py

Usage (as module):
    from src.geographic_analysis import GeoAnalyzer
    geo = GeoAnalyzer(df)
    state_df = geo.state_performance()

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
    FACTORY_COLOURS,
    FACTORY_COORDINATES,
    FEATURED_DATA_FILE,
    US_STATES,
    get_logger,
    load_data,
)

logger = get_logger(__name__)

# US state abbreviation map (needed for Plotly choropleth locationmode)
_STATE_ABBREV: dict[str, str] = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "District of Columbia": "DC", "Florida": "FL", "Georgia": "GA", "Hawaii": "HI",
    "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
    "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
    "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
    "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
    "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
    "Wisconsin": "WI", "Wyoming": "WY",
}

# Customer state approximate centroids (lat, lon) for scattergeo
_STATE_CENTROIDS: dict[str, tuple[float, float]] = {
    "Alabama": (32.806671, -86.791130), "Alaska": (61.370716, -152.404419),
    "Arizona": (33.729759, -111.431221), "Arkansas": (34.969704, -92.373123),
    "California": (36.116203, -119.681564), "Colorado": (39.059811, -105.311104),
    "Connecticut": (41.597782, -72.755371), "Delaware": (39.318523, -75.507141),
    "District of Columbia": (38.897438, -77.026817),
    "Florida": (27.766279, -81.686783), "Georgia": (33.040619, -83.643074),
    "Hawaii": (21.094318, -157.498337), "Idaho": (44.240459, -114.478828),
    "Illinois": (40.349457, -88.986137), "Indiana": (39.849426, -86.258278),
    "Iowa": (42.011539, -93.210526), "Kansas": (38.526600, -96.726486),
    "Kentucky": (37.668140, -84.670067), "Louisiana": (31.169960, -91.867805),
    "Maine": (44.693947, -69.381927), "Maryland": (39.063946, -76.802101),
    "Massachusetts": (42.230171, -71.530106), "Michigan": (43.326618, -84.536095),
    "Minnesota": (45.694454, -93.900192), "Mississippi": (32.741646, -89.678696),
    "Missouri": (38.456085, -92.288368), "Montana": (46.921925, -110.454353),
    "Nebraska": (41.125370, -98.268082), "Nevada": (38.313515, -117.055374),
    "New Hampshire": (43.452492, -71.563896), "New Jersey": (40.298904, -74.521011),
    "New Mexico": (34.840515, -106.248482), "New York": (42.165726, -74.948051),
    "North Carolina": (35.630066, -79.806419), "North Dakota": (47.528912, -99.784012),
    "Ohio": (40.388783, -82.764915), "Oklahoma": (35.565342, -96.928917),
    "Oregon": (44.572021, -122.070938), "Pennsylvania": (40.590752, -77.209755),
    "Rhode Island": (41.680893, -71.511780), "South Carolina": (33.856892, -80.945007),
    "South Dakota": (44.299782, -99.438828), "Tennessee": (35.747845, -86.692345),
    "Texas": (31.054487, -97.563461), "Utah": (40.150032, -111.862434),
    "Vermont": (44.045876, -72.710686), "Virginia": (37.769337, -78.169968),
    "Washington": (47.400902, -121.490494), "West Virginia": (38.491226, -80.954453),
    "Wisconsin": (44.268543, -89.616508), "Wyoming": (42.755966, -107.302490),
}


# ─────────────────────────────────────────────────────────────────────────────
# GEO ANALYZER CLASS
# ─────────────────────────────────────────────────────────────────────────────

class GeoAnalyzer:
    """
    Performs geographic analysis on the Nassau Candy shipment dataset.

    Attributes:
        df:      Featured DataFrame (output of Phase 2).
        df_us:   Subset restricted to US states only.
        logger:  Module-level logger.

    Example:
        >>> geo = GeoAnalyzer(df)
        >>> print(geo.state_performance().head())
    """

    def __init__(self, df: pd.DataFrame) -> None:
        self.df = df.copy()
        self.df_us = df[df["State/Province"].isin(US_STATES)].copy()
        self.logger = get_logger(self.__class__.__name__)
        self.logger.info(
            "GeoAnalyzer: %d total rows, %d US-only rows",
            len(self.df), len(self.df_us)
        )

    # ── State Performance ─────────────────────────────────────────────────────

    def state_performance(
        self, df: Optional[pd.DataFrame] = None, us_only: bool = True
    ) -> pd.DataFrame:
        """
        Compute per-state performance metrics.

        Args:
            df:      Optional filtered DataFrame.
            us_only: If True, restrict to US states (excludes Canadian provinces).

        Returns:
            DataFrame with one row per state, enriched with abbreviation and
            centroid coordinates.
        """
        d = (df if df is not None else (self.df_us if us_only else self.df))
        agg = d.groupby("State/Province").agg(
            shipments=("Row ID", "count"),
            total_sales=("Sales", "sum"),
            total_profit=("Gross Profit", "sum"),
            total_units=("Units", "sum"),
            avg_lead_time=("Shipping Lead Time", "mean"),
            median_lead_time=("Shipping Lead Time", "median"),
            delay_rate=("Delay Flag", "mean"),
            avg_efficiency_score=("Route Efficiency Score", "mean"),
        ).reset_index()

        agg.rename(columns={"State/Province": "state"}, inplace=True)
        agg["delay_rate_pct"] = (agg["delay_rate"] * 100).round(2)
        agg["avg_lead_time"] = agg["avg_lead_time"].round(2)
        agg["avg_efficiency_score"] = agg["avg_efficiency_score"].round(4)
        agg["profit_margin_pct"] = (
            agg["total_profit"] / agg["total_sales"].replace(0, np.nan) * 100
        ).fillna(0).round(2)

        # Add abbreviation and centroid for Plotly maps
        agg["state_abbrev"] = agg["state"].map(_STATE_ABBREV)
        agg["lat"] = agg["state"].map(lambda s: _STATE_CENTROIDS.get(s, (None, None))[0])
        agg["lon"] = agg["state"].map(lambda s: _STATE_CENTROIDS.get(s, (None, None))[1])

        return agg.sort_values("shipments", ascending=False).reset_index(drop=True)

    # ── Regional Performance ──────────────────────────────────────────────────

    def region_performance(
        self, df: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Compute per-region performance metrics.

        Args:
            df: Optional filtered DataFrame.

        Returns:
            DataFrame with one row per region.
        """
        d = df if df is not None else self.df
        agg = d.groupby("Region").agg(
            shipments=("Row ID", "count"),
            total_sales=("Sales", "sum"),
            total_profit=("Gross Profit", "sum"),
            total_units=("Units", "sum"),
            avg_lead_time=("Shipping Lead Time", "mean"),
            median_lead_time=("Shipping Lead Time", "median"),
            delay_rate=("Delay Flag", "mean"),
            unique_states=("State/Province", "nunique"),
            avg_efficiency_score=("Route Efficiency Score", "mean"),
        ).reset_index()

        agg["delay_rate_pct"] = (agg["delay_rate"] * 100).round(2)
        agg["avg_lead_time"] = agg["avg_lead_time"].round(2)
        agg["profit_margin_pct"] = (
            agg["total_profit"] / agg["total_sales"].replace(0, np.nan) * 100
        ).fillna(0).round(2)

        return agg.sort_values("shipments", ascending=False).reset_index(drop=True)

    # ── Factory Coverage ──────────────────────────────────────────────────────

    def factory_coverage(
        self, df: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Compute how many states and regions each factory serves.

        Args:
            df: Optional filtered DataFrame.

        Returns:
            DataFrame with factory coordinates plus coverage metrics.
        """
        d = df if df is not None else self.df
        agg = d.groupby("Factory").agg(
            shipments=("Row ID", "count"),
            states_served=("State/Province", "nunique"),
            regions_served=("Region", "nunique"),
            total_sales=("Sales", "sum"),
            avg_lead_time=("Shipping Lead Time", "mean"),
            delay_rate=("Delay Flag", "mean"),
        ).reset_index()

        agg["delay_rate_pct"] = (agg["delay_rate"] * 100).round(2)
        agg["avg_lead_time"] = agg["avg_lead_time"].round(2)

        # Add coordinates
        agg["lat"] = agg["Factory"].map(
            {name: coords[0] for name, coords in FACTORY_COORDINATES.items()}
        )
        agg["lon"] = agg["Factory"].map(
            {name: coords[1] for name, coords in FACTORY_COORDINATES.items()}
        )
        agg["color"] = agg["Factory"].map(FACTORY_COLOURS)

        return agg.sort_values("shipments", ascending=False).reset_index(drop=True)

    # ── Shipping Density ──────────────────────────────────────────────────────

    def shipping_density(
        self, df: Optional[pd.DataFrame] = None, top_n: int = 20
    ) -> pd.DataFrame:
        """
        Return the top-N states by shipment count (density).

        Args:
            df:    Optional filtered DataFrame.
            top_n: Number of states to return.

        Returns:
            DataFrame sorted by shipment count descending.
        """
        state_perf = self.state_performance(df=df)
        return state_perf.head(top_n)

    # ── Bottleneck Detection ───────────────────────────────────────────────────

    def bottleneck_states(
        self,
        delay_threshold: float = 50.0,
        min_shipments: int = 10,
        df: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """
        Identify states with delay rates above a threshold.

        Args:
            delay_threshold: Minimum delay rate (%) to flag as bottleneck.
            min_shipments:   Minimum shipment count to qualify.
            df:              Optional filtered DataFrame.

        Returns:
            DataFrame of bottleneck states sorted by delay rate descending.
        """
        state_perf = self.state_performance(df=df)
        bottlenecks = state_perf[
            (state_perf["delay_rate_pct"] >= delay_threshold) &
            (state_perf["shipments"] >= min_shipments)
        ].sort_values("delay_rate_pct", ascending=False)
        self.logger.info(
            "Found %d bottleneck states (delay >= %.0f%%, min %d shipments)",
            len(bottlenecks), delay_threshold, min_shipments
        )
        return bottlenecks.reset_index(drop=True)

    def high_delay_regions(
        self,
        delay_threshold: float = 45.0,
        df: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """
        Identify regions with above-threshold delay rates.

        Args:
            delay_threshold: Minimum delay rate (%) to flag.
            df:              Optional filtered DataFrame.

        Returns:
            DataFrame of high-delay regions.
        """
        region_perf = self.region_performance(df=df)
        return region_perf[
            region_perf["delay_rate_pct"] >= delay_threshold
        ].sort_values("delay_rate_pct", ascending=False).reset_index(drop=True)

    # ── Route Line Data (for Plotly scattergeo) ───────────────────────────────

    def route_line_data(
        self,
        df: Optional[pd.DataFrame] = None,
        min_shipments: int = 5,
    ) -> pd.DataFrame:
        """
        Build source/destination coordinate pairs for route lines on the map.

        Each row represents a unique Factory -> State route segment with
        aggregated metrics and both endpoint coordinates.

        Args:
            df:             Optional filtered DataFrame.
            min_shipments:  Minimum shipments for a route to be included.

        Returns:
            DataFrame with columns: Factory, state, factory_lat, factory_lon,
            state_lat, state_lon, shipments, avg_lead_time, delay_rate_pct,
            avg_efficiency_score.
        """
        d = df if df is not None else self.df_us
        route_col = "Factory \u2192 State Route"

        agg = d.groupby(["Factory", "State/Province", "Factory Latitude",
                         "Factory Longitude"]).agg(
            shipments=("Row ID", "count"),
            avg_lead_time=("Shipping Lead Time", "mean"),
            delay_rate=("Delay Flag", "mean"),
            avg_efficiency_score=("Route Efficiency Score", "mean"),
        ).reset_index()

        agg = agg[agg["shipments"] >= min_shipments].copy()
        agg["delay_rate_pct"] = (agg["delay_rate"] * 100).round(2)
        agg["avg_lead_time"] = agg["avg_lead_time"].round(2)
        agg["avg_efficiency_score"] = agg["avg_efficiency_score"].round(4)

        # Customer state centroids
        agg["state_lat"] = agg["State/Province"].map(
            lambda s: _STATE_CENTROIDS.get(s, (None, None))[0]
        )
        agg["state_lon"] = agg["State/Province"].map(
            lambda s: _STATE_CENTROIDS.get(s, (None, None))[1]
        )

        agg.rename(columns={
            "Factory Latitude": "factory_lat",
            "Factory Longitude": "factory_lon",
            "State/Province": "state",
        }, inplace=True)

        # Drop rows without coordinates
        agg = agg.dropna(subset=["state_lat", "state_lon"])
        return agg.reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# STANDALONE ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    """Run geographic analysis and print summary results."""
    from src.utils import ensure_dirs
    ensure_dirs()

    df = load_data(FEATURED_DATA_FILE, date_cols=["Order Date", "Ship Date"])
    geo = GeoAnalyzer(df)

    print("\n=== STATE PERFORMANCE (Top 10) ===")
    print(geo.state_performance().head(10)[
        ["state", "shipments", "avg_lead_time", "delay_rate_pct"]
    ].to_string(index=False))

    print("\n=== REGIONAL PERFORMANCE ===")
    print(geo.region_performance()[
        ["Region", "shipments", "avg_lead_time", "delay_rate_pct", "unique_states"]
    ].to_string(index=False))

    print("\n=== FACTORY COVERAGE ===")
    print(geo.factory_coverage()[
        ["Factory", "shipments", "states_served", "regions_served"]
    ].to_string(index=False))

    print("\n=== BOTTLENECK STATES (delay >= 50%) ===")
    bn = geo.bottleneck_states(delay_threshold=50.0)
    print(bn[["state", "shipments", "delay_rate_pct"]].head(10).to_string(index=False))


if __name__ == "__main__":
    main()
