# FraudOps Backend

Backend service foundation for **FraudOps — Context-Aware Autonomous Fraud Investigation Platform**.

## Overview & Scope (Batch 1)

This repository contains the backend skeleton for the FraudOps platform established during **Batch 1 (Foundation & Backend Setup)**.

### What is Included in Batch 1
- Clean modular backend project structure (`app/api`, `app/schemas`, `app/services`, `app/rules`, `app/repositories`, `app/core`).
- FastAPI application entry point at `app.main:app`.
- Health check endpoint (`GET /health`).
- Environment configuration management via Pydantic Settings (`app.core.config`).
- Automated tests using `pytest` and `fastapi.testclient`.
- Dependency management in `requirements.txt`.

---

## Batch 2 — Domain Models & Extensible Rule Engine Foundation

Batch 2 establishes the core domain data contracts and extensible rule execution framework:

### What is Included in Batch 2
- **Domain & Contract Schemas**:
  - `Transaction` (strongly typed with `Decimal` amounts, timezone-aware UTC timestamps, coordinate validation).
  - `Merchant`, `OperatingHours`, and `MerchantStatistics` for business-context intelligence.
  - `CustomerContext` for historical behavioral baselines.
  - `PreviousTransaction` for velocity and impossible travel comparisons.
  - `FraudEvaluationContext` uniting all contextual signals into a single pass-through object.
  - `RuleResult` with structured machine-readable `evidence` mapping.
  - `FraudEvaluation` container for multi-rule results.
- **Rule Engine Architecture**:
  - `FraudRule`: Abstract base class enforcing the asynchronous `evaluate(transaction, context) -> RuleResult` interface.
  - `RuleRegistry`: In-memory registry with duplicate detection, interface validation, and enabled-state filtering.
  - `RuleEngine`: Decoupled orchestration engine executing registered rules, measuring execution durations, and gracefully capturing rule failures without crashing.
  - `ContextServiceInterface`: Formal abstraction boundary for context retrieval.
  - Extensive unit tests covering all domain models, registry behaviors, and engine extensibility.

---

## Batch 3 — Deterministic Fraud Rules Implementation

Batch 3 implements the core deterministic fraud detection rule layer:

### What is Included in Batch 3
- **Four Core Deterministic Rules**:
  - `TransactionVelocityRule`: Sliding rolling-window frequency evaluation (`[t - window, t]`, threshold check, deterministic score scaling).
  - `UnusualAmountRule`: Customer personal baseline anomaly detection using historical median (minimum history requirement, zero-baseline handling, multiplier ratio scoring).
  - `ImpossibleLocationRule`: Speed anomaly evaluation between consecutive geolocated transactions using local Haversine distance formula (Earth radius 6371 km, strict speed threshold comparison).
  - `MerchantContextRule`: Business-context risk evaluation comparing transaction amount against merchant statistical distributions (`p95` -> `p99` -> `p50` -> `average` fallback hierarchy) and operating hours verification (supporting daytime and overnight ranges).
- **Shared Deterministic Helpers (`app.rules.helpers`)**:
  - `haversine_distance_km`: Great-circle geographical distance calculation.
  - `calculate_median`: Monetary median calculation preserving `Decimal` precision.
  - `score_to_severity`: Standardized rule-level signal mapping to `Severity` enum.
  - `is_within_operating_hours`: Timezone-aware operating hours evaluation.
- **Rule Registration Factory (`create_default_rule_registry`)**:
  - Instantiates isolated `RuleRegistry` pre-populated with all 4 deterministic rules.
- **Comprehensive Test Suite**:
  - 116 passing tests covering normal cases, boundary values, missing/insufficient data handling, deterministic repeatability, contextual differentiation, and integration through `RuleEngine`.

---

## Batch 4 — Risk Scoring & Aggregation Engine

Batch 4 implements the case-level synthesis layer:

### What is Included in Batch 4
- **RiskEngine (`app.risk.engine.RiskEngine`)**:
  - Consumes structured `RuleResult` sequences and aggregates them into a unified `FraudEvaluation`.
  - Normalizes weighted score over available successful rules (`normalized_score = sum(score_i * weight_i) / available_weight`).
  - Resilient signal handling: failed rules (`status == ERROR`) are excluded from available weight rather than falsely assumed clean (`score = 0`).
  - Operational completeness statuses: `COMPLETE` (100% coverage), `PARTIAL` (< 100% coverage), `NO_VALID_SIGNALS` (all rules failed; risk score is `None`, not 0).
  - Categorical case risk levels: `LOW` (0-39), `MEDIUM` (40-69), `HIGH` (70-89), `CRITICAL` (90-100).
  - Explicit input validation: rejects empty rule sets, duplicate rule results, unknown unconfigured rules, and out-of-range scores.
- **RiskConfiguration (`app.risk.config.RiskConfiguration`)**:
  - Configurable rule weights (`transaction_velocity: 0.20`, `unusual_amount: 0.25`, `impossible_location: 0.30`, `merchant_context: 0.25`).
  - Strict validation: exact sum 1.00, non-negative weights, Batch 3 rules validation.
- **Comprehensive Test Suite**:
  - 174 total passing tests (58 dedicated to Batch 4 risk engine, configuration, helpers, and end-to-end integration).

### What is Intentionally NOT Implemented Yet (Deferred to Later Batches)
- **Context Fetching**: Database queries and context enrichment logic belong to later batches once Member 4 establishes PostgreSQL tables.
- **Agent Orchestration**: LangGraph, OpenAI LLM integration, and investigation agents belong to **Member 2**.

---

## Prerequisites

- **Python**: Python 3.12+ (tested with Python 3.14)
- **pip**: Package installer for Python

---

## Local Setup & Run Guide

### 1. Navigate to the backend directory
```bash
cd backend
```

### 2. Create and activate a virtual environment

On Windows (Command Prompt):
```cmd
python -m venv .venv
.venv\Scripts\activate
```

On Windows (PowerShell):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

On Linux / macOS:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment variables (optional for local defaults)
Copy the template from the root directory or configure `.env`:
```bash
# In the repository root:
cp .env.example .env
```
Default fallback values (`APP_ENV=development`, `APP_PORT=8000`) will be used if `.env` is omitted.

### 5. Start the FastAPI development server
From the `backend/` directory:
```bash
uvicorn app.main:app --reload
```

The application will start on `http://127.0.0.1:8000`.

### 6. Verify the Health Check Endpoint
Send an HTTP GET request:
```bash
curl http://127.0.0.1:8000/health
```
Expected response:
```json
{"status": "ok"}
```
HTTP status: `200 OK`.

Interactive API documentation (Swagger UI) is accessible at:
```
http://127.0.0.1:8000/docs
```

---

## Running Tests

Execute the test suite from the `backend/` directory:
```bash
pytest
```
To run with verbose output:
```bash
pytest -v
```
