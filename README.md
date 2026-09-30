# FraudOps — Context-Aware Autonomous Fraud Investigation Platform

FraudOps is a fraud detection and investigation platform in development. The repository contains Member 1's deterministic backend and Member 3's React reviewer console. Agent investigation, persistent storage, and cloud integrations remain planned work.

## Team Ownership

| Member   | Area                              | Current status                                    |
| -------- | --------------------------------- | ------------------------------------------------- |
| Member 1 | Core fraud engine and backend     | Batches 1-4 and F-01 through F-04 completed       |
| Member 2 | Agent investigation               | Planned; not implemented in this repository state |
| Member 3 | Reviewer console                  | Frontend implementation is present                |
| Member 4 | Database and cloud infrastructure | Persistence and cloud integrations are planned    |

## Technology

- Backend: Python, FastAPI, Pydantic, deterministic rules, and risk evaluation
- Frontend: React, TypeScript, and Vite
- Tests: pytest, pytest-asyncio, and httpx
- Planned: LangGraph/OpenAI investigation, database persistence with SQLAlchemy/Alembic, and AWS notifications
- Docker Compose defines a local PostgreSQL service; backend database models and persistence are not implemented.

---

## Repository Structure

```
FraudOps-Autopilot/
│
├── backend/                  # FastAPI backend and deterministic fraud engine
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
├── frontend/                 # Member 3 reviewer console
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
