from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='SocialMediaLink',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('platform', models.CharField(choices=[('whatsapp', 'WhatsApp'), ('linkedin', 'LinkedIn'), ('facebook', 'Facebook'), ('instagram', 'Instagram'), ('github', 'GitHub')], max_length=20, unique=True, verbose_name='Platform Name')),
                ('url', models.URLField(blank=True, default='', help_text='Enter the full URL (e.g., https://wa.me/yourphone or https://linkedin.com/in/username)', max_length=500, verbose_name='Profile/Chat Link')),
                ('is_active', models.BooleanField(default=False, help_text='Toggle to show/hide this social media link in the footer', verbose_name='Show in Footer')),
            ],
            options={
                'verbose_name': 'Social Media Link',
                'verbose_name_plural': 'Social Media Links',
                'ordering': ['platform'],
            },
        ),
    ]
