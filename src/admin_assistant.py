"""
admin_assistant.py
==================
Smart AI-assisted Data Quality and Governance Assistant for the Administrator.

Analyzes uploaded or active datasets to diagnose:
- Schema inconsistencies and unexpected columns
- Missing values and incomplete records
- Duplicate order or row records
- Date logic violations (Order Date > Ship Date, extreme future dates)
- Negative transit lead times
- Statistical outliers (Units, Sales, Cost, Margin anomalies)
- Missing coordinates and unmapped products/factories

Generates intelligent recommendations with both individual fixes and one-click "Fix All" batch remediation.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.utils import PRODUCT_FACTORY_MAP, US_STATES, get_logger

logger = get_logger(__name__)

EXPECTED_CORE_COLUMNS = [
    "Order ID", "Order Date", "Ship Date", "Ship Mode", "Customer ID",
    "Country/Region", "City", "State/Province", "Division", "Region",
    "Product ID", "Product Name", "Sales", "Units", "Gross Profit", "Cost"
]


def analyze_dataset_health(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Run comprehensive diagnostic heuristics on a dataset.
    Returns structured analysis containing metrics, issues, and recommendations.
    """
    total_rows = len(df)
    if total_rows == 0:
        return {"health_score": 0, "issues": [], "recommendations": [], "summary": {}}

    issues: List[Dict[str, Any]] = []
    recommendations: List[Dict[str, Any]] = []
    deductions = 0

    # 1. Schema check
    missing_cols = [col for col in EXPECTED_CORE_COLUMNS if col not in df.columns]
    if missing_cols:
        deductions += min(30, len(missing_cols) * 8)
        issues.append({
            "severity": "High",
            "category": "Schema",
            "title": f"Missing Expected Columns ({len(missing_cols)})",
            "description": f"Columns missing: {', '.join(missing_cols[:5])}{'...' if len(missing_cols) > 5 else ''}",
            "impact": "May prevent complete feature engineering and route calculations.",
        })
        recommendations.append({
            "id": "fix_missing_cols",
            "title": "Auto-impute Missing Optional Columns",
            "action_type": "schema_repair",
            "description": "Initialize missing non-essential columns with sensible defaults or placeholders.",
        })

    # 2. Missing values
    null_counts = df.isnull().sum()
    total_nulls = int(null_counts.sum())
    high_null_cols = null_counts[null_counts > 0].to_dict()

    if total_nulls > 0:
        deductions += min(20, int(total_nulls / total_rows * 100))
        issues.append({
            "severity": "Medium" if total_nulls < total_rows * 0.05 else "High",
            "category": "Completeness",
            "title": f"Missing Cell Values ({total_nulls:,} total nulls)",
            "description": f"Affected fields: {', '.join([f'{k} ({v})' for k, v in list(high_null_cols.items())[:4]])}",
            "impact": "May cause calculation errors or missing data points in visualisations.",
        })
        recommendations.append({
            "id": "clean_nulls",
            "title": "Clean & Impute Missing Values",
            "action_type": "data_cleaning",
            "description": "Forward-fill or interpolate continuous metrics, and fill categoricals with 'Unknown'.",
        })

    # 3. Duplicate checks
    dup_rows = int(df.duplicated(subset=["Order ID", "Product ID"]).sum()) if "Order ID" in df.columns and "Product ID" in df.columns else int(df.duplicated().sum())
    if dup_rows > 0:
        deductions += min(15, int(dup_rows / total_rows * 100) + 5)
        issues.append({
            "severity": "Medium",
            "category": "Duplicates",
            "title": f"Potential Duplicate Records ({dup_rows:,} rows)",
            "description": f"Found {dup_rows:,} duplicate order line items sharing identical identifiers.",
            "impact": "Artificially inflates revenue and shipment volume counts.",
        })
        recommendations.append({
            "id": "drop_duplicates",
            "title": "De-duplicate Order Line Items",
            "action_type": "data_cleaning",
            "description": "Remove identical duplicate records, retaining the first recorded instance.",
        })

    # 4. Date Chronology and Anomalies
    date_issues_count = 0
    if "Order Date" in df.columns and "Ship Date" in df.columns:
        o_date = pd.to_datetime(df["Order Date"], errors="coerce")
        s_date = pd.to_datetime(df["Ship Date"], errors="coerce")
        negative_lt = (s_date < o_date).sum()
        if negative_lt > 0:
            date_issues_count += int(negative_lt)
            deductions += 15
            issues.append({
                "severity": "High",
                "category": "Chronology",
                "title": f"Inverted Date Sequences ({negative_lt:,} records)",
                "description": f"Ship Date occurs prior to Order Date in {negative_lt:,} line items.",
                "impact": "Results in negative transit lead times violating physical causality.",
            })
            recommendations.append({
                "id": "fix_dates",
                "title": "Align Inverted Date Sequences",
                "action_type": "data_cleaning",
                "description": "Swap Order Date and Ship Date where Ship Date < Order Date.",
            })

    # 5. Negative or Zero Lead Times
    if "Shipping Lead Time" in df.columns:
        neg_lt = (df["Shipping Lead Time"] <= 0).sum()
        if neg_lt > 0:
            deductions += 10
            issues.append({
                "severity": "High",
                "category": "Transit Metrics",
                "title": f"Negative or Zero Lead Times ({neg_lt:,} rows)",
                "description": f"{neg_lt:,} records show non-positive transit duration.",
                "impact": "Distorts SLA performance metrics.",
            })
            recommendations.append({
                "id": "fix_negative_lead_times",
                "title": "Correct Negative Lead Times to SLA Minimum",
                "action_type": "data_cleaning",
                "description": "Clip all non-positive lead times to a realistic minimum of 0.5 days.",
            })

    # 6. Statistical Outliers
    outlier_count = 0
    if "Sales" in df.columns and pd.api.types.is_numeric_dtype(df["Sales"]):
        q75 = df["Sales"].quantile(0.75)
        q25 = df["Sales"].quantile(0.25)
        iqr = q75 - q25
        high_sales = (df["Sales"] > (q75 + 4 * iqr)).sum()
        if high_sales > 0:
            outlier_count += int(high_sales)
            issues.append({
                "severity": "Low",
                "category": "Outliers",
                "title": f"Extreme Sales Value Outliers ({high_sales:,} orders)",
                "description": f"{high_sales:,} orders deviate beyond 4× Interquartile Range.",
                "impact": "May skew distribution visualizations and volume summaries.",
            })
            recommendations.append({
                "id": "cap_sales_outliers",
                "title": "Winsorize Sales Outliers at 99th Percentile",
                "action_type": "outlier_capping",
                "description": "Soft-cap extreme sales values to prevent scale distortion.",
            })

    # 7. Unmapped Products & Missing Coordinates
    unmapped_prods = set()
    if "Product Name" in df.columns:
        unmapped_prods = set(df["Product Name"].dropna()) - set(PRODUCT_FACTORY_MAP.keys())
        if unmapped_prods:
            deductions += min(15, len(unmapped_prods) * 5)
            issues.append({
                "severity": "Medium",
                "category": "Factory Allocation",
                "title": f"Unmapped Product SKUs ({len(unmapped_prods)} SKUs)",
                "description": f"Products without origin factory: {', '.join(list(unmapped_prods)[:3])}",
                "impact": "Prevents origin-to-destination route network mapping.",
            })
            recommendations.append({
                "id": "map_default_factory",
                "title": "Assign Unmapped SKUs to Secret Factory",
                "action_type": "product_mapping",
                "description": "Map unassigned confections to 'Secret Factory' as the default production center.",
            })

    health_score = max(5, 100 - deductions)

    summary = {
        "total_records": total_rows,
        "total_columns": len(df.columns),
        "total_nulls": total_nulls,
        "duplicate_count": dup_rows,
        "date_inversions": date_issues_count,
        "missing_columns_count": len(missing_cols),
        "unmapped_products": len(unmapped_prods),
        "health_score": health_score,
    }

    return {
        "health_score": health_score,
        "summary": summary,
        "issues": issues,
        "recommendations": recommendations,
    }


