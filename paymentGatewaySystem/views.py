import json
import logging
from decimal import Decimal
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status, views, permissions
from rest_framework.response import Response

from paymentGatewaySystem.models import (
    MerchantProfile, CustomerProfile, CardTokenVault, PaymentTransaction, ReconciliationReport
)
from paymentGatewaySystem.security import (
    MerchantAPIKeyAuthentication, IsMerchantUser, IsCustomerUser,
    encrypt_card_data, decrypt_card_data, generate_card_fingerprint
)
from paymentGatewaySystem.saga_orchestrator import PaymentSagaOrchestrator, SagaExecutionError
from paymentGatewaySystem.idempotency import handle_idempotency
from paymentGatewaySystem.razorpay_client import RazorpayTestClient
from paymentGatewaySystem.reconciliation import ReconciliationEngine, PendingTransactionPoller
from paymentGatewaySystem.state_machine import PaymentStateMachine
from paymentGatewaySystem.serializers import (
    CreateOrderSerializer, TokenizeCardSerializer, ProcessTokenPaymentSerializer,
    RefundSerializer, PaymentTransactionSerializer, CardTokenVaultSerializer,
    ReconciliationReportSerializer
)

logger = logging.getLogger(__name__)


def _get_or_create_merchant(user):
    merchant, _ = MerchantProfile.objects.get_or_create(
        user=user,
        defaults={
            'business_name': f"{user.username}'s Store",
            'api_key': f"key_live_{user.username}_12345",
            'api_secret_hash': 'secret_hash_demo'
        }
    )
    return merchant


def _get_or_create_customer(user):
    customer, _ = CustomerProfile.objects.get_or_create(
        user=user,
        defaults={'balance': Decimal('10000.00')}
    )
    return customer


