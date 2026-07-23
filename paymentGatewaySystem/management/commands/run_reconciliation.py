from django.core.management.base import BaseCommand
from paymentGatewaySystem.reconciliation import ReconciliationEngine


class Command(BaseCommand):
    help = 'Runs asynchronous reconciliation process comparing internal DB records against Razorpay settlement reports'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Initiating Payment Reconciliation System process..."))
        
        engine = ReconciliationEngine()
        report = engine.run_reconciliation()

        self.stdout.write(self.style.SUCCESS(
            f"Reconciliation Finished! Report ID: {report.report_id} | "
            f"Total Checked: {report.total_records_checked} | "
            f"Matched: {report.matched_records} | "
            f"Discrepancies: {report.discrepancy_count}"
        ))
