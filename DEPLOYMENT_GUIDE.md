# 🚀 Nassau Candy Logistics Platform — Production Deployment Runbook

Comprehensive production verification, architecture guide, and operational manual for deploying the **Logistics Analytics & AI Platform** (`:8501`) and the **Developer IAM & Control Portal** (`:8600`).

---

## 📌 Architecture & Dual-Service Overview

```
+─────────────────────────────────────────────────────────────────────────────+
|                         Enterprise Deployment Topology                      |
+─────────────────────────────────────────────────────────────────────────────+
                                      │
            ┌─────────────────────────┴─────────────────────────┐
            │                                                   │
            ▼                                                   ▼
┌───────────────────────────────┐               ┌───────────────────────────────┐
│  Logistics Analytics Platform │               │  Developer IAM & Control Hub  │
│        (Port 8501)            │               │        (Port 8600)            │
│  dashboard/app.py             │               │  developer_portal/dev_app.py  │
├───────────────────────────────┤               ├───────────────────────────────┤
│ • 15 Analytics Modules        │               │ • 3-Layer Security Hierarchy  │
│ • Executive Hub & KPIs        │               │ • Key Management & Assignment │
│ • Route & Geo Intelligence    │               │ • Trusted Workstation Registry│
│ • ML Delay Prediction (XGB)   │               │ • Registration ID Authority   │
│ • Admin Ingestion & Governance│               │ • Database Engine & VACUUM    │
└──────────────┬────────────────┘               └───────────────┬───────────────┘
               │                                                │
               └───────────────────────┬────────────────────────┘
                                       ▼
                       ┌───────────────────────────────┐
                       │  Unified Database & Datasets  │
                       │  • data/admin/logistics.db    │
                       │  • featured_data.csv (10,194) │
                       │  • cleaned_data.csv (10,194)  │
                       └───────────────────────────────┘
```

---

## 🔑 Operational Credentials & Access Keys

### 1. Logistics Analytics Platform (`http://localhost:8501`)
| Role | Username | Password | Purpose |
| :--- | :--- | :--- | :--- |
| **Chief Admin** | `admin` | `ChangeMeAdmin2026!` | Full administrative access, dataset upload/replace, user control, ML retraining |
| **Default Registration Key** | `REG-ADMIN-NASSAU-9901` | *(Single-use token)* | Used to onboard new administrators via the Register screen |
| **Additional Spare Keys** | `REG-ADMIN-NASSAU-9902`, `REG-ADMIN-NASSAU-9903` | *(Single-use tokens)* | Pre-seeded for IT / operations onboarding |

### 2. Developer IAM & Control Portal (`http://localhost:8600`)
| Layer | Identity / Credential | Value |
| :--- | :--- | :--- |
| **Layer 1: Root Owner Username** | Username / Email | `joydip_icy` (or `joydip_icy@nassaucandy.com`) |
| **Layer 1: Root Owner Password** | Password | `ChangeMeOnFirstLogin2026!` |
| **Layer 2: Master Management Key** | Cryptographic Key | `ChangeMeMasterKey2026!` |
| **Standard Developer** | Username / Password | `developer` / `ChangeMeDev2026!` |

---

## 🛠️ Launch & Deployment Methods

### Option A: Local / Virtual Machine Launch (Windows & Linux)
To launch both services concurrently with graceful shutdown handling:
```bash
python scripts/start_servers.py
```

### Option B: Docker Container Deployment
```bash
# 1. Build and run via Docker Compose
docker-compose up -d --build

# 2. Inspect logs
docker-compose logs -f

# 3. Stop containers
docker-compose down
```

### Option C: Standalone Process Execution
If running as systemd services or separate screen/tmux sessions:
```bash
# Service 1: Logistics Analytics Platform
python -m streamlit run dashboard/app.py --server.port 8501 --server.headless true

# Service 2: Developer IAM & Control Portal
python -m streamlit run developer_portal/dev_app.py --server.port 8600 --server.headless true
```

---

## 🔍 Pre-Flight Verification & Health Checks

Run the automated test suite to ensure 100% test passing:
```bash
python -m unittest discover tests
```
*Expected result:* `Ran 37 tests ... OK`

To re-seed or vacuum optimize the database at any time:
```bash
python scripts/seed_production_db.py
```
