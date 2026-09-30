# Member 1 Handoff Contract: Extensible Rule Engine & Domain Models

**Owner:** Member 1 — Core Fraud Engine & Backend  
**Target Consumers:** Member 2 (Agentic Investigation System), Member 3 (Frontend Reviewer Console), Member 4 (Database & Infrastructure)  
**Implementation Phase:** Batch 2 — Domain Models & Extensible Rule Engine Foundation  

---

## 1. Executive Summary & Pipeline Flow

The deterministic fraud engine is the primary evaluation gateway. It evaluates incoming financial transactions against pre-fetched context in a strictly deterministic, non-LLM manner.

```
Incoming Transaction
         │
         ▼
FraudEvaluationContext (Customer baseline, Merchant profile, Recent txns)
         │
         ▼
RuleRegistry (Configured FraudRule plugins)
         │
         ▼
RuleEngine.evaluate_all(transaction, context)
         │
         ▼
List[RuleResult] (Structured evidence & deterministic scores)
         │
         ▼
FraudEvaluation (Package delivered to downstream Risk Engine & Member 2 Investigation Layer)
```

---

## 2. Core Schemas & Contracts

### 2.1 Transaction Schema (`app.schemas.transaction.Transaction`)
Safe monetary representation using Python `Decimal` and timezone-aware timestamps.

```python
class Transaction(BaseModel):
    transaction_id: str             # Unique transaction identifier
    customer_id: str                # Unique customer reference
    merchant_id: str                # Unique merchant reference
    amount: Decimal                 # Monetary amount (> 0.00)
    currency: str = "INR"           # ISO 3-letter currency code (auto-uppercased)
    timestamp: datetime             # Timezone-aware timestamp (UTC normalized)
    latitude: Optional[float]       # Latitude (-90.0 to 90.0)
    longitude: Optional[float]      # Longitude (-180.0 to 180.0)
    transaction_type: Optional[str] # e.g. "PURCHASE", "TRANSFER"
    device_id: Optional[str]        # Hardware/client identifier
    ip_address: Optional[str]       # Client IP address
    country: Optional[str]          # Country code / name
    merchant_label: Optional[str]   # Display merchant label
```

### 2.2 Context Schema (`app.schemas.context.FraudEvaluationContext`)
The central context bundle passed into every rule. Rules **never** query the database directly; they evaluate exclusively against this structure.

```python
class FraudEvaluationContext(BaseModel):
    customer_context: Optional[CustomerContext] = None
    merchant_context: Optional[Merchant] = None
    merchant_statistics: Optional[MerchantStatistics] = None
    previous_transaction: Optional[PreviousTransaction] = None
    recent_transactions: List[PreviousTransaction] = []
    metadata: Dict[str, Any] = {}
```

Supporting sub-models:
- `CustomerContext`: `customer_id`, `average_transaction_amount`, `transaction_count`, `recent_transaction_count`, `historical_activity_summary`.
- `Merchant`: `merchant_id`, `merchant_name`, `category`, `business_type`, `latitude`, `longitude`, `operating_hours`, `statistics`.
- `OperatingHours`: `start_time` (HH:MM), `end_time` (HH:MM), `timezone`.
- `MerchantStatistics`: `transaction_count`, `average_transaction_amount`, `p50`, `p95`, `p99`, `typical_daily_volume`.
- `PreviousTransaction`: `transaction_id`, `timestamp`, `latitude`, `longitude`, `amount`, `merchant_id`, `device_id: Optional[str] = None`, `ip_address: Optional[str] = None`.  
  *Note:* `device_id` and `ip_address` are optional historical telemetry fields available for future velocity, device-switching, and network-clustering rules.

### 2.3 Rule Result Contract (`app.schemas.rule.RuleResult`)
Every fraud rule returns this standard format:

```python
class Severity(str, Enum):
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class RuleExecutionStatus(str, Enum):
    SUCCESS = "SUCCESS"  # Rule executed successfully to completion
    ERROR = "ERROR"      # Rule crashed or could not evaluate

class RuleResult(BaseModel):
    rule_id: str                          # Unique identifier of the rule (e.g. "unusual_amount")
    rule_name: str                        # Human-readable rule title
    triggered: bool                       # True if risk condition met
    score: int = 0                        # Rule-specific risk contribution (0 to 100)
    severity: Severity = Severity.NONE    # Severity rating
    reason: str = ""                      # Human-readable summary
    evidence: Dict[str, Any] = {}         # Structured key/value data for Member 2 agents
    execution_time_ms: Optional[float]    # Duration of rule execution in ms
    status: RuleExecutionStatus = RuleExecutionStatus.SUCCESS  # Execution status (SUCCESS or ERROR)
```

