import logging
import uuid
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from paymentGatewaySystem.models import (
    PaymentTransaction, CustomerProfile, MerchantProfile,
    SagaStateLog, OutboxEvent
)
from paymentGatewaySystem.state_machine import PaymentStateMachine, OptimisticLockError
from paymentGatewaySystem.razorpay_client import RazorpayTestClient

logger = logging.getLogger(__name__)


class SagaExecutionError(Exception):
    """Raised when a step in the payment Saga fails."""
    def __init__(self, message, failure_reason='GATEWAY_UNAVAILABLE'):
        super().__init__(message)
        self.failure_reason = failure_reason


class PaymentSagaOrchestrator:
    """
    Saga Pattern & Transactional Outbox Orchestrator.
    Manages multi-step payment workflow with compensating transactions.
    
    Steps:
      1. RESERVE_FUNDS: Check customer balance & lock ledger row.
      2. GATEWAY_AUTHORIZE: Create order / authorize with Razorpay API.
      3. GATEWAY_CAPTURE: Capture / clear payment.
      4. MERCHANT_SETTLEMENT: Credit merchant account & deduct customer balance.
      
    If any step fails, compensating transactions run to rollback changes atomically.
    """

    def __init__(self):
        self.razorpay_client = RazorpayTestClient()

    def _record_outbox_event(self, aggregate_id: str, event_type: str, payload: dict):
        """
        Transactional Outbox Pattern: Save event to Outbox table in same DB transaction.
        """
        OutboxEvent.objects.create(
            aggregate_type='PaymentTransaction',
            aggregate_id=str(aggregate_id),
            event_type=event_type,
            payload=payload,
            status='PENDING'
        )

    def execute_payment(self, payment_txn: PaymentTransaction, customer: CustomerProfile, merchant: MerchantProfile) -> PaymentTransaction:
        """
        Executes full distributed payment Saga.
        """
        saga_log = SagaStateLog.objects.create(
            transaction=payment_txn,
            current_step='STARTED',
            state='STARTED',
            payload={'transaction_id': str(payment_txn.transaction_id), 'amount': str(payment_txn.amount)}
        )

        try:
            # STEP 1: Reserve Customer Funds (Row-level Locking)
            self._step_reserve_customer_funds(payment_txn, customer, saga_log)

            # STEP 2: Gateway Pre-Authorization (Razorpay Test Mode Order Creation)
            self._step_gateway_authorize(payment_txn, saga_log)

            # STEP 3: Gateway Payment Capture (Clearing)
            self._step_gateway_capture(payment_txn, saga_log)

            # STEP 4: Ledger Settlement & Merchant Account Credit
            self._step_merchant_settlement(payment_txn, customer, merchant, saga_log)

            # Mark Saga Complete
            saga_log.state = 'COMMITTED'
            saga_log.current_step = 'SETTLEMENT_FINISHED'
            saga_log.save()

            return payment_txn

        except SagaExecutionError as e:
            logger.error(f"Saga Execution Failed at step {saga_log.current_step}: {e}")
            self._execute_compensation(payment_txn, customer, merchant, saga_log, e.failure_reason, str(e))
            raise e
        except Exception as e:
            logger.error(f"Unexpected error in Payment Saga: {e}")
            self._execute_compensation(payment_txn, customer, merchant, saga_log, 'GATEWAY_UNAVAILABLE', str(e))
            raise SagaExecutionError(str(e), failure_reason='GATEWAY_UNAVAILABLE')

    def _step_reserve_customer_funds(self, payment_txn: PaymentTransaction, customer: CustomerProfile, saga_log: SagaStateLog):
        """
        Step 1: Check and reserve customer funds using row-level locking (select_for_update).
        """
        saga_log.current_step = 'RESERVE_FUNDS'
        saga_log.save()

        with transaction.atomic():
            # Lock customer row to prevent race conditions during balance check
            cust_locked = CustomerProfile.objects.select_for_update().get(pk=customer.pk)
            
            if cust_locked.balance < payment_txn.amount:
                raise SagaExecutionError("Insufficient customer balance for transaction", failure_reason='INSUFFICIENT_FUNDS')
            
            self._record_outbox_event(
                payment_txn.transaction_id,
                'FUNDS_RESERVED',
                {'amount': str(payment_txn.amount), 'customer_id': str(customer.customer_id)}
            )

    def _step_gateway_authorize(self, payment_txn: PaymentTransaction, saga_log: SagaStateLog):
        """
        Step 2: Create order / pre-authorize in Razorpay Test API.
        """
        saga_log.current_step = 'GATEWAY_AUTHORIZE'
        saga_log.save()

        amount_paise = int(payment_txn.amount * 100)
        razorpay_order = self.razorpay_client.create_order(
            amount_paise=amount_paise,
            currency=payment_txn.currency,
            receipt=str(payment_txn.transaction_id)
        )

        if not razorpay_order or not razorpay_order.get('order_id'):
            raise SagaExecutionError("Razorpay order creation failed", failure_reason='GATEWAY_UNAVAILABLE')

        payment_txn.razorpay_order_id = razorpay_order['order_id']
        PaymentStateMachine.transition(payment_txn, 'AUTHORIZED')
        payment_txn.save()

        self._record_outbox_event(
            payment_txn.transaction_id,
            'PAYMENT_AUTHORIZED',
            {'order_id': payment_txn.razorpay_order_id, 'status': payment_txn.status}
        )

    def _step_gateway_capture(self, payment_txn: PaymentTransaction, saga_log: SagaStateLog):
        """
        Step 3: Capture / clear payment with Razorpay Test API.
        """
        saga_log.current_step = 'GATEWAY_CAPTURE'
        saga_log.save()

        if not payment_txn.razorpay_payment_id:
            payment_txn.razorpay_payment_id = f"pay_{uuid.uuid4().hex[:14]}"

        amount_paise = int(payment_txn.amount * 100)
        capture_res = self.razorpay_client.capture_payment(
            razorpay_payment_id=payment_txn.razorpay_payment_id,
            amount_paise=amount_paise,
            currency=payment_txn.currency
        )

        if capture_res.get('status') != 'captured':
            raise SagaExecutionError("Razorpay payment capture failed", failure_reason='GATEWAY_UNAVAILABLE')

        PaymentStateMachine.transition(payment_txn, 'CAPTURED')
        payment_txn.save()

        self._record_outbox_event(
            payment_txn.transaction_id,
            'PAYMENT_CAPTURED',
            {'payment_id': payment_txn.razorpay_payment_id, 'amount': str(payment_txn.amount)}
        )

    def _step_merchant_settlement(self, payment_txn: PaymentTransaction, customer: CustomerProfile, merchant: MerchantProfile, saga_log: SagaStateLog):
        """
        Step 4: Perform ACID Ledger balance transfer between customer and merchant.
        Uses select_for_update() row-level locking + Optimistic Concurrency Control.
        """
        saga_log.current_step = 'MERCHANT_SETTLEMENT'
        saga_log.save()

        with transaction.atomic():
            # Lock customer and merchant rows
            cust_locked = CustomerProfile.objects.select_for_update().get(pk=customer.pk)
            merch_locked = MerchantProfile.objects.select_for_update().get(pk=merchant.pk)

            # Double check balance
            if cust_locked.balance < payment_txn.amount:
                raise SagaExecutionError("Customer balance changed unexpectedly during settlement", failure_reason='INSUFFICIENT_FUNDS')

            # Update customer balance with OCC
            cust_locked.balance -= payment_txn.amount
            cust_locked.version += 1
            cust_locked.save()

            # Update merchant balance with OCC
            merch_locked.balance += payment_txn.amount
            merch_locked.version += 1
            merch_locked.save()

            # Transition state machine to SETTLED
            PaymentStateMachine.transition(payment_txn, 'SETTLED')
            payment_txn.save()

            self._record_outbox_event(
                payment_txn.transaction_id,
                'PAYMENT_SETTLED',
                {
                    'merchant_id': str(merchant.merchant_id),
                    'customer_id': str(customer.customer_id),
                    'amount': str(payment_txn.amount)
                }
            )

    def _execute_compensation(self, payment_txn: PaymentTransaction, customer: CustomerProfile, merchant: MerchantProfile, saga_log: SagaStateLog, failure_reason: str, error_msg: str):
        """
        Compensating Transactions Workflow:
        Triggers inverse actions based on failure step to ensure distributed consistency.
        """
        saga_log.state = 'COMPENSATING'
        saga_log.error_message = error_msg
        saga_log.save()

        failed_step = saga_log.current_step

        try:
            with transaction.atomic():
                # If payment was captured or settled, issue refund
                if payment_txn.status in ['CAPTURED', 'SETTLED'] and payment_txn.razorpay_payment_id:
                    self.razorpay_client.issue_refund(
                        razorpay_payment_id=payment_txn.razorpay_payment_id,
                        amount_paise=int(payment_txn.amount * 100)
                    )
                    
                    # Reverse merchant settlement if merchant was already credited
                    if failed_step == 'MERCHANT_SETTLEMENT' or payment_txn.status == 'SETTLED':
                        merch_locked = MerchantProfile.objects.select_for_update().get(pk=merchant.pk)
                        if merch_locked.balance >= payment_txn.amount:
                            merch_locked.balance -= payment_txn.amount
                            merch_locked.save()
                        cust_locked = CustomerProfile.objects.select_for_update().get(pk=customer.pk)
                        cust_locked.balance += payment_txn.amount
                        cust_locked.save()

                # Transition transaction to FAILED state
                PaymentStateMachine.transition(
                    payment_txn,
                    'FAILED',
                    failure_reason=failure_reason,
                    failure_message=error_msg
                )
                payment_txn.save()

                self._record_outbox_event(
                    payment_txn.transaction_id,
                    'PAYMENT_FAILED',
                    {'failure_reason': failure_reason, 'error_message': error_msg}
                )

            saga_log.state = 'COMPENSATED'
            saga_log.save()

        except Exception as comp_err:
            logger.critical(f"Compensating transaction failed for Saga {saga_log.saga_id}: {comp_err}")
            saga_log.state = 'FAILED'
            saga_log.error_message = f"Original error: {error_msg} | Compensation error: {comp_err}"
            saga_log.save()
