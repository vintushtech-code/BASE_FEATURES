import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


class MerchantProfile(models.Model):
    """
    Merchant account profile holding API keys, balances, and concurrency lock fields.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='merchant_profile'
    )
    merchant_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    business_name = models.CharField(max_length=255)
    api_key = models.CharField(max_length=100, unique=True, db_index=True)
    api_secret_hash = models.CharField(max_length=255)
    webhook_secret = models.CharField(max_length=255, blank=True, default='')
    
    # Financial ledger balance
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    reserved_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    
    # Optimistic Concurrency Control Version field
    version = models.PositiveIntegerField(default=1)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Merchant: {self.business_name} ({self.merchant_id})"


class CustomerProfile(models.Model):
    """
    Customer profile for buyers using the payment gateway.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='customer_profile'
    )
    customer_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    razorpay_customer_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    
    # Stored customer wallet/balance
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=10000.00)  # Default demo balance
    
    # Optimistic Concurrency Control Version field
    version = models.PositiveIntegerField(default=1)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Customer: {self.user.get_full_name() or self.user.username} ({self.customer_id})"


class CardTokenVault(models.Model):
    """
    PCI-DSS Compliant Card Vault.
    Raw card data (PAN, CVV) is NEVER stored in plain text.
    Only tokenized identifiers and AES-256-GCM encrypted tokens are stored.
    """
    token_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    customer = models.ForeignKey(CustomerProfile, on_delete=models.CASCADE, related_name='card_tokens')
    
    # Encrypted payload (contains AES-256-GCM cipher bytes of token metadata)
    encrypted_payload = models.TextField(help_text="AES-256-GCM encrypted card vault token")
    
    # Non-sensitive card display metadata
    last4 = models.CharField(max_length=4)
    card_network = models.CharField(max_length=20, default='Visa')  # Visa, Mastercard, RuPay, Amex
    expiry_month = models.IntegerField()
    expiry_year = models.IntegerField()
    
    # Fingerprint (SHA-256 hash of card number + customer salt) for deduplication without storing raw PAN
    fingerprint = models.CharField(max_length=64, db_index=True)
    
    # Razorpay Token ID reference
    razorpay_token_id = models.CharField(max_length=100, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['customer', 'fingerprint']),
        ]

    def __str__(self):
        return f"Card **** {self.last4} ({self.card_network})"


class PaymentTransaction(models.Model):
    """
    Core Payment Ledger Transaction Model.
    Tracks state machine lifecycle (CREATED -> AUTHORIZED -> CAPTURED -> SETTLED / FAILED / REFUNDED).
    Includes versioning for Optimistic Concurrency Control and Idempotency key indexing.
    """
    STATUS_CHOICES = (
        ('CREATED', 'Created'),
        ('AUTHORIZED', 'Authorized'),
        ('CAPTURED', 'Captured (Clearing)'),
        ('SETTLED', 'Settled'),
        ('FAILED', 'Failed'),
        ('REFUNDED', 'Refunded'),
    )

    FAILURE_REASON_CHOICES = (
        ('NONE', 'None'),
        ('INSUFFICIENT_FUNDS', 'Insufficient Funds'),
        ('INVALID_CARD', 'Invalid Card Data'),
        ('FRAUD_RISK_BLOCK', 'Fraud Risk Blocked'),
        ('GATEWAY_UNAVAILABLE', 'Gateway Unavailable'),
        ('DUPLICATE_REQUEST_REJECTED', 'Duplicate Request Rejected'),
        ('INVALID_SIGNATURE', 'Invalid Webhook Signature'),
    )

    transaction_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    idempotency_key = models.CharField(max_length=255, unique=True, null=True, blank=True, db_index=True)
    
    merchant = models.ForeignKey(MerchantProfile, on_delete=models.PROTECT, related_name='transactions')
    customer = models.ForeignKey(CustomerProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    
    # Razorpay References
    razorpay_order_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    razorpay_signature = models.CharField(max_length=255, blank=True, null=True)
    
    # Financial Details
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default='INR')
    
    # State Machine & Failure Tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='CREATED', db_index=True)
    failure_reason = models.CharField(max_length=50, choices=FAILURE_REASON_CHOICES, default='NONE')
    failure_message = models.TextField(blank=True, default='')
    
    # Optimistic Concurrency Control
    version = models.PositiveIntegerField(default=1)
    
    # Reconciliation flag
    is_reconciled = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['merchant', 'status']),
        ]

    def __str__(self):
        return f"Txn {self.transaction_id} | Status: {self.status} | Amt: {self.amount} {self.currency}"


