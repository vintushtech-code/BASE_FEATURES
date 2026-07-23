import csv
from django.contrib import admin
from django.http import HttpResponse
from django.utils.timezone import localtime
from .models import ContactSubmission

@admin.action(description="Export selected submissions to CSV")
def export_submissions_to_csv(modeladmin, request, queryset):
    """Custom admin action to export selected submissions to a CSV file."""
    response = HttpResponse(
        content_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="contact_submissions.csv"'},
    )
    writer = csv.writer(response)
    # CSV Header
    writer.writerow(["ID", "Name", "Email", "Subject", "Message", "IP Address", "Created At"])
    
    for submission in queryset:
        created_at_local = localtime(submission.created_at).strftime('%Y-%m-%d %H:%M:%S')
        writer.writerow([
            submission.id,
            submission.name,
            submission.email,
            submission.subject,
            submission.message,
            submission.ip_address,
            created_at_local,
        ])
    return response

@admin.register(ContactSubmission)
class ContactSubmissionAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'subject', 'ip_address', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('name', 'email', 'subject', 'message')
    # Make all submissions read-only in the admin to prevent tampering
    readonly_fields = ('name', 'email', 'subject', 'message', 'ip_address', 'created_at')
    actions = [export_submissions_to_csv]

    def has_add_permission(self, request):
        """Disable manual creation of contact form inquiries via Admin."""
        return False
