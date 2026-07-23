from django.core.management.base import BaseCommand
from paymentGatewaySystem.reconciliation import PendingTransactionPoller


class Command(BaseCommand):
    help = 'Scheduled background polling job to verify status of transactions remaining in a pending state beyond predefined timeout'

    def add_arguments(self, parser):
        parser.add_argument(
            '--timeout',
            type=int,
            default=15,
            help='Timeout in minutes beyond which transactions are polled (default: 15)'
        )

    def handle(self, *args, **options):
        timeout = options['timeout']
        self.stdout.write(self.style.NOTICE(f"Starting pending transaction status polling job (timeout: {timeout} mins)..."))
        
        poller = PendingTransactionPoller(timeout_minutes=timeout)
        result = poller.poll_and_reconcile_pending_transactions()

        self.stdout.write(self.style.SUCCESS(
            f"Polling completed: Checked={result['checked']}, Updated={result['updated']}, Failed={result['failed']}"
        ))