> **CRITICAL CONSUMER RULE (Risk Engine & Frontend & Agents):**  
> `status == RuleExecutionStatus.SUCCESS` indicates that the rule evaluated correctly.  
> `status == RuleExecutionStatus.ERROR` indicates the rule could not be evaluated.  
> **Downstream consumers MUST NEVER interpret `status == ERROR` as "fraud not detected" or "clean".**  
> Future Risk Engine implementations MUST inspect `status` and handle rule evaluation errors explicitly.

### 2.4 Fraud Evaluation Aggregate (`app.schemas.evaluation.FraudEvaluation`)
Aggregates all rule outcomes for downstream processing:

```python
class FraudEvaluation(BaseModel):
    transaction_id: str
    rule_results: List[RuleResult]
    risk_score: Optional[int] = None      # Deferred to Risk Engine (Batch 4)
    risk_level: Optional[str] = None      # Deferred to Risk Engine (Batch 4)
    evaluation_timestamp: datetime
    metadata: Dict[str, Any] = {}
```

---

## 3. FraudRule Abstract Interface (`app.rules.base.FraudRule`)

All deterministic fraud rules inherit from `FraudRule` and implement `evaluate`:

```python
class FraudRule(ABC):
    rule_id: str
    rule_name: str
    description: str = ""
    is_enabled: bool = True

    @abstractmethod
    async def evaluate(
        self,
        transaction: Transaction,
        context: FraudEvaluationContext,
    ) -> RuleResult:
        """
        Evaluate the transaction and contextual information.
        Must execute deterministically without external I/O.
        """
        pass
```

### Async Execution Decision
The `evaluate` method is `async` to align seamlessly with FastAPI's asynchronous event loop and allow non-blocking evaluation pipelines. Deterministic rules compute in-memory calculations without blocking.

---

## 4. RuleRegistry Behavior (`app.rules.registry.RuleRegistry`)

The `RuleRegistry` manages rule registration, validation, and retrieval:
- `register(rule: FraudRule) -> None`: Validates interface conformance and ensures unique `rule_id`. Raises `DuplicateRuleError` if `rule_id` is already registered, and `InvalidRuleError` if the object does not conform to `FraudRule`.
- `unregister(rule_id: str) -> FraudRule`: Removes a rule by its ID. Raises `RuleNotFoundError` if missing.
- `get(rule_id: str) -> Optional[FraudRule]`: Looks up a rule by ID.
- `get_enabled() -> List[FraudRule]`: Returns all registered rules where `is_enabled == True`.
- `clear() -> None`: Clears all registered rules (used for test isolation).

---

## 5. RuleEngine Behavior (`app.rules.engine.RuleEngine`)

The `RuleEngine` executes all enabled rules from the registry against the transaction and context:
- `evaluate_all(transaction, context) -> List[RuleResult]`: Executes each enabled rule, captures execution timing (`execution_time_ms`), and aggregates results.
- `evaluate_transaction(transaction, context) -> FraudEvaluation`: Bundles results into `FraudEvaluation`.

### Registry Isolation
`RuleEngine(registry: Optional[RuleRegistry] = None)` defaults to instantiating a fresh `RuleRegistry()` instance if no registry is explicitly supplied. This guarantees that multiple engine instances do not share mutable module-level state, preventing cross-test pollution and unexpected runtime coupling.

### Extensibility Pattern
The `RuleEngine` depends **only** on the abstract `FraudRule` interface. It does **not** import or reference concrete rules (`VelocityRule`, `UnusualAmountRule`, etc.). New rules can be written and registered in `RuleRegistry` dynamically without modifying a single line of `RuleEngine` code.

---

## 6. Rule Failure Behavior & Resilience

When a rule raises an unhandled exception:
1. The error is logged with full traceback via standard Python logging.
2. If `fail_fast=True`: The engine immediately halts and raises `RuleExecutionError(rule_id, message)`.
3. If `fail_fast=False` (default): The engine **never silently swallows errors**. Instead, it generates a transparent error `RuleResult` with explicit error semantics:
   - `status = RuleExecutionStatus.ERROR` (explicitly machine-readable; not `SUCCESS`)
   - `triggered = False`
   - `score = 0`
   - `severity = Severity.NONE`
   - `reason = "Rule evaluation failed with error: <ExceptionName>: <message>"`
   - `evidence = {"error": str(e), "error_type": "...", "execution_failed": True}`
   - Subsequent rules continue executing unaffected.
   - Downstream consumers can explicitly filter or handle `result.status == RuleExecutionStatus.ERROR` rather than mistaking a crashed rule for a clean evaluation.

