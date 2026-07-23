from django.core.management.base import BaseCommand
from django.utils import timezone
from paymentGatewaySystem.models import OutboxEvent


class Command(BaseCommand):
    help = 'Processes pending events from the Transactional Outbox pattern queue'

    def handle(self, *args, **options):
        pending_events = OutboxEvent.objects.filter(status='PENDING').order_by('created_at')[:50]
        processed_count = 0

        for event in pending_events:
            # Simulate event publishing to message bus (e.g. Kafka / RabbitMQ / SQS)
            event.status = 'PROCESSED'
            event.processed_at = timezone.now()
            event.save()
            processed_count += 1

        self.stdout.write(self.style.SUCCESS(f"Outbox Processor: Successfully published {processed_count} events."))
