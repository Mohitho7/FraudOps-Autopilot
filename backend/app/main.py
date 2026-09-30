"""
FraudOps Backend Application Entry Point.
"""

from fastapi import FastAPI
from app.api.v1.evaluations import router as evaluations_router
from app.core.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    description="FraudOps — Context-Aware Autonomous Fraud Investigation Platform",
    version="0.1.0",
)

# Register API routers
app.include_router(evaluations_router)


@app.get("/health", status_code=200)
def health_check() -> dict:
    """
    Health check endpoint returning system status.
    """
    return {"status": "ok"}

