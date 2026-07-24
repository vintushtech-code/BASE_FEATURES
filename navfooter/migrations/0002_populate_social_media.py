from django.db import migrations

def pre_populate_social_links(apps, schema_editor):
    SocialMediaLink = apps.get_model('navfooter', 'SocialMediaLink')
    platforms = ['whatsapp', 'linkedin', 'facebook', 'instagram', 'github']
    for platform in platforms:
        SocialMediaLink.objects.get_or_create(
            platform=platform,
            defaults={
                'url': '',
                'is_active': False
            }
        )

def remove_pre_populated_social_links(apps, schema_editor):
    SocialMediaLink = apps.get_model('navfooter', 'SocialMediaLink')
    platforms = ['whatsapp', 'linkedin', 'facebook', 'instagram', 'github']
    SocialMediaLink.objects.filter(platform__in=platforms).delete()

class Migration(migrations.Migration):

    dependencies = [
        ('navfooter', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(pre_populate_social_links, remove_pre_populated_social_links),
    ]
