"""
Integration tests for Fraud Evaluation API (Batch 6).
Covers POST /api/v1/fraud/evaluations and GET /api/v1/fraud/evaluations/{transaction_id}.
Verifies end-to-end execution through real deterministic rules and risk engine.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import (
    default_context_provider,
    default_evaluation_store,
    get_context_provider,
    get_evaluation_store,
    get_fraud_evaluation_service,
)
from app.main import app
from app.repositories.context_provider import InMemoryContextProvider
from app.repositories.evaluation_store import InMemoryEvaluationStore
from app.risk.config import RiskConfiguration
from app.risk.engine import RiskEngine
from app.rules.base import FraudRule
from app.rules.engine import RuleEngine
from app.rules.registry import RuleRegistry, create_default_rule_registry
from app.schemas.customer import CustomerContext
from app.schemas.merchant import Merchant, MerchantStatistics, OperatingHours
from app.schemas.transaction import PreviousTransaction
from app.services.context_service import ContextService
from app.services.fraud_evaluation_service import FraudEvaluationService



@pytest.fixture(autouse=True)
def reset_dependencies():
    """Reset shared default providers and clean app dependency overrides before each test."""
    app.dependency_overrides.clear()
    default_context_provider.clear()
    default_evaluation_store.clear()
    yield
    app.dependency_overrides.clear()
    default_context_provider.clear()
    default_evaluation_store.clear()


@pytest.fixture
def client():
    return TestClient(app)


def sample_transaction_payload(
    tx_id: str = "tx-api-100",
    amount: str = "5000.00",
    customer_id: str = "cust-1",
    merchant_id: str = "merch-1",
    timestamp: str = "2026-03-15T12:00:00Z",
    lat: float = 12.9716,
    lon: float = 77.5946,
) -> dict:
    return {
        "transaction_id": tx_id,
        "customer_id": customer_id,
        "merchant_id": merchant_id,
        "amount": amount,
        "currency": "INR",
        "timestamp": timestamp,
        "latitude": lat,
        "longitude": lon,
        "transaction_type": "PURCHASE",
        "device_id": "dev-001",
        "ip_address": "192.168.1.1",
        "country": "IN",
        "merchant_label": "Test Retail",
    }


class TestFraudEvaluationAPI:
    # -------------------------------------------------------------------------
    # 1. Health check still works
    # -------------------------------------------------------------------------
    def test_health_check_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    # -------------------------------------------------------------------------
    # 2. POST valid transaction
    # -------------------------------------------------------------------------
    def test_post_valid_transaction(self, client):
        payload = sample_transaction_payload()
        response = client.post("/api/v1/fraud/evaluations", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["transaction_id"] == "tx-api-100"
        assert "risk_score" in data
        assert "risk_level" in data
        assert data["evaluation_status"] in ("COMPLETE", "PARTIAL")
        assert "rule_results" in data
        assert len(data["rule_results"]) == 4

    # -------------------------------------------------------------------------
    # 3. POST invalid amount rejected (422)
    # -------------------------------------------------------------------------
    def test_post_invalid_amount_rejected(self, client):
        payload = sample_transaction_payload(amount="0.00")  # amount must be > 0.00
        response = client.post("/api/v1/fraud/evaluations", json=payload)
        assert response.status_code == 422

        payload_neg = sample_transaction_payload(amount="-50.00")
        response_neg = client.post("/api/v1/fraud/evaluations", json=payload_neg)
        assert response_neg.status_code == 422

    # -------------------------------------------------------------------------
    # 4. POST invalid coordinates rejected (422)
    # -------------------------------------------------------------------------
    def test_post_invalid_coordinates_rejected(self, client):
        payload = sample_transaction_payload(lat=95.0)  # lat must be <= 90
        response = client.post("/api/v1/fraud/evaluations", json=payload)
        assert response.status_code == 422

        payload_lon = sample_transaction_payload(lon=-190.0)  # lon must be >= -180
        response_lon = client.post("/api/v1/fraud/evaluations", json=payload_lon)
        assert response_lon.status_code == 422

    # -------------------------------------------------------------------------
    # 5. POST invalid timestamp rejected (422)
    # -------------------------------------------------------------------------
    def test_post_invalid_timestamp_rejected(self, client):
        payload = sample_transaction_payload(timestamp="not-a-valid-iso-date")
        response = client.post("/api/v1/fraud/evaluations", json=payload)
        assert response.status_code == 422

    # -------------------------------------------------------------------------
    # 6. Normal clean evaluation (score 0, LOW)
    # -------------------------------------------------------------------------
    def test_normal_clean_evaluation(self, client):
        # Empty history, normal amount -> all rules clean
        payload = sample_transaction_payload(tx_id="tx-clean-test")
        response = client.post("/api/v1/fraud/evaluations", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["risk_score"] == 0
        assert data["risk_level"] == "LOW"
        assert data["evaluation_status"] == "COMPLETE"
        assert data["coverage_ratio"] == 1.0
        assert len(data["clean_rules"]) == 4
        assert len(data["triggered_rules"]) == 0
        assert len(data["failed_rules"]) == 0

    # -------------------------------------------------------------------------
    # 7. High-risk evaluation (real Batch 3 anomaly triggers score >= 70)
    # -------------------------------------------------------------------------
    def test_high_risk_evaluation_end_to_end(self, client):
        # Setup context where customer had 1,000 median, and current is 60,000 (60x -> score=100 on amount)
        # And location rule triggers: previous in Delhi at 11:30, current in Bangalore at 12:00 (30 min, 1740 km -> 3480 km/h)
        provider = InMemoryContextProvider()
        t_curr = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)

        # Delhi coordinates
        prev_tx = PreviousTransaction(
            transaction_id="pt-delhi",
            timestamp=t_curr - timedelta(minutes=30),
            amount=Decimal("1000.00"),
            merchant_id="merch-delhi",
            latitude=28.6139,
            longitude=77.2090,
        )
        provider.set_transaction_history("cust-highrisk", [
            prev_tx,
            PreviousTransaction(
                transaction_id="pt-baseline-1",
                timestamp=t_curr - timedelta(hours=2),
                amount=Decimal("1000.00"),
                merchant_id="merch-delhi",
            ),
            PreviousTransaction(
                transaction_id="pt-baseline-2",
                timestamp=t_curr - timedelta(hours=3),
                amount=Decimal("1000.00"),
                merchant_id="merch-delhi",
            ),
        ])
        provider.add_merchant_statistics(
            "merch-1",
            MerchantStatistics(
                transaction_count=2000,
                average_transaction_amount=Decimal("2000.00"),
                p95=Decimal("5000.00"),
                p99=Decimal("10000.00"),
            ),
        )

        # Bangalore coordinates for current transaction
        payload = sample_transaction_payload(
            tx_id="tx-highrisk",
            customer_id="cust-highrisk",
            amount="60000.00",
            timestamp=t_curr.isoformat(),
            lat=12.9716,
            lon=77.5946,
        )

        app.dependency_overrides[get_context_provider] = lambda: provider

        response = client.post("/api/v1/fraud/evaluations", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Both UnusualAmount and ImpossibleLocation trigger
        assert "unusual_amount" in data["triggered_rules"]
        assert "impossible_location" in data["triggered_rules"]
        assert data["risk_score"] >= 70
        assert data["risk_level"] in ("HIGH", "CRITICAL")
        assert data["evaluation_status"] == "COMPLETE"

    # -------------------------------------------------------------------------
    # 8. Partial rule failure (evaluation_status == PARTIAL)
    # -------------------------------------------------------------------------
    def test_partial_rule_failure_returns_partial_status(self, client):
        class CrashingLocationRule(FraudRule):
            rule_id = "impossible_location"
            rule_name = "Crashing Location Rule"

            async def evaluate(self, transaction, context):
                raise RuntimeError("Geolocation database connection refused")

        # Custom registry with crashing rule
        registry = create_default_rule_registry()
        registry.unregister("impossible_location")
        registry.register(CrashingLocationRule())

        rule_engine = RuleEngine(registry=registry)
        provider = InMemoryContextProvider()
        context_service = ContextService(provider=provider)
        service = FraudEvaluationService(context_service=context_service, rule_engine=rule_engine)

        app.dependency_overrides[get_fraud_evaluation_service] = lambda: service

        payload = sample_transaction_payload()
        response = client.post("/api/v1/fraud/evaluations", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["evaluation_status"] == "PARTIAL"
        assert "impossible_location" in data["failed_rules"]
        assert data["coverage_ratio"] == 0.70  # 1.0 - 0.30 weight = 0.70

    # -------------------------------------------------------------------------
    # 9. Complete rule failure / NO_VALID_SIGNALS
    # -------------------------------------------------------------------------
    def test_all_rules_failed_state(self, client):
        class AlwaysFailRule(FraudRule):
            def __init__(self, rule_id):
                self.rule_id = rule_id
                self.rule_name = rule_id

            async def evaluate(self, transaction, context):
                raise RuntimeError("Global rule evaluation failure")

        registry = RuleRegistry()
        for rid in ["transaction_velocity", "unusual_amount", "impossible_location", "merchant_context"]:
            registry.register(AlwaysFailRule(rid))

        rule_engine = RuleEngine(registry=registry)
        provider = InMemoryContextProvider()
        context_service = ContextService(provider=provider)
        service = FraudEvaluationService(context_service=context_service, rule_engine=rule_engine)

        app.dependency_overrides[get_fraud_evaluation_service] = lambda: service

        payload = sample_transaction_payload()
        response = client.post("/api/v1/fraud/evaluations", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["evaluation_status"] == "NO_VALID_SIGNALS"
        assert data["risk_score"] is None
        assert data["risk_level"] is None
        assert data["coverage_ratio"] == 0.0
        assert len(data["failed_rules"]) == 4

    # -------------------------------------------------------------------------
    # 10. Context provider failure -> 503 Service Unavailable
    # -------------------------------------------------------------------------
    def test_context_provider_failure_returns_503(self, client):
        class FailingProvider(InMemoryContextProvider):
            async def get_customer_context(self, customer_id: str):
                raise ConnectionError("PostgreSQL cluster unavailable")

        app.dependency_overrides[get_context_provider] = lambda: FailingProvider()

        payload = sample_transaction_payload()
        response = client.post("/api/v1/fraud/evaluations", json=payload)

        assert response.status_code == 503
        data = response.json()
        assert "Context retrieval unavailable" in data["detail"]

    # -------------------------------------------------------------------------
    # 11. Missing optional context -> evaluation still works (200 OK)
    # -------------------------------------------------------------------------
    def test_missing_optional_context_still_evaluates(self, client):
        # Empty provider has no customer baseline, no merchant stats, no history
        provider = InMemoryContextProvider()
        app.dependency_overrides[get_context_provider] = lambda: provider

        payload = sample_transaction_payload(customer_id="brand-new-cust", merchant_id="brand-new-merch")
        response = client.post("/api/v1/fraud/evaluations", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["evaluation_status"] == "COMPLETE"
        assert data["risk_score"] == 0

    # -------------------------------------------------------------------------
    # 12. FraudEvaluation response preserves evidence
    # -------------------------------------------------------------------------
    def test_response_preserves_evidence_structure(self, client):
        payload = sample_transaction_payload()
        response = client.post("/api/v1/fraud/evaluations", json=payload)

        assert response.status_code == 200
        data = response.json()

        res_map = {r["rule_id"]: r for r in data["rule_results"]}
        assert "transaction_velocity" in res_map
        assert "unusual_amount" in res_map
        assert "impossible_location" in res_map
        assert "merchant_context" in res_map

        # Verify evidence field is present and non-empty dict
        for r in data["rule_results"]:
            assert isinstance(r["evidence"], dict)
            assert "score" in r
            assert "severity" in r
            assert "status" in r

    # -------------------------------------------------------------------------
    # 13. Repeat evaluation is deterministic
    # -------------------------------------------------------------------------
    def test_repeat_evaluation_is_deterministic(self, client):
        payload = sample_transaction_payload()
        r1 = client.post("/api/v1/fraud/evaluations", json=payload).json()
        r2 = client.post("/api/v1/fraud/evaluations", json=payload).json()

        assert r1["risk_score"] == r2["risk_score"]
        assert r1["risk_level"] == r2["risk_level"]
        assert r1["coverage_ratio"] == r2["coverage_ratio"]
        assert r1["triggered_rules"] == r2["triggered_rules"]
        assert r1["clean_rules"] == r2["clean_rules"]
        assert r1["failed_rules"] == r2["failed_rules"]

    # -------------------------------------------------------------------------
    # 14. GET existing evaluation
    # -------------------------------------------------------------------------
    def test_get_existing_evaluation(self, client):
        payload = sample_transaction_payload(tx_id="tx-store-get")
        post_res = client.post("/api/v1/fraud/evaluations", json=payload)
        assert post_res.status_code == 200

        get_res = client.get("/api/v1/fraud/evaluations/tx-store-get")
        assert get_res.status_code == 200
        data = get_res.json()
        assert data["transaction_id"] == "tx-store-get"
        assert data["risk_score"] == post_res.json()["risk_score"]

    # -------------------------------------------------------------------------
    # 15. GET missing transaction (404 Not Found)
    # -------------------------------------------------------------------------
    def test_get_missing_transaction_returns_404(self, client):
        response = client.get("/api/v1/fraud/evaluations/tx-non-existent")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