class CreateOrderView(views.APIView):
    """
    POST /api/payments/create-order/
    Creates a new payment transaction & runs the distributed payment Saga.
    Supports HTTP Idempotency-Key header.
    """
    authentication_classes = [MerchantAPIKeyAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        # Idempotency wrapper execution
        return handle_idempotency(request, self._create_order_logic, *args, **kwargs)

    def _create_order_logic(self, request, *args, **kwargs):
        serializer = CreateOrderSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        amount = serializer.validated_data['amount']
        currency = serializer.validated_data['currency']
        idempotency_key = request.headers.get('Idempotency-Key') or request.META.get('HTTP_IDEMPOTENCY_KEY')
        
        # Check simulation parameters for negative test cases
        simulate_failure = request.data.get('simulate_failure')
        
        merchant = _get_or_create_merchant(request.user)
        
        cust_id = serializer.validated_data.get('customer_id')
        if cust_id:
            customer = CustomerProfile.objects.filter(customer_id=cust_id).first()
        else:
            customer = _get_or_create_customer(request.user)

        # Negative test case simulation: Fraud block check
        if simulate_failure == 'FRAUD_RISK_BLOCK':
            txn = PaymentTransaction.objects.create(
                idempotency_key=idempotency_key,
                merchant=merchant,
                customer=customer,
                amount=amount,
                currency=currency,
                status='FAILED',
                failure_reason='FRAUD_RISK_BLOCK',
                failure_message='Transaction blocked by anti-fraud risk engine.'
            )
            return Response({
                "error": "FRAUD_RISK_BLOCK",
                "message": "Transaction blocked by anti-fraud risk engine.",
                "transaction": PaymentTransactionSerializer(txn).data
            }, status=status.HTTP_403_FORBIDDEN)

        # Negative test case simulation: Invalid card data
        if simulate_failure == 'INVALID_CARD':
            txn = PaymentTransaction.objects.create(
                idempotency_key=idempotency_key,
                merchant=merchant,
                customer=customer,
                amount=amount,
                currency=currency,
                status='FAILED',
                failure_reason='INVALID_CARD',
                failure_message='Card validation error: Invalid card number or checksum.'
            )
            return Response({
                "error": "INVALID_CARD",
                "message": "Card validation error.",
                "transaction": PaymentTransactionSerializer(txn).data
            }, status=status.HTTP_400_BAD_REQUEST)

        # Initialize transaction record
        txn = PaymentTransaction.objects.create(
            idempotency_key=idempotency_key,
            merchant=merchant,
            customer=customer,
            amount=amount,
            currency=currency,
            status='CREATED'
        )

        orchestrator = PaymentSagaOrchestrator()
        
        try:
            settled_txn = orchestrator.execute_payment(txn, customer, merchant)
            return Response({
                "status": "SUCCESS",
                "message": "Payment created and settled successfully via Saga Orchestrator.",
                "transaction": PaymentTransactionSerializer(settled_txn).data
            }, status=status.HTTP_201_CREATED)

        except SagaExecutionError as e:
            return Response({
                "status": "FAILED",
                "error": e.failure_reason,
                "message": str(e),
                "transaction": PaymentTransactionSerializer(txn).data
            }, status=status.HTTP_400_BAD_REQUEST)


class TokenizeCardView(views.APIView):
    """
    POST /api/payments/tokenize-card/
    PCI-DSS Compliant Card Vault Tokenization.
    Encrypts raw card details using AES-256-GCM and returns vault token.
    Raw PAN is NEVER stored in plain text.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = TokenizeCardSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        customer = _get_or_create_customer(request.user)
        card_num = serializer.validated_data['card_number'].replace(' ', '')
        
        # Detect card network
        card_network = 'Visa'
        if card_num.startswith('5'):
            card_network = 'Mastercard'
        elif card_num.startswith('3'):
            card_network = 'Amex'
        elif card_num.startswith('6'):
            card_network = 'RuPay'

        last4 = card_num[-4:]
        fingerprint = generate_card_fingerprint(card_num, str(customer.customer_id))

        # Check existing card token
        existing_vault = CardTokenVault.objects.filter(customer=customer, fingerprint=fingerprint).first()
        if existing_vault:
            return Response({
                "message": "Card already tokenized in vault.",
                "token": CardTokenVaultSerializer(existing_vault).data
            }, status=status.HTTP_200_OK)

        # Encrypt sensitive card payload using AES-256
        encrypted_payload = encrypt_card_data({
            'card_number': card_num,
            'cvv': serializer.validated_data['cvv'],
            'exp_month': serializer.validated_data['exp_month'],
            'exp_year': serializer.validated_data['exp_year'],
        })

        vault_token = CardTokenVault.objects.create(
            customer=customer,
            encrypted_payload=encrypted_payload,
            last4=last4,
            card_network=card_network,
            expiry_month=serializer.validated_data['exp_month'],
            expiry_year=serializer.validated_data['exp_year'],
            fingerprint=fingerprint,
            razorpay_token_id=f"token_{customer.customer_id.hex[:10]}"
        )

        return Response({
            "message": "Card successfully tokenized with PCI-DSS compliance.",
            "token": CardTokenVaultSerializer(vault_token).data
        }, status=status.HTTP_201_CREATED)


class ProcessTokenPaymentView(views.APIView):
    """
    POST /api/payments/process-token-payment/
    Processes payment using tokenized card reference.
    Supports Idempotency-Key.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        return handle_idempotency(request, self._process_logic, *args, **kwargs)

    def _process_logic(self, request, *args, **kwargs):
        serializer = ProcessTokenPaymentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        customer = _get_or_create_customer(request.user)
        merchant = _get_or_create_merchant(request.user)
        token_id = serializer.validated_data['token_id']

        vault_card = CardTokenVault.objects.filter(token_id=token_id, customer=customer).first()
        if not vault_card:
            return Response({"error": "INVALID_TOKEN", "message": "Card token not found."}, status=status.HTTP_404_NOT_FOUND)

        # Decrypt payload inside secure boundary
        decrypted_card = decrypt_card_data(vault_card.encrypted_payload)

        idempotency_key = request.headers.get('Idempotency-Key') or request.META.get('HTTP_IDEMPOTENCY_KEY')
        amount = serializer.validated_data['amount']

        txn = PaymentTransaction.objects.create(
            idempotency_key=idempotency_key,
            merchant=merchant,
            customer=customer,
            amount=amount,
            currency=serializer.validated_data['currency'],
            status='CREATED'
        )

        orchestrator = PaymentSagaOrchestrator()
        try:
            settled_txn = orchestrator.execute_payment(txn, customer, merchant)
            return Response({
                "status": "SUCCESS",
                "message": "Tokenized payment processed successfully.",
                "transaction": PaymentTransactionSerializer(settled_txn).data
            }, status=status.HTTP_200_OK)
        except SagaExecutionError as e:
            return Response({
                "status": "FAILED",
                "error": e.failure_reason,
                "message": str(e),
                "transaction": PaymentTransactionSerializer(txn).data
            }, status=status.HTTP_400_BAD_REQUEST)


class RefundView(views.APIView):
    """
    POST /api/payments/refund/
    Issues a full refund for a captured or settled payment, triggering Saga compensating action.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        return handle_idempotency(request, self._refund_logic, *args, **kwargs)

    def _refund_logic(self, request, *args, **kwargs):
        serializer = RefundSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        txn_id = serializer.validated_data['transaction_id']
        txn = PaymentTransaction.objects.filter(transaction_id=txn_id).first()

        if not txn:
            return Response({"error": "NOT_FOUND", "message": "Transaction not found."}, status=status.HTTP_404_NOT_FOUND)

        if txn.status not in ['CAPTURED', 'SETTLED']:
            return Response({
                "error": "INVALID_STATE",
                "message": f"Cannot refund transaction in status '{txn.status}'."
            }, status=status.HTTP_400_BAD_REQUEST)

        merchant = txn.merchant
        customer = txn.customer

        client = RazorpayTestClient()
        if txn.razorpay_payment_id:
            refund_res = client.issue_refund(
                razorpay_payment_id=txn.razorpay_payment_id,
                amount_paise=int(txn.amount * 100)
            )

        # Perform balance reversal
        if merchant and customer:
            if merchant.balance >= txn.amount:
                merchant.balance -= txn.amount
                merchant.save()
            customer.balance += txn.amount
            customer.save()

        PaymentStateMachine.transition(txn, 'REFUNDED')
        txn.save()

        return Response({
            "status": "SUCCESS",
            "message": "Payment refunded successfully with ledger reversal.",
            "transaction": PaymentTransactionSerializer(txn).data
        }, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name='dispatch')
class WebhookView(views.APIView):
    """
    POST /api/payments/webhook/
    Asynchronous Razorpay Webhook listener.
    Verifies HMAC-SHA256 signature and updates payment status.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        sig_header = request.headers.get('X-Razorpay-Signature') or request.META.get('HTTP_X_RAZORPAY_SIGNATURE')
        client = RazorpayTestClient()

        if not client.verify_webhook_signature(request.body, sig_header):
            logger.warning("Razorpay Webhook Signature Verification Failed!")
            return Response({
                "error": "INVALID_SIGNATURE",
                "message": "Webhook HMAC signature verification failed."
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            event_payload = json.loads(request.body.decode('utf-8'))
        except Exception:
            event_payload = {}

        event_name = event_payload.get('event')
        entity = event_payload.get('payload', {}).get('payment', {}).get('entity', {})
        rzp_payment_id = entity.get('id')
        rzp_order_id = entity.get('order_id')

        logger.info(f"Received Webhook Event: {event_name} for Payment: {rzp_payment_id}")

        if rzp_order_id:
            txn = PaymentTransaction.objects.filter(razorpay_order_id=rzp_order_id).first()
            if txn:
                txn.razorpay_payment_id = rzp_payment_id or txn.razorpay_payment_id
                if event_name in ['payment.captured', 'order.paid']:
                    if txn.status != 'SETTLED':
                        PaymentStateMachine.transition(txn, 'CAPTURED')
                        txn.save()
                elif event_name == 'payment.failed':
                    PaymentStateMachine.transition(
                        txn,
                        'FAILED',
                        failure_reason=entity.get('error_code') or 'GATEWAY_UNAVAILABLE',
                        failure_message=entity.get('error_description') or 'Payment failed on Razorpay'
                    )
                    txn.save()

        return Response({"status": "EVENT_PROCESSED"}, status=status.HTTP_200_OK)


class TransactionStatusView(views.APIView):
    """
    GET /api/payments/status/<uuid:transaction_id>/
    Fetches status, state machine history, and saga logs for a transaction.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, transaction_id):
        txn = PaymentTransaction.objects.filter(transaction_id=transaction_id).first()
        if not txn:
            return Response({"error": "NOT_FOUND", "message": "Transaction not found."}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            "transaction": PaymentTransactionSerializer(txn).data
        }, status=status.HTTP_200_OK)


class RunReconciliationView(views.APIView):
    """
    POST /api/payments/reconcile/
    Triggers asynchronous reconciliation process comparing internal DB records with Razorpay settlement reports.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        engine = ReconciliationEngine()
        report = engine.run_reconciliation()
        return Response({
            "message": "Reconciliation job executed successfully.",
            "report": ReconciliationReportSerializer(report).data
        }, status=status.HTTP_200_OK)


class PollPendingPaymentsView(views.APIView):
    """
    POST /api/payments/poll-pending/
    Triggers background poller for pending transactions older than 15 minutes.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        poller = PendingTransactionPoller(timeout_minutes=0)  # Check all pending
        result = poller.poll_and_reconcile_pending_transactions()
        return Response({
            "message": "Pending transaction poller finished successfully.",
            "result": result
        }, status=status.HTTP_200_OK)


class ListTransactionsView(views.APIView):
    """
    GET /api/payments/list/
    Lists recent payment transactions for ledger UI.
    """
    authentication_classes = [MerchantAPIKeyAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        merchant = _get_or_create_merchant(request.user)
        txns = PaymentTransaction.objects.filter(merchant=merchant).order_by('-created_at')[:50]
        return Response({
            "transactions": PaymentTransactionSerializer(txns, many=True).data
        }, status=status.HTTP_200_OK)


from django.shortcuts import render

class DashboardView(views.APIView):
    """
    GET /api/payments/ui/
    Renders interactive Payment Gateway Sandbox & Console UI.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        merchant_api_key = 'key_admin_merchant_9999'
        if request.user.is_authenticated:
            merchant = _get_or_create_merchant(request.user)
            merchant_api_key = merchant.api_key
        return render(request, 'paymentGatewaySystem/dashboard.html', {
            'merchant_api_key': merchant_api_key
        })