---

## 7. Example Rule Implementation

```python
class DummyThresholdRule(FraudRule):
    rule_id = "amount_threshold_example"
    rule_name = "Amount Threshold Rule"
    description = "Example dummy rule demonstrating implementation contract"

    async def evaluate(self, transaction: Transaction, context: FraudEvaluationContext) -> RuleResult:
        threshold = Decimal("50000.00")
        is_triggered = transaction.amount > threshold

        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            triggered=is_triggered,
            score=30 if is_triggered else 0,
            severity=Severity.MEDIUM if is_triggered else Severity.NONE,
            reason="Transaction amount exceeded 50,000 threshold" if is_triggered else "Within limits",
            evidence={
                "amount": str(transaction.amount),
                "threshold": str(threshold),
            },
        )
```

---

## 8. What the Engine Intentionally Does NOT Do

To maintain strict architectural boundaries:
- **No Risk Scoring**: The engine does NOT compute composite risk scores, weighted averages, or threshold classifications (`risk_score` is deferred to Batch 4).
- **No Database Fetching**: Rules do NOT query PostgreSQL or invoke ORM calls.
- **No AI / LLM Logic**: The rule engine is purely deterministic. Evidence synthesis and investigation reasoning belong to Member 2.
- **No Case Generation**: Creation of investigation cases or fraud tickets belongs to downstream case orchestration.

---

## 9. Batch 3 — Production Deterministic Fraud Rules

Batch 3 implements four production-grade deterministic rules adhering to the `FraudRule` contract:

### 9.1 `TransactionVelocityRule` (`app.rules.velocity.TransactionVelocityRule`)
- **Rule ID / Name**: `transaction_velocity` / `Transaction Velocity Rule`
- **Purpose**: Detect unusually high transaction frequency for a customer/account within a rolling sliding window.
- **Inputs**: Current `transaction.timestamp`, historical transactions in `context.recent_transactions` and `context.previous_transaction`.
- **Configuration**:
  - `window_minutes` (default: `10` minutes)
  - `transaction_threshold` (default: `5` transactions)
- **Deterministic Logic**:
  - Filters historical transactions strictly falling within `[current_time - window_minutes, current_time]`.
  - Discards future-dated transactions (`timestamp > current_time`).
  - Total count includes previous qualifying transactions plus 1 for the current transaction.
- **Trigger Conditions**: Triggers if and only if `count >= transaction_threshold`.
- **Score & Severity**:
  - `count < threshold`: `score = 0`, `severity = Severity.NONE`, `triggered = False`
  - `count == threshold`: `score = 60`, `severity = Severity.MEDIUM`, `triggered = True`
  - `count > threshold`: `score = min(100, 60 + ((count - threshold) * 10))`, `severity = score_to_severity(score)`, `triggered = True`
- **Evidence Structure**:
  - `window_minutes`, `transaction_threshold`, `current_transaction_id`, `current_transaction_timestamp`, `window_start`, `window_end`, `transaction_count`, `qualifying_transaction_ids`, `score`, `severity`, `reason`.
- **Insufficient Data Behavior**: Empty or low transaction history evaluates with `count < threshold` -> `triggered = False`, `status = SUCCESS`.

### 9.2 `UnusualAmountRule` (`app.rules.amount.UnusualAmountRule`)
- **Rule ID / Name**: `unusual_amount` / `Unusual Amount Rule`
- **Purpose**: Detect transactions that deviate abnormally from the customer's personal historical baseline (never global thresholds).
- **Inputs**: `transaction.amount`, historical amounts extracted from `context.recent_transactions` and `context.previous_transaction`.
- **Configuration**:
  - `minimum_history` (default: `3` transactions)
  - `amount_multiplier_threshold` (default: `3.0`x)
- **Deterministic Logic**:
  - Requires at least `minimum_history` usable historical transactions.
  - Computes baseline using historical **median** (`calculate_median` preserving `Decimal` precision).
  - Multiplier ratio: `ratio = current_amount / median_baseline`.
- **Trigger Conditions**: Triggers if `ratio >= amount_multiplier_threshold`.
- **Zero Baseline Handling**:
  - If baseline is `0.00` and current amount is `0.00`: `clean`, `score = 0`, `severity = Severity.NONE`.
  - If baseline is `0.00` and current amount > `0.00`: explicit zero-baseline anomaly, `triggered = True`, `score = 70`, `severity = Severity.HIGH`.
