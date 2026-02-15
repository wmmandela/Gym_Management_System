from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('gym', '0005_timetableplan'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='WorkoutSessionEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_type', models.CharField(choices=[('start', 'Start'), ('complete', 'Complete')], max_length=12)),
                ('workout_name', models.CharField(blank=True, max_length=140)),
                ('mode', models.CharField(blank=True, max_length=20)),
                ('location', models.CharField(blank=True, max_length=20)),
                ('duration_minutes', models.PositiveIntegerField(default=0)),
                ('calories_estimated', models.PositiveIntegerField(default=0)),
                ('occurred_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='workout_session_events', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddIndex(
            model_name='workoutsessionevent',
            index=models.Index(fields=['user', 'event_type', 'occurred_at'], name='gym_workout_user_id_7fee4b_idx'),
        ),
    ]
