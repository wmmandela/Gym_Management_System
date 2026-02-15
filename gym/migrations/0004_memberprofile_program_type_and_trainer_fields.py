from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gym', '0003_create_admin_user'),
    ]

    operations = [
        migrations.AddField(
            model_name='memberprofile',
            name='assigned_trainer',
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name='memberprofile',
            name='assigned_trainer_time',
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name='memberprofile',
            name='program_type',
            field=models.CharField(choices=[('personal_trainer', 'Personal trainer'), ('individual', 'Individual'), ('hybrid', 'Hybrid')], default='individual', max_length=20),
        ),
    ]