- **Score & Severity**:
  - `ratio < threshold`: `score = 0`, `severity = Severity.NONE`, `triggered = False`
  - `ratio >= threshold`: `score = min(100, 60 + int((ratio - threshold) * 20))`, `severity = score_to_severity(score)`, `triggered = True`
- **Evidence Structure**:
  - `current_amount`, `historical_transaction_count`, `historical_amounts`, `median_baseline`, `multiplier_ratio`, `configured_threshold`, `minimum_history_required`, `insufficient_historical_data`, `score`, `severity`, `reason`.
- **Insufficient Data Behavior**: If fewer than `minimum_history` transactions exist, returns `triggered = False`, `status = SUCCESS`, with `insufficient_historical_data = True`.

### 9.3 `ImpossibleLocationRule` (`app.rules.location.ImpossibleLocationRule`)
- **Rule ID / Name**: `impossible_location` / `Impossible Location Rule`
- **Purpose**: Detect transactions implying physically impossible travel speeds compared with the most recent prior geolocated transaction.
- **Inputs**: `transaction.latitude`, `transaction.longitude`, `transaction.timestamp`, and previous transactions from `context`.
- **Configuration**:
  - `max_implied_speed_kmh` (default: `900.0` km/h)
- **Deterministic Logic**:
  - Filters historical transactions to find the most recent valid transaction with non-null GPS coordinates occurring before current transaction.
  - Computes distance locally using Haversine formula (`haversine_distance_km`, Earth radius 6371 km). Zero external API calls.
  - Computes `elapsed_hours = (current_timestamp - previous_timestamp).total_seconds() / 3600.0`.
  - Implied speed: `implied_speed_kmh = distance_km / elapsed_hours`.
- **Trigger Conditions**: Triggers strictly if `implied_speed_kmh > max_implied_speed_kmh`.
- **Edge Cases**:
  - Same location (`distance <= 0.001 km`): speed treated as `0.0`, `clean`.
  - Missing coordinates on either current or prior transaction: `clean`, `status = SUCCESS`, `missing_location_data = True`.
  - Non-positive elapsed time: `clean`, `status = SUCCESS`.
- **Score & Severity**:
  - `speed <= threshold`: `score = 0`, `severity = Severity.NONE`, `triggered = False`
  - `speed > threshold`: `excess_ratio = (speed - threshold) / threshold`, `score = min(100, 70 + int(excess_ratio * 30))`, `severity = score_to_severity(score)`, `triggered = True`
- **Evidence Structure**:
  - `current_transaction_id`, `current_latitude`, `current_longitude`, `previous_transaction_id`, `previous_latitude`, `previous_longitude`, `distance_km`, `elapsed_seconds`, `elapsed_hours`, `implied_speed_kmh`, `speed_threshold_kmh`, `missing_location_data`, `score`, `severity`, `reason`.

### 9.4 `MerchantContextRule` (`app.rules.merchant_context.MerchantContextRule`)
- **Rule ID / Name**: `merchant_context` / `Merchant Context Rule`
- **Purpose**: Context-aware risk evaluation based on merchant statistical profile (`p95`, `p99`, `p50`, `average`) and operating hours. Proves that the exact same transaction amount (e.g. ₹60,000) produces different outcomes depending on business context (clean at Jewelry vs anomalous at Fuel Station).
- **Inputs**: `transaction.amount`, `transaction.timestamp`, `context.merchant_context`, `context.merchant_statistics`.
- **Configuration**:
  - `fallback_multiplier` (default: `3.0`x)
- **Statistical Baseline Preference Hierarchy**:
  1. `p95`: Primary baseline. Triggers if `amount > p95`.
  2. `p99`: Secondary baseline (or escalation). If `amount > p99`, stronger anomaly signal (`score >= 85`).
  3. `p50`: Fallback baseline. Triggers if `amount / p50 > fallback_multiplier`.
  4. `average_transaction_amount`: Final fallback. Triggers if `amount / average > fallback_multiplier`.