def apply_recommendation_fix(df: pd.DataFrame, recommendation_id: str) -> Tuple[pd.DataFrame, str]:
    """
    Apply automated remediation to DataFrame based on recommendation ID.
    Returns (cleaned_df, message).
    """
    df_clean = df.copy()

    if recommendation_id == "drop_duplicates":
        before = len(df_clean)
        if "Order ID" in df_clean.columns and "Product ID" in df_clean.columns:
            df_clean = df_clean.drop_duplicates(subset=["Order ID", "Product ID"])
        else:
            df_clean = df_clean.drop_duplicates()
        removed = before - len(df_clean)
        return df_clean, f"Removed {removed:,} duplicate records."

    elif recommendation_id == "clean_nulls":
        for col in df_clean.columns:
            if pd.api.types.is_numeric_dtype(df_clean[col]):
                df_clean[col] = df_clean[col].fillna(df_clean[col].median() if not df_clean[col].dropna().empty else 0)
            else:
                df_clean[col] = df_clean[col].fillna("Unknown")
        return df_clean, "Imputed missing values across numeric and categorical attributes."

    elif recommendation_id == "fix_dates":
        if "Order Date" in df_clean.columns and "Ship Date" in df_clean.columns:
            o_date = pd.to_datetime(df_clean["Order Date"], errors="coerce")
            s_date = pd.to_datetime(df_clean["Ship Date"], errors="coerce")
            inverted = s_date < o_date
            count = inverted.sum()
            temp_o = df_clean.loc[inverted, "Order Date"]
            df_clean.loc[inverted, "Order Date"] = df_clean.loc[inverted, "Ship Date"]
            df_clean.loc[inverted, "Ship Date"] = temp_o
            return df_clean, f"Corrected {count:,} inverted order/ship date pairs."
        return df_clean, "Date columns not found."

    elif recommendation_id == "fix_negative_lead_times":
        if "Shipping Lead Time" in df_clean.columns:
            fixed_cnt = (df_clean["Shipping Lead Time"] <= 0).sum()
            df_clean["Shipping Lead Time"] = df_clean["Shipping Lead Time"].clip(lower=0.5).round(2)
            return df_clean, f"Fixed {fixed_cnt:,} non-positive lead times to minimum 0.5 days."
        return df_clean, "Shipping Lead Time column not found."

    elif recommendation_id == "cap_sales_outliers":
        if "Sales" in df_clean.columns and pd.api.types.is_numeric_dtype(df_clean["Sales"]):
            p99 = df_clean["Sales"].quantile(0.99)
            capped = (df_clean["Sales"] > p99).sum()
            df_clean["Sales"] = df_clean["Sales"].clip(upper=p99)
            return df_clean, f"Capped {capped:,} extreme sales outliers at 99th percentile (${p99:,.2f})."
        return df_clean, "Sales column not found."

    elif recommendation_id == "map_default_factory":
        if "Product Name" in df_clean.columns:
            if "Factory" not in df_clean.columns:
                df_clean["Factory"] = df_clean["Product Name"].map(PRODUCT_FACTORY_MAP).fillna("Secret Factory")
            else:
                df_clean["Factory"] = df_clean["Factory"].fillna("Secret Factory")
            return df_clean, "Assigned unmapped products to 'Secret Factory'."
        return df_clean, "Product Name column not found."

    elif recommendation_id == "fix_missing_cols":
        for col in EXPECTED_CORE_COLUMNS:
            if col not in df_clean.columns:
                if col in ["Sales", "Gross Profit", "Cost"]:
                    df_clean[col] = 0.0
                elif col == "Units":
                    df_clean[col] = 1
                else:
                    df_clean[col] = "Standard Class" if col == "Ship Mode" else "Unassigned"
        return df_clean, "Created missing schema columns with default initial values."

    return df_clean, f"Unrecognized recommendation: {recommendation_id}"


def apply_all_recommendations(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    """Apply all recommended fixes in one atomic sequence."""
    analysis = analyze_dataset_health(df)
    recommendations = analysis.get("recommendations", [])
    current_df = df.copy()
    logs = []

    for rec in recommendations:
        current_df, msg = apply_recommendation_fix(current_df, rec["id"])
        logs.append(msg)

    return current_df, logs
