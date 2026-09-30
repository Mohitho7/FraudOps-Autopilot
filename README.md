# FraudOps — Context-Aware Autonomous Fraud Investigation Platform

FraudOps is a fraud detection and investigation platform in development. The current implementation is Member 1's deterministic backend: transaction context, fraud rules, risk evaluation, and a handoff contract. Agent investigation, persistent storage, and the reviewer console are planned work, not implemented features.

---

## Design Direction

Risk evaluation is deterministic; any future agentic investigation layer is intended to remain separate from fraud-rule evaluation. Consequential actions are intended to remain under human reviewer authority.

---

## Team Ownership

FraudOps is developed across four functional verticals:

| Role                             | Member                   | Responsibilities                                                                                                                         |
| -------------------------------- | ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------- |
| **Core Fraud Engine & Backend**  | **Member 1** _(Current)_ | FastAPI foundation, transaction ingestion, context enrichment, extensible rule engine, risk scoring, evaluation APIs, handoff contracts. |
| **Agentic Investigation System** | **Member 2**             | LangGraph investigation orchestrator, behavioral/relationship analysis, evidence builder, recommendation agent.                          |
| **Frontend & Reviewer Console**  | **Member 3**             | React console, investigation workbench, graph visualization, reviewer decisions.                                                         |
| **Data, Cloud & Infrastructure** | **Member 4**             | PostgreSQL models, SQLAlchemy persistence, Alembic migrations, AWS SES/SNS, Docker environment, system QA.                               |

---

## Current and Planned Technologies

- **Implemented backend**: Python, FastAPI, Pydantic, deterministic rule engine, risk engine
- **Implemented testing**: pytest, pytest-asyncio, httpx
- **Planned for other members**: LangGraph/OpenAI investigation, React reviewer console, PostgreSQL persistence with SQLAlchemy/Alembic, AWS notifications
- Docker Compose defines a local PostgreSQL service; backend persistence and database models are not implemented.

---

## Repository Structure

```
FraudOps-Autopilot/
│
├── backend/                  # FastAPI backend and Rule Engine
│   ├── app/
│   │   ├── api/              # API route controllers
│   │   ├── core/             # Configuration and settings
│   │   ├── repositories/     # Data persistence boundaries
│   │   ├── rules/            # Deterministic fraud rules
│   │   ├── schemas/          # Pydantic schemas and contracts
│   │   ├── services/         # Application and domain services
│   │   ├── __init__.py
│   │   └── main.py           # FastAPI entry point
│   ├── tests/                # Automated pytest suite
│   ├── requirements.txt      # Backend Python dependencies
│   └── README.md             # Backend setup and documentation
│
├── frontend/                 # Planned reviewer console (Member 3)
├── data/                     # Data resources
├── scripts/                  # Project scripts
├── docs/                     # Technical specifications and contracts
│   └── contracts/            # Inter-member interface contracts
├── documention/              # Primary design and architecture specifications
│
├── .env.example              # Environment variables template
├── .gitignore                # Git ignore configuration
├── docker-compose.yml        # Local infrastructure services
└── README.md                 # Project root documentation
```

---

## Completed: Member 1 Core Fraud Engine

- Batch 1: backend foundation
- Batch 2 and Batch 2 hardening: domain models and rule-engine foundation
- Batch 3: transaction velocity, unusual amount, impossible location, and merchant-context rules
- Batch 4: risk engine
- F-01 future-dated transaction correction; F-02 custom-rule flexibility cleanup; F-03 partial-evaluation handoff clarification; F-04 `ROUND_HALF_UP` documentation and test cleanup
- Verified backend tests: 227 passed, 0 failed, 0 skipped (1 deprecation warning)

## Next / Planned

- Batch 5 has not started.
- Member 2: agentic investigation implementation
- Member 3: frontend reviewer console
- Member 4: database persistence, migrations, and cloud notifications

---

## How to Run the Backend Locally

### 1. Enter the backend directory

```bash
cd backend
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv
# On Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# On Linux / macOS:
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the application

```bash
uvicorn app.main:app --reload
```

### 5. Verify the health endpoint

```bash
curl http://127.0.0.1:8000/health
```

Response:

```json
{ "status": "ok" }
```

### 6. Run automated tests

```bash
pytest
```
