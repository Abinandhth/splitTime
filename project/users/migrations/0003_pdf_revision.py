# Generated by Django 5.1.7 on 2025-03-25 05:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_remove_settings_max'),
    ]

    operations = [
        migrations.AddField(
            model_name='pdf',
            name='revision',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