- **Operating Hours Evaluation**: Evaluates whether the transaction occurred within the merchant's operating hours (handling daytime and overnight ranges) and attaches `operating_hours_status: "WITHIN_HOURS" | "OUTSIDE_HOURS" | "UNKNOWN"` to structured evidence.
- **Score & Severity**:
  - `amount <= baseline`: `score = 0`, `severity = Severity.NONE`, `triggered = False`
  - `amount > p95` (below `p99`): `score = 65-84`, `severity = MEDIUM / HIGH`, `triggered = True`
  - `amount > p99`: `score = min(100, 85 + int(excess * 15))`, `severity = HIGH / CRITICAL`, `triggered = True`
  - Fallback: `score = min(100, 65 + int(deviation * 15))`, `severity = score_to_severity(score)`, `triggered = True`
- **Evidence Structure**:
  - `merchant_id`, `merchant_category`, `current_transaction_amount`, `baseline_type`, `baseline_value`, `p95`, `p99`, `p50`, `average`, `typical_daily_volume`, `operating_hours_status`, `within_operating_hours`, `ratio`, `fallback_multiplier`, `insufficient_merchant_statistics`, `score`, `severity`, `reason`.
- **Insufficient Data Behavior**: If merchant statistics are unavailable or all zero, returns `clean`, `status = SUCCESS`, with `insufficient_merchant_statistics = True`.

---

## 10. Developer Guide: Registering & Adding New Rules

### 10.1 Using the Pre-configured Registry
```python
from app.rules import RuleEngine, create_default_rule_registry

# Creates an isolated registry pre-populated with all 4 Batch 3 rules
registry = create_default_rule_registry()
engine = RuleEngine(registry=registry)

evaluation = await engine.evaluate_transaction(transaction, context)
```

### 10.2 Adding a Future Rule Without Modifying `RuleEngine`
The `RuleEngine` is completely decoupled and generic. To add a new rule:
1. Subclass `FraudRule`:
   ```python
   from app.rules.base import FraudRule
   from app.schemas.rule import RuleResult, Severity, RuleExecutionStatus

   class DeviceSwitchingRule(FraudRule):
       rule_id = "device_switching"
       rule_name = "Device Switching Rule"

       async def evaluate(self, transaction, context) -> RuleResult:
           # Pure deterministic in-memory logic
           ...
           return RuleResult(
               rule_id=self.rule_id,
               rule_name=self.rule_name,
               triggered=is_triggered,
               score=score,
               severity=severity,
               reason=reason,
               evidence=evidence,
               status=RuleExecutionStatus.SUCCESS,
           )
   ```
2. Register into `RuleRegistry`:
   ```python
   registry.register(DeviceSwitchingRule())
   ```
3. Run through `RuleEngine`:
   ```python
   engine = RuleEngine(registry=registry)
   results = await engine.evaluate_all(transaction, context)
   ```
   No changes to `RuleEngine` internals are required!

---

## 11. Batch 4 — Risk Scoring & Aggregation Engine (`app.risk`)

Batch 4 implements the case-level synthesis layer: a deterministic `RiskEngine` that aggregates individual `RuleResult` signals into a normalized `FraudEvaluation`.

### 11.1 Purpose & Architectural Separation
- `RuleEngine`: Executes individual `FraudRule` evaluations -> outputs `List[RuleResult]`. Does NOT aggregate or score risk.
- `RiskEngine`: Consumes `List[RuleResult]` -> computes normalized `risk_score`, assigns categorical `risk_level`, records operational completeness (`COMPLETE`, `PARTIAL`, `NO_VALID_SIGNALS`), and outputs `FraudEvaluation`.
- **Heuristic Disclaimer:** The `risk_score` is a deterministic weighted heuristic aggregation (0-100). It is **NOT** a machine-learning probability, statistical confidence, or certainty of fraud.

### 11.2 Input Contract
- Consumes `Sequence[RuleResult]` and optional `transaction_id: str`.
- Alternatively consumes an existing un-scored `FraudEvaluation` via `evaluate_evaluation(raw_eval)`.
- Input validation:
  - Empty `rule_results` raises `EmptyRuleResultsError`.
  - Duplicate `rule_id` entries raise `DuplicateRuleResultError`.
  - Unconfigured `rule_id` entries raise `UnknownRuleResultError` (prevents silent signal omissions).
  - Out-of-range scores (`< 0` or `> 100`) raise `InvalidScoreError`.

### 11.3 Rule Weight Configuration (`RiskConfiguration`)
Configurable rule weights sum to exactly `1.00` in `Decimal`:
- `transaction_velocity`: `0.20`
- `unusual_amount`: `0.25`
- `impossible_location`: `0.30`
- `merchant_context`: `0.25`

*Note:* Default weights are heuristic demonstration values and not calibrated from production fraud data. All weights are strictly validated on instantiation (non-negative, exact sum 1.00, required Batch 3 rules present).