class IdempotencyRecord(models.Model):
    """
    Stores HTTP request idempotency records.
    Returns cached response if duplicate Idempotency-Key is received.
    """
    key = models.CharField(max_length=255, unique=True, db_index=True)
    request_path = models.CharField(max_length=255)
    request_hash = models.CharField(max_length=64)
    response_status = models.IntegerField()
    response_body = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)

    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"IdempotencyKey: {self.key} | Path: {self.request_path}"


class OutboxEvent(models.Model):
    """
    Transactional Outbox Pattern.
    Guarantees at-least-once event delivery for distributed saga orchestration.
    Written atomically in the same DB transaction as business entity updates.
    """
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('PROCESSED', 'Processed'),
        ('FAILED', 'Failed'),
    )

    event_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    aggregate_type = models.CharField(max_length=50, default='PaymentTransaction')
    aggregate_id = models.CharField(max_length=100)
    event_type = models.CharField(max_length=100)  # e.g., PAYMENT_AUTHORIZED, PAYMENT_CAPTURED, REFUND_ISSUED
    payload = models.JSONField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', db_index=True)
    retry_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"OutboxEvent {self.event_type} ({self.aggregate_id}) - Status: {self.status}"


class SagaStateLog(models.Model):
    """
    Saga Pattern Execution Log.
    Tracks state transitions and compensating transaction steps.
    """
    STATE_CHOICES = (
        ('STARTED', 'Started'),
        ('COMMITTED', 'Committed'),
        ('COMPENSATING', 'Compensating'),
        ('COMPENSATED', 'Compensated'),
        ('FAILED', 'Failed'),
    )

    saga_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    transaction = models.ForeignKey(PaymentTransaction, on_delete=models.CASCADE, related_name='saga_logs', null=True, blank=True)
    current_step = models.CharField(max_length=50)
    state = models.CharField(max_length=20, choices=STATE_CHOICES, default='STARTED')
    payload = models.JSONField(default=dict)
    error_message = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Saga {self.saga_id} Step: {self.current_step} State: {self.state}"


class ReconciliationReport(models.Model):
    """
    Asynchronous Reconciliation Report.
    Stores results of automated comparison between DB transactions and Razorpay settlement reports.
    """
    report_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    total_records_checked = models.IntegerField(default=0)
    matched_records = models.IntegerField(default=0)
    discrepancy_count = models.IntegerField(default=0)
    status = models.CharField(max_length=20, default='COMPLETED')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Reconciliation Report {self.report_id} - Discrepancies: {self.discrepancy_count}"


class DiscrepancyLog(models.Model):
    """
    Individual record discrepancies flagged during Reconciliation process.
    """
    DISCREPANCY_CHOICES = (
        ('MISSING_IN_LOCAL', 'Record Missing in Local DB'),
        ('MISSING_IN_GATEWAY', 'Record Missing in Razorpay Gateway'),
        ('STATUS_MISMATCH', 'Status Mismatch Between Systems'),
        ('AMOUNT_MISMATCH', 'Amount Mismatch Between Systems'),
    )

    report = models.ForeignKey(ReconciliationReport, on_delete=models.CASCADE, related_name='discrepancies')
    transaction = models.ForeignKey(PaymentTransaction, on_delete=models.SET_NULL, null=True, blank=True)
    discrepancy_type = models.CharField(max_length=50, choices=DISCREPANCY_CHOICES)
    details = models.JSONField()
    resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Discrepancy: {self.discrepancy_type} on Txn {self.transaction_id if self.transaction else 'N/A'}"
