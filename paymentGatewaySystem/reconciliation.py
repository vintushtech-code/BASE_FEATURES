import logging
from datetime import timedelta
from django.utils import timezone
from paymentGatewaySystem.models import (
    PaymentTransaction, ReconciliationReport, DiscrepancyLog
)
from paymentGatewaySystem.razorpay_client import RazorpayTestClient
from paymentGatewaySystem.state_machine import PaymentStateMachine

logger = logging.getLogger(__name__)


class PendingTransactionPoller:
    """
    Scheduled background job to query status of transactions remaining in CREATED or AUTHORIZED
    state beyond predefined timeout (e.g. 15 minutes).
    """
    def __init__(self, timeout_minutes: int = 15):
        self.timeout_minutes = timeout_minutes
        self.client = RazorpayTestClient()

    def poll_and_reconcile_pending_transactions(self) -> dict:
        """
        Polls Razorpay API for all stuck/pending transactions older than timeout.
        """
        cutoff_time = timezone.now() - timedelta(minutes=self.timeout_minutes)
        pending_txns = PaymentTransaction.objects.filter(
            status__in=['CREATED', 'AUTHORIZED'],
            created_at__lte=cutoff_time
        )

        checked_count = 0
        updated_count = 0
        failed_count = 0

        for txn in pending_txns:
            checked_count += 1
            if not txn.razorpay_payment_id:
                # If order was created but never submitted to checkout, mark EXPIRED/FAILED
                PaymentStateMachine.transition(
                    txn,
                    'FAILED',
                    failure_reason='GATEWAY_UNAVAILABLE',
                    failure_message=f"Transaction timed out after {self.timeout_minutes} minutes in CREATED state."
                )
                txn.save()
                failed_count += 1
                continue

            # Query Razorpay for actual payment status
            gateway_data = self.client.fetch_payment_status(txn.razorpay_payment_id)
            gateway_status = gateway_data.get('status')

            if gateway_status == 'captured':
                PaymentStateMachine.transition(txn, 'CAPTURED')
                txn.is_reconciled = True
                txn.save()
                updated_count += 1
            elif gateway_status == 'failed':
                PaymentStateMachine.transition(
                    txn,
                    'FAILED',
                    failure_reason=gateway_data.get('error_code') or 'GATEWAY_UNAVAILABLE',
                    failure_message=gateway_data.get('error_description') or 'Payment failed on Razorpay gateway'
                )
                txn.save()
                failed_count += 1

        logger.info(f"Pending Poller finished: Checked {checked_count}, Updated {updated_count}, Failed {failed_count}")
        return {
            'checked': checked_count,
            'updated': updated_count,
            'failed': failed_count,
        }


class ReconciliationEngine:
    """
    Asynchronous Reconciliation System.
    Systematically compares internal DB records against Razorpay settlement reports.
    Identifies missing records, status mismatches, and amount discrepancies.
    """
    def __init__(self):
        self.client = RazorpayTestClient()

    def run_reconciliation(self, start_time=None, end_time=None) -> ReconciliationReport:
        """
        Runs full reconciliation for specified date range (default last 24 hours).
        """
        end_time = end_time or timezone.now()
        start_time = start_time or (end_time - timedelta(days=1))

        report = ReconciliationReport.objects.create(
            start_time=start_time,
            end_time=end_time,
            status='RUNNING'
        )

        local_txns = PaymentTransaction.objects.filter(
            created_at__gte=start_time,
            created_at__lte=end_time
        )

        total_checked = 0
        matched = 0
        discrepancies = 0

        for txn in local_txns:
            total_checked += 1
            
            # Skip unsubmitted mock transactions without Razorpay IDs
            if not txn.razorpay_payment_id:
                if txn.status in ['CAPTURED', 'SETTLED']:
                    DiscrepancyLog.objects.create(
                        report=report,
                        transaction=txn,
                        discrepancy_type='MISSING_IN_GATEWAY',
                        details={'message': f'Txn {txn.transaction_id} is marked {txn.status} in DB but lacks Razorpay Payment ID.'}
                    )
                    discrepancies += 1
                continue

            # Fetch payment status from Razorpay Test API
            gateway_info = self.client.fetch_payment_status(txn.razorpay_payment_id)
            gateway_status = gateway_info.get('status')
            gateway_amount_paise = gateway_info.get('amount', 0)
            local_amount_paise = int(txn.amount * 100)

            has_discrepancy = False

            # Check status alignment
            # Razorpay 'captured' maps to DB 'CAPTURED' or 'SETTLED'
            if gateway_status == 'captured' and txn.status not in ['CAPTURED', 'SETTLED']:
                DiscrepancyLog.objects.create(
                    report=report,
                    transaction=txn,
                    discrepancy_type='STATUS_MISMATCH',
                    details={
                        'local_status': txn.status,
                        'gateway_status': gateway_status,
                        'message': f"DB status is {txn.status} but Gateway status is captured."
                    }
                )
                has_discrepancy = True
            elif gateway_status == 'failed' and txn.status != 'FAILED':
                DiscrepancyLog.objects.create(
                    report=report,
                    transaction=txn,
                    discrepancy_type='STATUS_MISMATCH',
                    details={
                        'local_status': txn.status,
                        'gateway_status': gateway_status,
                        'message': f"DB status is {txn.status} but Gateway status is failed."
                    }
                )
                has_discrepancy = True

            # Check amount alignment
            if gateway_amount_paise != local_amount_paise:
                DiscrepancyLog.objects.create(
                    report=report,
                    transaction=txn,
                    discrepancy_type='AMOUNT_MISMATCH',
                    details={
                        'local_amount': str(txn.amount),
                        'gateway_amount_paise': gateway_amount_paise,
                        'message': f"Amount mismatch: DB={txn.amount}, Gateway paise={gateway_amount_paise}"
                    }
                )
                has_discrepancy = True

            if has_discrepancy:
                discrepancies += 1
            else:
                matched += 1
                txn.is_reconciled = True
                txn.save()

        report.total_records_checked = total_checked
        report.matched_records = matched
        report.discrepancy_count = discrepancies
        report.status = 'COMPLETED'
        report.save()

        logger.info(f"Reconciliation Report {report.report_id} complete. Checked: {total_checked}, Discrepancies: {discrepancies}")
        return report