#### Operational Modes (`require_all_batch3_rules`):
- **DEFAULT MODE (`require_all_batch3_rules=True`)**:
  - The standard FraudOps production pipeline expects all four Batch 3 rules (`transaction_velocity`, `unusual_amount`, `impossible_location`, `merchant_context`).
  - Omitting any required Batch 3 rule produces a `RiskConfigurationError`. This prevents accidental incomplete deployments in production.
- **CUSTOM MODE (`require_all_batch3_rules=False`)**:
  - Custom rule subsets are explicitly supported for controlled configurations, testing, experimentation, or future rule evolution (e.g., evaluating with only `transaction_velocity` and `merchant_context`).
  - **Validation Invariants Enforced in Custom Mode**:
    - Weights must still sum to exactly `1.00` in `Decimal`.
    - Every configured rule must have a valid, non-empty `rule_id` and non-negative numeric `Decimal` weight.
    - Duplicate rule IDs are strictly rejected.
    - Custom mode does **NOT** disable input validation or error checks.
  - *Operational Note:* Custom configurations are not automatically production-safe without careful operational review and domain calibration.

### 11.4 Weighted Aggregation Formula & Normalization
For successful rule results (`status == RuleExecutionStatus.SUCCESS`):
$$\text{available\_weight} = \sum_{r \in \text{successful}} \text{weight}_r$$
$$\text{raw\_weighted\_sum} = \sum_{r \in \text{successful}} (\text{score}_r \times \text{weight}_r)$$
$$\text{normalized\_score} = \text{ROUND\_HALF\_UP}\left(\frac{\text{raw\_weighted\_sum}}{\text{available\_weight}}\right)$$

#### Precise Decimal Rounding Contract:
- **Conceptual Formula:**
  $$\text{normalized\_score} = \text{ROUND\_HALF\_UP}\left(\frac{\text{raw\_weighted\_sum}}{\text{available\_weight}}\right)$$
- **Arithmetic Engine:** All mathematical calculations use Python `Decimal` to avoid IEEE 754 floating-point precision drift.
- **Integer Quantization:** The final score is quantized to the nearest integer and clamped within `[0, 100]`.
- **Midpoint Behavior (`ROUND_HALF_UP`):** Exact midpoint values (`.50`) round strictly upward away from zero:
  - `69.49` → `69`
  - `69.50` → `70`
  - `69.51` → `70`
  - `68.50` → `69`
- **Important Distinction:** The implementation strictly uses `Decimal.quantize(Decimal("1"), rounding=ROUND_HALF_UP)`. It does **NOT** use Python's built-in `round()` function (which implements "banker's rounding" / round-half-to-even, where `round(68.5) == 68`).

### 11.5 Failed-Rule Behavior & Signal Resilience
- **Crucial Distinction:** A rule that failed execution (`status == RuleExecutionStatus.ERROR`) is **NEVER** treated as clean (`score = 0`).
- Failed rules are excluded from both numerator and denominator (`available_weight`).
- This preserves the signal strength of surviving rules and prevents service outages from creating false "safe" evaluations.

### 11.6 Operational Completeness (`evaluation_status`)
- `COMPLETE`: All configured rules evaluated successfully (`coverage_ratio == 1.0`).
- `PARTIAL`: A subset of rules succeeded while others failed with `ERROR` (`0.0 < coverage_ratio < 1.0`).
- `NO_VALID_SIGNALS`: Every rule failed with `ERROR` (`coverage_ratio == 0.0`). In this case:
  - `risk_score = None`
  - `risk_level = None`
  - `evaluation_status = "NO_VALID_SIGNALS"`
  - It is **never** falsely represented as `score = 0` or `LOW` risk.

### 11.7 Case-Level Risk Level Mapping (`RiskLevel`)
Deterministic mapping based on the normalized `risk_score`:
- `0` to `39`: `RiskLevel.LOW`
- `40` to `69`: `RiskLevel.MEDIUM`
- `70` to `89`: `RiskLevel.HIGH`
- `90` to `100`: `RiskLevel.CRITICAL`

