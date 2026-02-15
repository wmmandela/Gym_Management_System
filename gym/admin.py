from django.contrib import admin
from .models import MemberProfile, WorkoutPlan, TimetablePlan, MealTimetablePlan, WorkoutSessionEvent

# Register your models here.


@admin.register(MemberProfile)
class MemberProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'onboarding_complete', 'created_at')
    search_fields = ('name', 'email')
    list_filter = ('onboarding_complete', 'program_type', 'fitness_level', 'primary_goal', 'training_type')


@admin.register(WorkoutPlan)
class WorkoutPlanAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'created_at')
    search_fields = ('title', 'user__email')


@admin.register(TimetablePlan)
class TimetablePlanAdmin(admin.ModelAdmin):
    list_display = ('user', 'updated_at')
    search_fields = ('user__email',)


@admin.register(MealTimetablePlan)
class MealTimetablePlanAdmin(admin.ModelAdmin):
    list_display = ('user', 'updated_at')
    search_fields = ('user__email',)


@admin.register(WorkoutSessionEvent)
class WorkoutSessionEventAdmin(admin.ModelAdmin):
    list_display = ('user', 'event_type', 'workout_name', 'duration_minutes', 'calories_estimated', 'occurred_at')
    list_filter = ('event_type', 'mode', 'location')
    search_fields = ('user__email', 'workout_name')
