"""
utils.py
========
Shared utilities for the Nassau Candy Distributor Shipping Analysis project.

Provides:
    - Centralised logging configuration
    - Project-wide path constants
    - Factory metadata (coordinates, product mappings)
    - Colour palette for consistent visualisations
    - Helper functions used across all modules

Author: Nassau Candy Analytics Team
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

# ─────────────────────────────────────────────────────────────────────────────
# PROJECT ROOT & PATH CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

# Resolve project root regardless of where the script is executed from
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

DATA_RAW_DIR: Path = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED_DIR: Path = PROJECT_ROOT / "data" / "processed"
OUTPUTS_CHARTS_DIR: Path = PROJECT_ROOT / "outputs" / "charts"
OUTPUTS_MAPS_DIR: Path = PROJECT_ROOT / "outputs" / "maps"
OUTPUTS_MODELS_DIR: Path = PROJECT_ROOT / "outputs" / "models"
REPORTS_DIR: Path = PROJECT_ROOT / "reports"
NOTEBOOKS_DIR: Path = PROJECT_ROOT / "notebooks"

RAW_DATA_FILE: Path = DATA_RAW_DIR / "Nassau Candy Distributor.csv"
CLEANED_DATA_FILE: Path = DATA_PROCESSED_DIR / "cleaned_data.csv"
FEATURED_DATA_FILE: Path = DATA_PROCESSED_DIR / "featured_data.csv"

# ─────────────────────────────────────────────────────────────────────────────
# ENSURE DIRECTORIES EXIST
# ─────────────────────────────────────────────────────────────────────────────

def ensure_dirs() -> None:
    """Create all required output directories if they do not already exist."""
    dirs = [
        DATA_RAW_DIR,
        DATA_PROCESSED_DIR,
        OUTPUTS_CHARTS_DIR,
        OUTPUTS_MAPS_DIR,
        OUTPUTS_MODELS_DIR,
        REPORTS_DIR,
        NOTEBOOKS_DIR,
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────────────────────

def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Create and return a configured logger.

    Args:
        name:  Logger name, typically ``__name__`` of the calling module.
        level: Logging level (default: ``logging.INFO``).

    Returns:
        A :class:`logging.Logger` instance with a stream handler attached.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # Avoid adding duplicate handlers

    logger.setLevel(level)
    # Use UTF-8 writer to avoid CP1252 encode errors on Windows
    import io
    stream = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, "buffer") else sys.stdout
    handler = logging.StreamHandler(stream)
    handler.setLevel(level)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


# ─────────────────────────────────────────────────────────────────────────────
# FACTORY METADATA
# ─────────────────────────────────────────────────────────────────────────────

#: Factory name → (latitude, longitude)
FACTORY_COORDINATES: Dict[str, Tuple[float, float]] = {
    "Lot's O' Nuts":    (32.881893, -111.768036),
    "Wicked Choccy's":  (32.076176, -81.088371),
    "Sugar Shack":      (48.119140, -96.181150),
    "Secret Factory":   (41.446333, -90.565487),
    "The Other Factory":(35.117500, -89.971107),
}

#: Product name → Factory name
PRODUCT_FACTORY_MAP: Dict[str, str] = {
    # Lot's O' Nuts
    "Wonka Bar - Nutty Crunch Surprise":    "Lot's O' Nuts",
    "Wonka Bar - Fudge Mallows":            "Lot's O' Nuts",
    "Wonka Bar - Scrumdiddlyumptious":      "Lot's O' Nuts",

    # Wicked Choccy's
    "Wonka Bar - Milk Chocolate":           "Wicked Choccy's",
    "Wonka Bar - Triple Dazzle Caramel":    "Wicked Choccy's",

    # Sugar Shack
    "Laffy Taffy":                          "Sugar Shack",
    "SweeTARTS":                            "Sugar Shack",
    "Nerds":                                "Sugar Shack",
    "Fun Dip":                              "Sugar Shack",
    "Fizzy Lifting Drinks":                 "Sugar Shack",

    # Secret Factory
    "Everlasting Gobstopper":               "Secret Factory",
    "Lickable Wallpaper":                   "Secret Factory",
    "Wonka Gum":                            "Secret Factory",

    # The Other Factory
    "Hair Toffee":                          "The Other Factory",
    "Kazookles":                            "The Other Factory",
}

#: Factory → list of products
FACTORY_PRODUCTS: Dict[str, List[str]] = {}
for _product, _factory in PRODUCT_FACTORY_MAP.items():
    FACTORY_PRODUCTS.setdefault(_factory, []).append(_product)

#: Canonical list of US states (for filtering out Canadian provinces)
US_STATES: List[str] = [
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado",
    "Connecticut", "Delaware", "District of Columbia", "Florida", "Georgia",
    "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky",
    "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota",
    "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire",
    "New Jersey", "New Mexico", "New York", "North Carolina", "North Dakota",
    "Ohio", "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island",
    "South Carolina", "South Dakota", "Tennessee", "Texas", "Utah", "Vermont",
    "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming",
]

#: Known regions in the dataset
REGIONS: List[str] = ["Gulf", "Interior", "Pacific", "Atlantic"]

#: Ship modes ordered from slowest to fastest
SHIP_MODES_ORDERED: List[str] = [
    "Standard Class",
    "Second Class",
    "First Class",
    "Same Day",
]

# ─────────────────────────────────────────────────────────────────────────────
# DELAY THRESHOLD CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

#: Lead-time (days) threshold per ship mode above which a shipment is "delayed".
#: Using data-driven approach: median-based thresholds computed at runtime,
#: but these static fallbacks are used if the dataset is unavailable.
DELAY_THRESHOLD_DAYS: Dict[str, float] = {
    "Standard Class": 5.0,
    "Second Class":   3.0,
    "First Class":    2.0,
    "Same Day":       1.0,
}

# ─────────────────────────────────────────────────────────────────────────────
# COLOUR PALETTE
# ─────────────────────────────────────────────────────────────────────────────

#: Primary dark brand colour palette
PALETTE_DARK: Dict[str, str] = {
    "primary":      "#6C63FF",
    "secondary":    "#FF6584",
    "accent":       "#43E97B",
    "warning":      "#F7B731",
    "danger":       "#FC5C7D",
    "info":         "#4FC3F7",
    "success":      "#43E97B",
    "background":   "#0F1117",
    "surface":      "#1E2130",
    "text":         "#E8EAED",
    "muted":        "#9AA0B9",
    "card_bg":      "linear-gradient(135deg,rgba(30,33,48,.9),rgba(20,23,35,.9))",
    "card_border":  "rgba(108,99,255,.25)",
}

#: Premium light brand colour palette
PALETTE_LIGHT: Dict[str, str] = {
    "primary":      "#5348E8",
    "secondary":    "#E83E68",
    "accent":       "#10B981",
    "warning":      "#D97706",
    "danger":       "#EF4444",
    "info":         "#0284C7",
    "success":      "#10B981",
    "background":   "#F8FAFC",
    "surface":      "#FFFFFF",
    "text":         "#0F172A",
    "muted":        "#64748B",
    "card_bg":      "linear-gradient(135deg,#FFFFFF,#F1F5F9)",
    "card_border":  "rgba(83,72,232,.2)",
}

#: Default alias
PALETTE: Dict[str, str] = PALETTE_DARK


def get_palette(theme: str = "dark") -> Dict[str, str]:
    """Return the palette dictionary corresponding to the active theme."""
    return PALETTE_LIGHT if theme.lower() == "light" else PALETTE_DARK


#: Factory colour map for consistent colouring across charts
FACTORY_COLOURS: Dict[str, str] = {
    "Lot's O' Nuts":    "#6C63FF",
    "Wicked Choccy's":  "#FF6584",
    "Sugar Shack":      "#43E97B",
    "Secret Factory":   "#F7B731",
    "The Other Factory":"#4FC3F7",
}

#: Region colour map
REGION_COLOURS: Dict[str, str] = {
    "Gulf":     "#FF6584",
    "Interior": "#6C63FF",
    "Pacific":  "#43E97B",
    "Atlantic": "#F7B731",
}

#: Ship mode colour map
SHIP_MODE_COLOURS: Dict[str, str] = {
    "Standard Class": "#9AA0B9",
    "Second Class":   "#4FC3F7",
    "First Class":    "#6C63FF",
    "Same Day":       "#43E97B",
}

# ─────────────────────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def format_number(value: float, prefix: str = "", suffix: str = "", decimals: int = 2) -> str:
    """
    Format a numeric value with optional prefix/suffix and thousand separators.

    Args:
        value:    The numeric value to format.
        prefix:   String prepended to the formatted number (e.g. ``"$"``).
        suffix:   String appended to the formatted number (e.g. ``"%"``).
        decimals: Number of decimal places.

    Returns:
        A formatted string, e.g. ``"$1,234.56"``.

    Example:
        >>> format_number(1234567.89, prefix="$")
        '$1,234,567.89'
    """
    return f"{prefix}{value:,.{decimals}f}{suffix}"


def load_data(path: Path, date_cols: Optional[List[str]] = None) -> pd.DataFrame:
    """
    Load a CSV file into a DataFrame with optional date parsing.

    Args:
        path:      Absolute path to the CSV file.
        date_cols: List of column names to parse as dates.

    Returns:
        A :class:`pandas.DataFrame`.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
    """
    logger = get_logger(__name__)
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")
    logger.info("Loading data from %s", path)
    df = pd.read_csv(path, parse_dates=date_cols or [])
    logger.info("Loaded %d rows × %d columns", *df.shape)
    return df


def save_data(df: pd.DataFrame, path: Path, index: bool = False) -> None:
    """
    Save a DataFrame to CSV, creating parent directories as needed.

    Args:
        df:    DataFrame to save.
        path:  Destination file path.
        index: Whether to write the row index.
    """
    logger = get_logger(__name__)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=index)
    logger.info("Saved %d rows -> %s", len(df), path)


def compute_efficiency_score(
    delay_rate: pd.Series,
    normalised_lead_time: pd.Series,
    delay_weight: float = 0.6,
    lead_time_weight: float = 0.4,
) -> pd.Series:
    """
    Compute a composite Route Efficiency Score (higher = more efficient).

    The score is calculated as::

        efficiency = 1 - (delay_weight * delay_rate + lead_time_weight * norm_lt)

    Both inputs should be normalised to [0, 1].

    Args:
        delay_rate:           Series of delay rates (fraction, 0–1) per route.
        normalised_lead_time: Lead time normalised to [0, 1].
        delay_weight:         Weight for the delay component (default 0.6).
        lead_time_weight:     Weight for the lead-time component (default 0.4).

    Returns:
        A :class:`pandas.Series` of efficiency scores in [0, 1].
    """
    raw_score = delay_weight * delay_rate + lead_time_weight * normalised_lead_time
    efficiency = 1 - raw_score
    return efficiency.clip(0, 1)