### 11.8 Output Handoff Contract for Member 2 (Investigation System)
The resulting `FraudEvaluation` object provides a complete structured package:
```python
class FraudEvaluation(BaseModel):
    transaction_id: str                      # Transaction reference
    rule_results: List[RuleResult]           # Complete unmutated list of raw rule results
    risk_score: Optional[int]                # Normalized case score (0-100) or None
    risk_level: Optional[str]                # LOW, MEDIUM, HIGH, CRITICAL, or None
    evaluation_status: Optional[str]         # COMPLETE, PARTIAL, NO_VALID_SIGNALS
    coverage_ratio: Optional[float]          # Proportion of evaluated weight (e.g. 1.0, 0.70)
    triggered_rules: List[str]               # Rule IDs that triggered anomalies
    clean_rules: List[str]                   # Rule IDs that evaluated clean
    failed_rules: List[str]                  # Rule IDs that encountered errors
    evaluation_timestamp: datetime           # Time of evaluation
    metadata: Dict[str, Any]                 # Detailed mathematical & operational breakdown
```

### 11.9 How Member 2 Agents Consume the Handoff
1. **Routing:** If `evaluation_status == "NO_VALID_SIGNALS"`, route to technical system alert / data engineering rather than fraud investigation.
2. **Prioritization:** If `risk_level in ("HIGH", "CRITICAL")` or `risk_score >= 70`, trigger autonomous agentic deep investigation (LangGraph).
3. **Evidence Synthesis:** Inspect `evaluation.triggered_rules` and retrieve granular details directly from `result.evidence` of each corresponding `RuleResult` in `evaluation.rule_results` (e.g., implied speed, median baseline, velocity count).

### 11.10 Partial Evaluation Safety & Downstream Member 2 Contract
Downstream investigation consumers (Member 2 agentic workflows and human reviewer consoles) must adhere to these safety requirements:

1. **`evaluation_status` is Authoritative for Completeness:** `evaluation_status` explicitly communicates data completeness (`COMPLETE`, `PARTIAL`, or `NO_VALID_SIGNALS`).
2. **`COMPLETE` Semantics:** All configured fraud rules executed and evaluated successfully (`coverage_ratio == 1.0`, `failed_rules == []`).
3. **`PARTIAL` Semantics:** One or more configured rules encountered errors (`status == ERROR`). Signals are incomplete (`0.0 < coverage_ratio < 1.0`).
4. **`NO_VALID_SIGNALS` Semantics:** Zero configured rules evaluated successfully. No valid deterministic risk score can be formed (`risk_score = None`, `risk_level = None`).
5. **`risk_level` Must NEVER Be Interpreted Alone:** A `risk_level` of `LOW` in a `PARTIAL` evaluation merely reflects the mathematical score of surviving signals (e.g. `score = 0`); it is **NOT** verification that the transaction is benign.
6. **Incomplete Coverage Is Not Proof of Innocence:** If critical telemetry was missing (e.g., GPS service timed out, causing `impossible_location` to fail), an unobserved fraud vector may exist. Member 2 must factor `coverage_ratio` and `failed_rules` into agent prompts.
7. **Required Minimum Consumer Inspection Fields:** Downstream agents must inspect at minimum:
   - `evaluation_status`
   - `coverage_ratio`
   - `risk_score`
   - `risk_level`
   - `failed_rules`
   - `triggered_rules`
   - `rule_results`
8. **Missing Signals Remain Unconditionally Visible:** All failed rules are surfaced in `evaluation.failed_rules`, `evaluation.metadata["failed_rules"]`, and within `evaluation.rule_results` with `status == RuleExecutionStatus.ERROR`.
9. **Never Convert `ERROR` to Clean Evidence:** Member 2 investigation prompts must treat failed rules as operational unknowns, never as clean or negative fraud signals.

---

## 12. Batch 5 — Context Retrieval & Enrichment Layer (`app.services.context_service`)

Batch 5 establishes the deterministic context enrichment boundary, constructing the unified `FraudEvaluationContext` for incoming transactions without querying a hardcoded database.

### 12.1 Purpose & Architectural Separation
- **`ContextService` Responsibility:** Fetches customer baseline profiles, merchant information, statistical distributions, and recent transaction history.
- **Strict Boundary:** The `ContextService` performs **zero** fraud calculations and **zero** risk scoring. It only gathers and organizes contextual telemetry for rule execution.
- **Pluggable Persistence Adapter:** Does not import or bind directly to PostgreSQL/SQLAlchemy. Operates against `ContextProviderInterface`, enabling Member 4 to attach database-backed persistence seamlessly later.

