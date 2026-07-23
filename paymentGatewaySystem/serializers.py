from decimal import Decimal
from rest_framework import serializers
from paymentGatewaySystem.models import (
    PaymentTransaction, CardTokenVault, MerchantProfile, CustomerProfile,
    ReconciliationReport, DiscrepancyLog, SagaStateLog, OutboxEvent
)


class CreateOrderSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('1.00'))
    currency = serializers.CharField(max_length=10, default='INR')
    customer_id = serializers.UUIDField(required=False, allow_null=True)
    receipt = serializers.CharField(max_length=100, required=False, allow_blank=True)


class TokenizeCardSerializer(serializers.Serializer):
    card_number = serializers.CharField(max_length=19, min_length=13)
    exp_month = serializers.IntegerField(min_value=1, max_value=12)
    exp_year = serializers.IntegerField(min_value=2024, max_value=2050)
    cvv = serializers.CharField(max_length=4, min_length=3)
    card_holder = serializers.CharField(max_length=100, required=False)


class ProcessTokenPaymentSerializer(serializers.Serializer):
    token_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('1.00'))

    currency = serializers.CharField(max_length=10, default='INR')


class RefundSerializer(serializers.Serializer):
    transaction_id = serializers.UUIDField()
    reason = serializers.CharField(max_length=255, required=False, default="Customer requested refund")


class CardTokenVaultSerializer(serializers.ModelSerializer):
    class Meta:
        model = CardTokenVault
        fields = ['token_id', 'last4', 'card_network', 'expiry_month', 'expiry_year', 'created_at']


class SagaStateLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = SagaStateLog
        fields = ['saga_id', 'current_step', 'state', 'payload', 'error_message', 'created_at']


class OutboxEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = OutboxEvent
        fields = ['event_id', 'event_type', 'status', 'created_at']


class PaymentTransactionSerializer(serializers.ModelSerializer):
    saga_logs = SagaStateLogSerializer(many=True, read_only=True)

    class Meta:
        model = PaymentTransaction
        fields = [
            'transaction_id', 'idempotency_key', 'razorpay_order_id', 'razorpay_payment_id',
            'amount', 'currency', 'status', 'failure_reason', 'failure_message',
            'version', 'is_reconciled', 'created_at', 'updated_at', 'saga_logs'
        ]


class DiscrepancyLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = DiscrepancyLog
        fields = ['id', 'discrepancy_type', 'details', 'resolved', 'created_at']


class ReconciliationReportSerializer(serializers.ModelSerializer):
    discrepancies = DiscrepancyLogSerializer(many=True, read_only=True)

    class Meta:
        model = ReconciliationReport
        fields = [
            'report_id', 'start_time', 'end_time', 'total_records_checked',
            'matched_records', 'discrepancy_count', 'status', 'created_at', 'discrepancies'
        ]
