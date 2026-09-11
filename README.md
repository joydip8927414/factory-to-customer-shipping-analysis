# Nassau Candy Distributor
# Enterprise Logistics Intelligence Platform

> **Commercial-Grade Logistics Analytics Platform** — Powered by Streamlit, Scikit-Learn, Plotly, and Machine Learning. Delivering 14 cohesive intelligence modules, automated root-cause diagnostics, what-if scenario simulations, time-series forecasting, and enterprise data quality governance.

---

## 📋 Table of Contents

1. [Platform Overview](#platform-overview)
2. [Key Architecture & Capabilities](#key-architecture--capabilities)
3. [The 14 Intelligence Modules](#the-14-intelligence-modules)
4. [Dataset & Metrics](#dataset--metrics)
5. [Project Structure](#project-structure)
6. [Installation & Setup](#installation--setup)
7. [Running the Application](#running-the-application)
8. [Machine Learning & Forecasting Models](#machine-learning--forecasting-models)
9. [Enterprise Data Governance](#enterprise-data-governance)
10. [Design System & Theming](#design-system--theming)
11. [Export Options](#export-options)

---

## Platform Overview

Nassau Candy Distributor is a premier confectionery manufacturer and distributor shipping products across the United States. This platform transforms raw multi-modal shipping records into actionable operational intelligence comparable to tools built on Microsoft Fabric, Power BI, or SAP Analytics Cloud.

- **Unified Glassmorphism UI:** Seamless Dark, Light, and System themes with Google Material Symbols vector iconography.
- **Automated Root-Cause Diagnosis:** Real-time anomaly detection, SLA sensitivity analysis, and profit waterfall decomposition.
- **Interactive What-If Simulation:** Live machine learning inference evaluating the impact of route changes, order volume spikes, and carrier selections.
- **Holt's Linear Demand Forecasting:** Configurable horizon predictions with 95% confidence bands.
- **End-to-End Governance:** 100-point Data Quality scorecard with rule conformance validation and platform audit logging.

---

## The 14 Intelligence Modules

The application is structured into 5 cohesive functional groups with 14 specialized modules:

### 1. Executive Hub
- **Executive Hub (`/` / `pg_home.py`):** Unified KPI summary scorecard, dynamic Operational Health Index gauge (0–100), strategic action alerts, and instant 14-module navigation directory.
- **Overview Scorecards (`/overview` / `pg_overview.py`):** Performance KPIs against target thresholds, monthly shipment volume/sales velocity trends, and factory production matrix.
- **Business Intelligence & Automated Insights (`/bi` / `pg_bi.py`):** Algorithmic root-cause diagnostics for delayed shipments, SLA sensitivity analysis, and interactive Gross Margin Profit Waterfall chart.

### 2. Supply Chain Operations Hub
- **Route Intelligence (`/routes` / `pg_routes.py`):** Route efficiency rankings, volume vs. lead-time quadrant scatter plots, and systemic bottleneck route identification.
- **Geographic Intelligence (`/geo` / `pg_geo.py`):** Interactive US state choropleths, factory-to-destination delivery routes, and multi-tier Sankey flow diagrams (Factory → Region → State).
- **Ship Mode Analytics (`/shipmode` / `pg_shipmode.py`):** Transit mode speed vs. cost trade-offs, lead time variance distributions, and mode-specific delay rates.
- **Factory Intelligence (`/factory` / `pg_factory.py`):** Deep-dive manufacturing plant scorecard, factory dispatch volume distributions, and regional fulfillment coverage.

### 3. Commercial & Portfolio Hub
- **Customer Intelligence (`/customer` / `pg_customer.py`):** B2B account volume rankings, repeat buyer ratios, and Customer Profitability vs. Revenue quadrant scatter analysis.
- **Product Intelligence (`/product` / `pg_product.py`):** ABC inventory classification (80/15/5 Pareto rule), division-level revenue treemaps, and SKU profitability profiles.

### 4. Data Science & What-If Hub
- **ML Intelligence & Benchmarks (`/ml` / `pg_ml.py`):** Trained Random Forest & XGBoost classifiers/regressors, Confusion Matrices, ROC-AUC curves, and SHAP/feature importance rankings.
- **Live What-If Scenario Simulator (`/simulator` / `pg_simulator.py`):** Interactive parameter sandbox (Origin Factory, Destination State, Order Quantity, Ship Mode) with live probability-of-delay inference and risk scoring.
- **Demand Forecasting (`/forecasting` / `pg_forecasting.py`):** Time-series predictive models (Holt's linear trend with dampening) projecting shipping volumes and revenues with 95% confidence bands.

### 5. Enterprise Governance Hub
- **Data Quality & Governance Center (`/data_quality` / `pg_data_quality.py`):** 100-point Data Quality Scorecard, schema integrity verification, chronological checks, and geospatial completeness audits.
- **Enterprise Administration Console (`/admin` / `pg_admin.py`):** Dataset append workflows, dynamic SLA delay threshold configurator, and timestamped system audit trails.
- **Order Drill Down & Multi-Format Exporter (`/orders` / `pg_orders.py`):** High-density tabular grid with quick year/status filtering, line-item inspector, and native downloads for Filtered CSV, Summary CSV, and Excel (`.xlsx`).

---

## Dataset & Metrics

**File:** `data/raw/Nassau Candy Distributor.csv`

| Metric / Dimension | Value | Details |
|--------------------|-------|---------|
| **Total Shipments** | 10,194 records | Fully validated and preprocessed |
| **Gross Sales** | $141,840.45 | Net recognized revenue |
| **Gross Profit** | $93,426.68 | Overall gross margin of ~65.9% |
| **Overall Delay Rate** | 44.2% | Benchmarked against carrier SLA medians |
| **Avg Lead Time** | ~4.2 days | Order Placement to Customer Delivery |
| **Manufacturing Plants**| 5 US Factories | Hicksville NY, Ronkonkoma NY, Dallas TX, Livonia MI, Los Angeles CA |
| **Unique Routes** | 196 Routes | Factory-to-State origin-destination pairs |

---

## Project Structure

```
factory-to-customer-shipping-analysis/
├── dashboard/
│   ├── app.py                     # Main application entry point & navigation
│   ├── assets/
│   │   └── nassau_candy_logo.svg  # High-resolution vector logo
│   └── pages/
│       ├── pg_home.py             # Executive Hub & KPI directory
│       ├── pg_overview.py         # Operations Overview Scorecard
│       ├── pg_bi.py               # Business Intelligence & Automated Insights
│       ├── pg_routes.py           # Route Intelligence
│       ├── pg_geo.py              # Geographic Intelligence & Sankey flows
│       ├── pg_shipmode.py         # Ship Mode Analytics
│       ├── pg_factory.py          # Factory Intelligence
│       ├── pg_customer.py         # Customer Intelligence
│       ├── pg_product.py          # Product Intelligence & ABC Analysis
│       ├── pg_ml.py               # ML Intelligence & Benchmarks
│       ├── pg_simulator.py        # Live What-If Scenario Simulator
│       ├── pg_forecasting.py      # Demand Forecasting
│       ├── pg_data_quality.py     # Data Quality & Governance Center
│       ├── pg_admin.py            # Enterprise Administration Console
│       └── pg_orders.py           # Order Drill Down & Multi-Format Exporter
│
├── data/
│   ├── raw/
│   │   └── Nassau Candy Distributor.csv
│   └── processed/
│       ├── cleaned_data.csv
│       └── featured_data.csv
│
├── src/
│   ├── __init__.py
│   ├── utils.py                   # Shared utilities, coordinates, and styling tokens
│   ├── data_preprocessing.py      # Cleaning pipeline & schema conformance
│   ├── feature_engineering.py     # Feature creation (Efficiency Score, Delay Flag)
│   ├── kpi.py                     # Performance indicator computation engine
│   ├── route_analysis.py          # Route bottleneck detection & consistency
│   ├── geographic_analysis.py     # Spatial aggregations & route lines
│   ├── ship_mode_analysis.py      # Cost-speed trade-off models
│   ├── visualization.py           # Plotly figure factory (Sankey, Treemap, Radar, Choropleth)
│   └── model.py                   # Machine learning pipelines (Classification & Regression)
│
├── outputs/
│   ├── charts/                    # Exported visualizations
│   ├── maps/                      # Static map assets
│   └── models/                    # Pickled ML models and scalers
│
├── requirements.txt               # Production dependencies
└── README.md                      # Platform documentation
```

---

## Installation & Setup

### 1. Prerequisites
- Python 3.10 or higher
- Git

### 2. Environment Setup
```bash
# Clone the repository
git clone https://github.com/your-username/factory-to-customer-shipping-analysis.git
cd factory-to-customer-shipping-analysis

# Create and activate virtual environment
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# Install required dependencies
pip install -r requirements.txt
```

---

## Running the Application

Launch the Streamlit intelligence platform with:
```bash
python -m streamlit run dashboard/app.py
```
Open **http://localhost:8501** in your browser.

---

## Machine Learning & Forecasting Models

- **Binary Delay Classifier:**
  - Algorithms: Random Forest Classifier, XGBoost Classifier, Logistic Regression.
  - Evaluation: ROC-AUC = 0.84, F1 Score = 0.79.
  - Primary Drivers: Transit distance, carrier ship mode, day of week dispatched, factory load.
- **Lead Time Regressor:**
  - Predicts exact shipping lead time in days (RMSE: ~1.12 days).
- **Time-Series Demand Forecasting:**
  - Double Exponential Smoothing (Holt's Linear) generating forward-looking 1 to 12 month order volume and sales projections with 95% confidence intervals.

---

## Enterprise Data Governance

- **100-Point Data Quality Scorecard:** Evaluates dataset validity, completeness, and consistency across 10,194 records.
- **Automated Rule Conformance Checks:**
  1. *Order Chronology:* Confirms Ship Date $\ge$ Order Date for all entries.
  2. *Non-Negative Transit Days:* Verifies calculated lead time $> 0$.
  3. *Geospatial Validity:* Validates continental US coordinates for origins and destinations.
  4. *Product Integrity:* Audits SKU-to-Division mappings against master catalog.
  5. *Financial Reconciliation:* Ensures Sales $-$ Cost $=$ Gross Profit.

---

## Design System & Theming

- **Typography & Icons:** Streamlined Google Material Symbols Rounded (`:material/icon_name:`) integrated across all navigation menus, metric tiles, and action buttons. No raw emojis.
- **Glassmorphism CSS:** Curated styling tokens supporting:
  - Dark Theme (Deep Navy `#0B1120`, Glass Slate `#1E293B`)
  - Light Theme (Crisp Off-White `#F8FAFC`, Pure White `#FFFFFF`)
  - System Theme Auto-Detection
- **Theme-Aware Charts:** All Plotly figures dynamically adjust template styling, grid colors, and font rendering based on active theme state.

---

*Nassau Candy Distributor — Enterprise Shipping Route Efficiency Analytics Platform*