### 12.2 Provider Contract (`app.repositories.context_provider.ContextProviderInterface`)
```python
class ContextProviderInterface(ABC):
    @abstractmethod
    async def get_customer_context(self, customer_id: str) -> Optional[CustomerContext]: ...

    @abstractmethod
    async def get_merchant(self, merchant_id: str) -> Optional[Merchant]: ...

    @abstractmethod
    async def get_merchant_statistics(self, merchant_id: str) -> Optional[MerchantStatistics]: ...

    @abstractmethod
    async def get_recent_transactions(self, customer_id: str, current_timestamp: datetime, limit: int) -> List[PreviousTransaction]: ...

    @abstractmethod
    async def get_previous_transaction(self, customer_id: str, current_timestamp: datetime) -> Optional[PreviousTransaction]: ...
```

### 12.3 Context Construction Guarantees
1. **Defense-in-Depth Temporal Boundary:** Enforces `historical.timestamp <= current_transaction.timestamp`. Any future-dated transaction returned by upstream sources is strictly excluded from historical context.
2. **Current Transaction Exclusion:** The current transaction (`transaction.transaction_id`) is strictly excluded from history to prevent duplicate self-referencing.
3. **Deduplication:** Merges transaction candidates across recent and previous feeds, deduplicating by `transaction_id`.
4. **Deterministic Ordering:** Historical transactions are sorted descending by `timestamp` (newest first), with `transaction_id` descending as a secondary tie-breaker.
5. **Bounded History Window:** Capped by `max_recent_transactions` (default: 10, configurable).
6. **Previous Transaction Selection:** Selects the most recent valid historical transaction occurring strictly at or before the current timestamp.
7. **Telemetry Preservation:** Preserves `device_id` and `ip_address` on `PreviousTransaction` models.
8. **Missing Data vs. Provider Failure Semantics:**
   - *Expected Missing Data:* If a new customer or merchant has no recorded profile or statistics, the service returns `None` for optional fields, allowing rules to evaluate under insufficient data conditions.
   - *Provider Failure:* If the underlying database or network raises an unhandled exception, `ContextService` raises an explicit `ContextRetrievalError(message, original_exception)`. Infrastructure outages never masquerade as clean/safe evaluations.

---

## 13. Batch 6 — Fraud Evaluation Service & API Layer (`app.services`, `app.api`)

Batch 6 exposes the complete deterministic FraudOps evaluation capability through application services and standard FastAPI endpoints.

### 13.1 FraudEvaluationService Pipeline Orchestration
The `FraudEvaluationService` coordinates the lifecycle of an evaluation:
```
Transaction
     ↓
ContextService.build_context(transaction)
     ↓
FraudEvaluationContext
     ↓
RuleEngine.evaluate_all(transaction, context)
     ↓
List[RuleResult]
     ↓
RiskEngine.evaluate(rule_results, transaction_id)
     ↓
EvaluationStore.save(evaluation)
     ↓
FraudEvaluation
```

### 13.2 Persistence Boundary (`EvaluationStoreInterface`)
Persistence of computed evaluations is decoupled through `EvaluationStoreInterface`:
- `save(evaluation: FraudEvaluation) -> None`
- `get(transaction_id: str) -> Optional[FraudEvaluation]`
- A reference in-memory store (`InMemoryEvaluationStore`) is used for local execution and testing.
- Member 4 will plug in a PostgreSQL-backed adapter implementing this same interface without requiring changes to the service or API routes.

### 13.3 API Endpoints

#### 1. POST `/api/v1/fraud/evaluations`
- **Request Body:** `Transaction` (JSON payload adhering to domain model)
- **Response Body:** `FraudEvaluation` (HTTP 200 OK)
- **Error Responses:**
  - `422 Unprocessable Entity`: Validation failure on transaction fields (e.g. amount <= 0, latitude > 90, malformed timestamp).
  - `503 Service Unavailable`: Raised when underlying context retrieval fails (`ContextRetrievalError`).
  - `500 Internal Server Error`: Unexpected internal service failure.

#### 2. GET `/api/v1/fraud/evaluations/{transaction_id}`
- **Path Parameter:** `transaction_id: str`
- **Response Body:** `FraudEvaluation` (HTTP 200 OK)
- **Error Responses:**
  - `404 Not Found`: If no evaluation has been recorded for the given `transaction_id`.

#### 3. GET `/health`
- **Response Body:** `{"status": "ok"}` (HTTP 200 OK)

### 13.4 Downstream Member 2 Handoff & Security
- API responses preserve the complete unmutated `rule_results` list with granular `evidence` maps.
- Diagnostic metadata (`coverage_ratio`, `evaluation_status`, `triggered_rules`, `failed_rules`) is fully preserved across JSON serialization.
- PII and sensitive transaction payloads are not logged in plain text.


