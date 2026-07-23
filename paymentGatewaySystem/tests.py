import json
import uuid
from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from paymentGatewaySystem.models import (
    MerchantProfile, CustomerProfile, CardTokenVault, PaymentTransaction,
    IdempotencyRecord, OutboxEvent, SagaStateLog, ReconciliationReport, DiscrepancyLog
)
from paymentGatewaySystem.security import (
    encrypt_card_data, decrypt_card_data, generate_card_fingerprint
)
from paymentGatewaySystem.state_machine import PaymentStateMachine, InvalidStateTransitionError
from paymentGatewaySystem.saga_orchestrator import PaymentSagaOrchestrator, SagaExecutionError
from paymentGatewaySystem.razorpay_client import RazorpayTestClient
from paymentGatewaySystem.reconciliation import ReconciliationEngine, PendingTransactionPoller

User = get_user_model()


class PaymentGatewaySystemTests(TestCase):
    def setUp(self):
        # Create test users
        self.merchant_user = User.objects.create_user(
            username='merchant_test',
            email='merchant@example.com',
            password='Password123!'
        )
        self.merchant = MerchantProfile.objects.create(
            user=self.merchant_user,
            business_name="Test Store",
            api_key="key_test_12345",
            api_secret_hash="secret_12345"
        )

        self.customer_user = User.objects.create_user(
            username='customer_test',
            email='customer@example.com',
            password='Password123!'
        )
        self.customer = CustomerProfile.objects.create(
            user=self.customer_user,
            balance=Decimal('5000.00')
        )

        self.client = APIClient()
        self.client.force_authenticate(user=self.merchant_user)

    # -------------------------------------------------------------
    # 1. PCI-DSS Compliance & AES-256 Tokenization Tests
    # -------------------------------------------------------------
    def test_pci_dss_card_tokenization(self):
        card_payload = {
            'card_number': '4111111111111111',
            'cvv': '123',
            'exp_month': 12,
            'exp_year': 2028
        }
        encrypted = encrypt_card_data(card_payload)
        self.assertNotIn('4111111111111111', encrypted)  # Raw card never in plaintext

        decrypted = decrypt_card_data(encrypted)
        self.assertEqual(decrypted['card_number'], '4111111111111111')

        fingerprint = generate_card_fingerprint('4111111111111111', str(self.customer.customer_id))
        self.assertEqual(len(fingerprint), 64)  # SHA-256 hash length

    def test_tokenize_card_api(self):
        self.client.force_authenticate(user=self.customer_user)
        url = reverse('paymentGatewaySystem:tokenize-card')
        payload = {
            'card_number': '4111111111111111',
            'exp_month': 12,
            'exp_year': 2028,
            'cvv': '123'
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('token', response.data)
        self.assertEqual(response.data['token']['last4'], '1111')

    # -------------------------------------------------------------
    # 2. State Machine Lifecycle & Optimistic Concurrency Control
    # -------------------------------------------------------------
    def test_state_machine_valid_transitions(self):
        txn = PaymentTransaction.objects.create(
            merchant=self.merchant,
            customer=self.customer,
            amount=Decimal('100.00'),
            status='CREATED'
        )
        PaymentStateMachine.transition(txn, 'AUTHORIZED')
        self.assertEqual(txn.status, 'AUTHORIZED')
        self.assertEqual(txn.version, 2)

        PaymentStateMachine.transition(txn, 'CAPTURED')
        self.assertEqual(txn.status, 'CAPTURED')

        PaymentStateMachine.transition(txn, 'SETTLED')
        self.assertEqual(txn.status, 'SETTLED')

    def test_state_machine_invalid_transition_raises_error(self):
        txn = PaymentTransaction.objects.create(
            merchant=self.merchant,
            customer=self.customer,
            amount=Decimal('100.00'),
            status='FAILED'
        )
        with self.assertRaises(InvalidStateTransitionError):
            PaymentStateMachine.transition(txn, 'SETTLED')

    # -------------------------------------------------------------
    # 3. Saga Pattern & Transactional Outbox Tests
    # -------------------------------------------------------------
    def test_payment_saga_success_flow(self):
        txn = PaymentTransaction.objects.create(
            merchant=self.merchant,
            customer=self.customer,
            amount=Decimal('200.00'),
            status='CREATED'
        )
        orchestrator = PaymentSagaOrchestrator()
        settled_txn = orchestrator.execute_payment(txn, self.customer, self.merchant)

        self.assertEqual(settled_txn.status, 'SETTLED')
        
        # Verify ledger updates
        self.merchant.refresh_from_db()
        self.customer.refresh_from_db()
        self.assertEqual(self.merchant.balance, Decimal('200.00'))
        self.assertEqual(self.customer.balance, Decimal('4800.00'))

        # Verify Transactional Outbox events created
        outbox_events = OutboxEvent.objects.filter(aggregate_id=str(txn.transaction_id))
        self.assertGreaterEqual(outbox_events.count(), 4)

    def test_saga_compensating_transaction_on_insufficient_funds(self):
        # Set low customer balance
        self.customer.balance = Decimal('10.00')
        self.customer.save()

        txn = PaymentTransaction.objects.create(
            merchant=self.merchant,
            customer=self.customer,
            amount=Decimal('500.00'),
            status='CREATED'
        )
        orchestrator = PaymentSagaOrchestrator()
        with self.assertRaises(SagaExecutionError):
            orchestrator.execute_payment(txn, self.customer, self.merchant)

        txn.refresh_from_db()
        self.assertEqual(txn.status, 'FAILED')
        self.assertEqual(txn.failure_reason, 'INSUFFICIENT_FUNDS')

    # -------------------------------------------------------------
    # 4. Idempotency Engine Tests
    # -------------------------------------------------------------
    def test_idempotent_request_returns_cached_response(self):
        url = reverse('paymentGatewaySystem:create-order')
        headers = {'HTTP_IDEMPOTENCY_KEY': 'idemp_key_unique_001'}
        payload = {'amount': 150.00, 'currency': 'INR'}

        # First Call
        resp1 = self.client.post(url, payload, format='json', **headers)
        self.assertEqual(resp1.status_code, status.HTTP_201_CREATED)

        # Duplicate Call with same Idempotency-Key
        resp2 = self.client.post(url, payload, format='json', **headers)
        self.assertEqual(resp2.status_code, status.HTTP_201_CREATED)
        self.assertTrue(resp2.data.get('_cached_idempotent_response'))

    def test_idempotent_key_payload_conflict(self):
        url = reverse('paymentGatewaySystem:create-order')
        headers = {'HTTP_IDEMPOTENCY_KEY': 'idemp_key_unique_002'}

        # First Call
        self.client.post(url, {'amount': 100.00}, format='json', **headers)

        # Second Call with different payload using same key -> Conflict
        resp = self.client.post(url, {'amount': 999.00}, format='json', **headers)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data['error'], 'DUPLICATE_REQUEST_REJECTED')

    # -------------------------------------------------------------
    # 5. Negative Scenario & Exception Simulation Tests
    # -------------------------------------------------------------
    def test_negative_scenario_fraud_risk_block(self):
        url = reverse('paymentGatewaySystem:create-order')
        payload = {'amount': 500.00, 'simulate_failure': 'FRAUD_RISK_BLOCK'}
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['error'], 'FRAUD_RISK_BLOCK')

    def test_negative_scenario_invalid_card(self):
        url = reverse('paymentGatewaySystem:create-order')
        payload = {'amount': 500.00, 'simulate_failure': 'INVALID_CARD'}
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'INVALID_CARD')

    # -------------------------------------------------------------
    # 6. Webhook HMAC Verification Tests
    # -------------------------------------------------------------
    def test_razorpay_webhook_signature_verification(self):
        url = reverse('paymentGatewaySystem:webhook')
        payload = json.dumps({"event": "payment.captured", "payload": {}})
        headers = {'HTTP_X_RAZORPAY_SIGNATURE': 'mock_wh_sig_valid'}
        response = self.client.post(url, payload, content_type='application/json', **headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # -------------------------------------------------------------
    # 7. Reconciliation & Background Polling Tests
    # -------------------------------------------------------------
    def test_reconciliation_engine(self):
        # Create a sample transaction with missing razorpay payment ID to trigger discrepancy
        PaymentTransaction.objects.create(
            merchant=self.merchant,
            customer=self.customer,
            amount=Decimal('300.00'),
            status='SETTLED'  # Marked SETTLED without payment ID
        )

        engine = ReconciliationEngine()
        report = engine.run_reconciliation()

        self.assertEqual(report.status, 'COMPLETED')
        self.assertGreaterEqual(report.discrepancy_count, 1)

    def test_pending_poller(self):
        poller = PendingTransactionPoller(timeout_minutes=0)
        result = poller.poll_and_reconcile_pending_transactions()
        self.assertIn('checked', result)
