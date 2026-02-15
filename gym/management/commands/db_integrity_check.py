from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import OperationalError, ProgrammingError
from django.db.models import Count, Q
from django.utils import timezone

from gym.models import MemberProfile, WorkoutPlan


class Command(BaseCommand):
    help = "Run PostgreSQL data integrity checks for users, profiles, plans, and onboarding consistency."

    def handle(self, *args, **options):
        now = timezone.now()
        seven_days_ago = now - timedelta(days=7)

        try:
            User = get_user_model()

            user_count = User.objects.count()
            profile_count = MemberProfile.objects.count()
            plan_count = WorkoutPlan.objects.count()

            users_without_profile = User.objects.filter(member_profile__isnull=True).count()
            profiles_without_user = MemberProfile.objects.filter(user__isnull=True).count()

            onboarding_incomplete = MemberProfile.objects.filter(onboarding_complete=False).count()
            onboarding_missing_fields = MemberProfile.objects.filter(
                onboarding_complete=True
            ).filter(
                Q(primary_goal='')
                | Q(training_type='')
                | Q(workout_frequency='')
                | Q(workout_duration='')
                | Q(program_type='')
            ).count()

            personal_without_assignment = MemberProfile.objects.filter(
                program_type='personal_trainer'
            ).filter(Q(assigned_trainer='') | Q(assigned_trainer_time='')).count()

            duplicate_profile_emails = (
                MemberProfile.objects.values('email')
                .annotate(c=Count('id'))
                .filter(c__gt=1)
                .count()
            )

            plans_without_owner = WorkoutPlan.objects.filter(user__isnull=True).count()
            recent_profiles = MemberProfile.objects.filter(created_at__gte=seven_days_ago).count()
            recent_plans = WorkoutPlan.objects.filter(created_at__gte=seven_days_ago).count()

            self.stdout.write(self.style.SUCCESS("=== PostgreSQL Integrity Report ==="))
            self.stdout.write(f"Users: {user_count}")
            self.stdout.write(f"Member profiles: {profile_count}")
            self.stdout.write(f"Workout plans: {plan_count}")
            self.stdout.write("-")

            self._emit_check("Users without profile", users_without_profile)
            self._emit_check("Profiles without user", profiles_without_user)
            self._emit_check("Onboarding incomplete profiles", onboarding_incomplete, warn_if_positive=False)
            self._emit_check("Onboarding complete but missing required fields", onboarding_missing_fields)
            self._emit_check("Personal-trainer profiles missing trainer assignment", personal_without_assignment)
            self._emit_check("Duplicate profile emails", duplicate_profile_emails)
            self._emit_check("Plans without owner", plans_without_owner)

            self.stdout.write("-")
            self.stdout.write(f"Recent profiles (last 7 days): {recent_profiles}")
            self.stdout.write(f"Recent plans (last 7 days): {recent_plans}")
            self.stdout.write(self.style.SUCCESS("=== End Report ==="))

        except (OperationalError, ProgrammingError) as exc:
            self.stdout.write(self.style.ERROR("Database integrity check failed: unable to query PostgreSQL."))
            self.stdout.write(self.style.WARNING(f"Details: {exc}"))
            self.stdout.write(self.style.WARNING("Ensure PostgreSQL is running and migrations are applied."))

    def _emit_check(self, label, count, warn_if_positive=True):
        if count == 0:
            self.stdout.write(self.style.SUCCESS(f"PASS: {label}: {count}"))
        elif warn_if_positive:
            self.stdout.write(self.style.WARNING(f"WARN: {label}: {count}"))
        else:
            self.stdout.write(f"INFO: {label}: {count}")
