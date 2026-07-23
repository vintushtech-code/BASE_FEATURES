from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('login', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='SuperUser',
            fields=[
            ],
            options={
                'verbose_name': 'Super User',
                'verbose_name_plural': 'Super Users',
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('login.customuser',),
        ),
    ]
