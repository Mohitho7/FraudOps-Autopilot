"""
Unit tests for ContextService (Batch 5 - Context Retrieval & Enrichment Layer).
Covers all 20 required test scenarios including defense-in-depth, deduplication,
boundary filtering, and provider error resilience.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest

from app.repositories.context_provider import InMemoryContextProvider
from app.schemas.customer import CustomerContext
from app.schemas.merchant import Merchant, MerchantStatistics, OperatingHours
from app.schemas.transaction import PreviousTransaction, Transaction
from app.services.context_service import ContextService
from app.services.exceptions import ContextRetrievalError


def make_transaction(
    tx_id: str = "tx-current",
    customer_id: str = "cust-1",
    merchant_id: str = "merch-1",
    amount: str = "5000.00",
    timestamp: datetime = None,
) -> Transaction:
    return Transaction(
        transaction_id=tx_id,
        customer_id=customer_id,
        merchant_id=merchant_id,
        amount=Decimal(amount),
        currency="INR",
        timestamp=timestamp or datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc),
    )


def make_previous(
    tx_id: str,
    amount: str = "1000.00",
    timestamp: datetime = None,
    device_id: str = None,
    ip_address: str = None,
) -> PreviousTransaction:
    return PreviousTransaction(
        transaction_id=tx_id,
        timestamp=timestamp or datetime(2026, 3, 15, 10, 0, 0, tzinfo=timezone.utc),
        amount=Decimal(amount),
        merchant_id="merch-1",
        device_id=device_id,
        ip_address=ip_address,
    )


class TestContextService:
    # -------------------------------------------------------------------------
    # 1. Customer Context Retrieved
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_customer_context_retrieved(self):
        provider = InMemoryContextProvider()
        cust = CustomerContext(
            customer_id="cust-1",
            average_transaction_amount=Decimal("2500.00"),
            transaction_count=42,
            recent_transaction_count=5,
        )
        provider.add_customer(cust)

        service = ContextService(provider=provider)
        tx = make_transaction(customer_id="cust-1")
        context = await service.build_context(tx)

        assert context.customer_context is not None
        assert context.customer_context.customer_id == "cust-1"
        assert context.customer_context.transaction_count == 42
        assert context.customer_context.average_transaction_amount == Decimal("2500.00")

    # -------------------------------------------------------------------------
    # 2. Merchant Context Retrieved
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_merchant_context_retrieved(self):
        provider = InMemoryContextProvider()
        merchant = Merchant(
            merchant_id="merch-1",
            merchant_name="Reliance Retail",
            category="GROCERY",
            operating_hours=OperatingHours(start_time="08:00", end_time="22:00", timezone="Asia/Kolkata"),
        )
        provider.add_merchant(merchant)

        service = ContextService(provider=provider)
        tx = make_transaction(merchant_id="merch-1")
        context = await service.build_context(tx)

        assert context.merchant_context is not None
        assert context.merchant_context.merchant_id == "merch-1"
        assert context.merchant_context.merchant_name == "Reliance Retail"
        assert context.merchant_context.category == "GROCERY"

    # -------------------------------------------------------------------------
    # 3. Merchant Statistics Retrieved (standalone or embedded)
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_merchant_statistics_retrieved(self):
        provider = InMemoryContextProvider()
        stats = MerchantStatistics(
            transaction_count=5000,
            average_transaction_amount=Decimal("1200.00"),
            p50=Decimal("1000.00"),
            p95=Decimal("4500.00"),
            p99=Decimal("9000.00"),
        )
        provider.add_merchant_statistics("merch-1", stats)

        service = ContextService(provider=provider)
        tx = make_transaction(merchant_id="merch-1")
        context = await service.build_context(tx)

        assert context.merchant_statistics is not None
        assert context.merchant_statistics.p95 == Decimal("4500.00")
        assert context.merchant_statistics.p99 == Decimal("9000.00")

    # -------------------------------------------------------------------------
    # 4. Recent Transactions Retrieved
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_recent_transactions_retrieved(self):
        provider = InMemoryContextProvider()
        t_curr = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
        history = [
            make_previous("p1", "100.00", timestamp=t_curr - timedelta(minutes=30)),
            make_previous("p2", "200.00", timestamp=t_curr - timedelta(minutes=15)),
        ]
        provider.set_transaction_history("cust-1", history)

        service = ContextService(provider=provider)
        tx = make_transaction(customer_id="cust-1", timestamp=t_curr)
        context = await service.build_context(tx)

        assert len(context.recent_transactions) == 2
        assert {pt.transaction_id for pt in context.recent_transactions} == {"p1", "p2"}

    # -------------------------------------------------------------------------
    # 5. Previous Transaction Selected Correctly
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_previous_transaction_selected_correctly(self):
        provider = InMemoryContextProvider()
        t_curr = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
        p_older = make_previous("p_old", "100.00", timestamp=t_curr - timedelta(hours=2))
        p_latest = make_previous("p_latest", "500.00", timestamp=t_curr - timedelta(minutes=10))

        provider.set_transaction_history("cust-1", [p_older, p_latest])

        service = ContextService(provider=provider)
        tx = make_transaction(customer_id="cust-1", timestamp=t_curr)
        context = await service.build_context(tx)

        assert context.previous_transaction is not None
        assert context.previous_transaction.transaction_id == "p_latest"
        assert context.previous_transaction.amount == Decimal("500.00")

    # -------------------------------------------------------------------------
    # 6. Future-Dated Historical Transaction Excluded (Defense-in-Depth)
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_future_dated_transaction_excluded(self):
        provider = InMemoryContextProvider()
        t_curr = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
        p_valid = make_previous("p_valid", "200.00", timestamp=t_curr - timedelta(minutes=10))
        p_future = make_previous("p_future", "1000000.00", timestamp=t_curr + timedelta(minutes=30))

        provider.set_transaction_history("cust-1", [p_valid, p_future])

        service = ContextService(provider=provider)
        tx = make_transaction(customer_id="cust-1", timestamp=t_curr)
        context = await service.build_context(tx)

        assert len(context.recent_transactions) == 1
        assert context.recent_transactions[0].transaction_id == "p_valid"
        assert "p_future" not in [pt.transaction_id for pt in context.recent_transactions]
        assert context.previous_transaction.transaction_id == "p_valid"

    # -------------------------------------------------------------------------
    # 7. Current Transaction Excluded from History
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_current_transaction_excluded_from_history(self):
        provider = InMemoryContextProvider()
        t_curr = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
        p_dup = make_previous("tx-current", "5000.00", timestamp=t_curr)
        p_other = make_previous("p_other", "1000.00", timestamp=t_curr - timedelta(minutes=5))

        provider.set_transaction_history("cust-1", [p_dup, p_other])

        service = ContextService(provider=provider)
        tx = make_transaction(tx_id="tx-current", customer_id="cust-1", timestamp=t_curr)
        context = await service.build_context(tx)

        assert len(context.recent_transactions) == 1
        assert context.recent_transactions[0].transaction_id == "p_other"
        assert context.previous_transaction.transaction_id == "p_other"

    # -------------------------------------------------------------------------
    # 8. Duplicate Transaction Across Sources Deduplicated
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_duplicate_transaction_deduplicated(self):
        provider = InMemoryContextProvider()
        t_curr = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
        p1 = make_previous("p1", "500.00", timestamp=t_curr - timedelta(minutes=10))

        # p1 present multiple times in history
        provider.set_transaction_history("cust-1", [p1, p1, p1])

        service = ContextService(provider=provider)
        tx = make_transaction(customer_id="cust-1", timestamp=t_curr)
        context = await service.build_context(tx)

        assert len(context.recent_transactions) == 1
        assert context.recent_transactions[0].transaction_id == "p1"

    # -------------------------------------------------------------------------
    # 9. History Ordered Deterministically (timestamp desc, tx_id desc)
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_history_ordered_deterministically(self):
        provider = InMemoryContextProvider()
        t_curr = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
        t_same = t_curr - timedelta(minutes=20)
        p_old = make_previous("p_old", "100.00", timestamp=t_curr - timedelta(hours=1))
        p_tie_b = make_previous("p_tie_b", "200.00", timestamp=t_same)
        p_tie_a = make_previous("p_tie_a", "200.00", timestamp=t_same)
        p_newest = make_previous("p_newest", "300.00", timestamp=t_curr - timedelta(minutes=5))

        # Insert out of order
        provider.set_transaction_history("cust-1", [p_old, p_tie_a, p_newest, p_tie_b])

        service = ContextService(provider=provider)
        tx = make_transaction(customer_id="cust-1", timestamp=t_curr)
        context = await service.build_context(tx)

        # Expected order: p_newest, p_tie_b (higher ID on tie), p_tie_a, p_old
        ordered_ids = [pt.transaction_id for pt in context.recent_transactions]
        assert ordered_ids == ["p_newest", "p_tie_b", "p_tie_a", "p_old"]

    # -------------------------------------------------------------------------
    # 10. History Limit Respected (max_recent_transactions)
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_history_limit_respected(self):
        provider = InMemoryContextProvider()
        t_curr = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
        txs = [
            make_previous(f"p_{i}", "100.00", timestamp=t_curr - timedelta(minutes=i))
            for i in range(1, 20)
        ]
        provider.set_transaction_history("cust-1", txs)

        # Set limit to 5
        service = ContextService(provider=provider, max_recent_transactions=5)
        tx = make_transaction(customer_id="cust-1", timestamp=t_curr)
        context = await service.build_context(tx)

        assert len(context.recent_transactions) == 5
        # Must be the 5 most recent
        expected_ids = [f"p_{i}" for i in range(1, 6)]
        assert [pt.transaction_id for pt in context.recent_transactions] == expected_ids

    # -------------------------------------------------------------------------
    # 11. Empty History Handled Cleanly
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_empty_history_handled(self):
        provider = InMemoryContextProvider()
        service = ContextService(provider=provider)
        tx = make_transaction(customer_id="cust-new")
        context = await service.build_context(tx)

        assert context.recent_transactions == []
        assert context.previous_transaction is None

    # -------------------------------------------------------------------------
    # 12. Missing Merchant Statistics Handled
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_missing_merchant_statistics_handled(self):
        provider = InMemoryContextProvider()
        merchant_no_stats = Merchant(
            merchant_id="merch-new",
            merchant_name="Brand New Shop",
            category="RETAIL",
        )
        provider.add_merchant(merchant_no_stats)

        service = ContextService(provider=provider)
        tx = make_transaction(merchant_id="merch-new")
        context = await service.build_context(tx)

        assert context.merchant_context is not None
        assert context.merchant_statistics is None

    # -------------------------------------------------------------------------
    # 13. Missing Customer Context Handled According to Schema
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_missing_customer_context_handled(self):
        provider = InMemoryContextProvider()
        service = ContextService(provider=provider)
        tx = make_transaction(customer_id="cust-unknown")
        context = await service.build_context(tx)

        assert context.customer_context is None

    # -------------------------------------------------------------------------
    # 14. Provider Failure Propagates as Explicit ContextRetrievalError
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_provider_failure_raises_context_retrieval_error(self):
        class BrokenProvider(InMemoryContextProvider):
            async def get_customer_context(self, customer_id: str):
                raise ConnectionError("Database connection timed out")

        service = ContextService(provider=BrokenProvider())
        tx = make_transaction()

        with pytest.raises(ContextRetrievalError, match="Failed to retrieve customer context"):
            await service.build_context(tx)

    # -------------------------------------------------------------------------
    # 15. Same Input Produces Identical Context (Determinism)
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_deterministic_context_construction(self):
        provider = InMemoryContextProvider()
        t_curr = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
        provider.set_transaction_history("cust-1", [
            make_previous("p1", "500.00", timestamp=t_curr - timedelta(minutes=10)),
            make_previous("p2", "1000.00", timestamp=t_curr - timedelta(minutes=5)),
        ])

        service = ContextService(provider=provider)
        tx = make_transaction(timestamp=t_curr)

        c1 = await service.build_context(tx)
        c2 = await service.build_context(tx)

        assert [pt.transaction_id for pt in c1.recent_transactions] == [pt.transaction_id for pt in c2.recent_transactions]
        assert c1.previous_transaction.transaction_id == c2.previous_transaction.transaction_id
        assert c1.metadata["recent_transaction_count"] == c2.metadata["recent_transaction_count"]

    # -------------------------------------------------------------------------
    # 16. Device ID Preserved
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_device_id_preserved(self):
        provider = InMemoryContextProvider()
        t_curr = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
        pt = make_previous("p1", device_id="device-fingerprint-xyz", timestamp=t_curr - timedelta(minutes=5))
        provider.set_transaction_history("cust-1", [pt])

        service = ContextService(provider=provider)
        tx = make_transaction(timestamp=t_curr)
        context = await service.build_context(tx)

        assert context.recent_transactions[0].device_id == "device-fingerprint-xyz"
        assert context.previous_transaction.device_id == "device-fingerprint-xyz"

    # -------------------------------------------------------------------------
    # 17. IP Address Preserved
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_ip_address_preserved(self):
        provider = InMemoryContextProvider()
        t_curr = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
        pt = make_previous("p1", ip_address="203.0.113.195", timestamp=t_curr - timedelta(minutes=5))
        provider.set_transaction_history("cust-1", [pt])

        service = ContextService(provider=provider)
        tx = make_transaction(timestamp=t_curr)
        context = await service.build_context(tx)

        assert context.recent_transactions[0].ip_address == "203.0.113.195"
        assert context.previous_transaction.ip_address == "203.0.113.195"

    # -------------------------------------------------------------------------
    # 18. Timezone Offsets Handled Correctly
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_timezone_offsets_handled_correctly(self):
        provider = InMemoryContextProvider()
        # 12:00 UTC == 17:30 IST (+05:30)
        t_utc = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
        ist = timezone(timedelta(hours=5, minutes=30))

        # Prior transaction recorded in IST: 17:00 IST (11:30 UTC -> 30 mins before)
        pt_prior_ist = make_previous("pt_ist", timestamp=datetime(2026, 3, 15, 17, 0, 0, tzinfo=ist))
        # Future transaction recorded in IST: 18:00 IST (12:30 UTC -> 30 mins after)
        pt_future_ist = make_previous("pt_future_ist", timestamp=datetime(2026, 3, 15, 18, 0, 0, tzinfo=ist))

        provider.set_transaction_history("cust-1", [pt_prior_ist, pt_future_ist])

        service = ContextService(provider=provider)
        tx = make_transaction(timestamp=t_utc)
        context = await service.build_context(tx)

        # Prior transaction must be included
        assert len(context.recent_transactions) == 1
        assert context.recent_transactions[0].transaction_id == "pt_ist"
        assert "pt_future_ist" not in [pt.transaction_id for pt in context.recent_transactions]

    # -------------------------------------------------------------------------
    # 19. Transaction at Exact Current Timestamp Handled (<= T Included)
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_transaction_at_exact_current_timestamp_included(self):
        provider = InMemoryContextProvider()
        t_curr = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
        # Another transaction at the exact same timestamp with a distinct transaction_id
        pt_exact = make_previous("pt_exact", "100.00", timestamp=t_curr)
        pt_micro_future = make_previous("pt_future", "200.00", timestamp=t_curr + timedelta(microseconds=1))

        provider.set_transaction_history("cust-1", [pt_exact, pt_micro_future])

        service = ContextService(provider=provider)
        tx = make_transaction(tx_id="tx-curr-diff", timestamp=t_curr)
        context = await service.build_context(tx)

        assert len(context.recent_transactions) == 1
        assert context.recent_transactions[0].transaction_id == "pt_exact"
        assert "pt_future" not in [pt.transaction_id for pt in context.recent_transactions]

    # -------------------------------------------------------------------------
    # 20. Future Transaction Never Appears in Recent Transactions
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_multiple_future_transactions_never_appear(self):
        provider = InMemoryContextProvider()
        t_curr = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
        futures = [
            make_previous(f"pf_{i}", timestamp=t_curr + timedelta(minutes=i))
            for i in range(1, 10)
        ]
        valid = make_previous("p_valid", timestamp=t_curr - timedelta(minutes=5))

        provider.set_transaction_history("cust-1", futures + [valid])

        service = ContextService(provider=provider)
        tx = make_transaction(timestamp=t_curr)
        context = await service.build_context(tx)

        assert len(context.recent_transactions) == 1
        assert context.recent_transactions[0].transaction_id == "p_valid"
