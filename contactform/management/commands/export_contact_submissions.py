import csv
import json
from django.core.management.base import BaseCommand, CommandError
from django.utils.timezone import localtime
from contactform.models import ContactSubmission

class Command(BaseCommand):
    help = 'Backup contact form submissions to a CSV or JSON file.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--format',
            type=str,
            choices=['csv', 'json'],
            default='csv',
            help='Output format: csv or json (default: csv)'
        )
        parser.add_argument(
            '--output',
            type=str,
            required=True,
            help='Output file path (e.g. backup.csv or backup.json)'
        )

    def handle(self, *args, **options):
        fmt = options['format']
        output_path = options['output']
        
        submissions = ContactSubmission.objects.all().order_by('created_at')
        
        if not submissions.exists():
            self.stdout.write(self.style.WARNING("No contact submissions found in the database."))
            return

        try:
            if fmt == 'csv':
                with open(output_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(["ID", "Name", "Email", "Subject", "Message", "IP Address", "Created At"])
                    for sub in submissions:
                        created_at_str = localtime(sub.created_at).strftime('%Y-%m-%d %H:%M:%S')
                        writer.writerow([
                            sub.id,
                            sub.name,
                            sub.email,
                            sub.subject,
                            sub.message,
                            sub.ip_address,
                            created_at_str
                        ])
            else:
                # JSON format
                data = []
                for sub in submissions:
                    created_at_str = localtime(sub.created_at).strftime('%Y-%m-%d %H:%M:%S')
                    data.append({
                        'id': sub.id,
                        'name': sub.name,
                        'email': sub.email,
                        'subject': sub.subject,
                        'message': sub.message,
                        'ip_address': sub.ip_address,
                        'created_at': created_at_str
                    })
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)

            self.stdout.write(self.style.SUCCESS(f"Successfully backed up {submissions.count()} submissions to {output_path}"))
        except Exception as e:
            raise CommandError(f"Failed to export contact submissions: {e}")
