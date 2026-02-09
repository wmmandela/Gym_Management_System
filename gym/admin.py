from django.contrib import admin
from .models import MemberProfile, WorkoutPlan

# Register your models here.


@admin.register(MemberProfile)
class MemberProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'onboarding_complete', 'created_at')
    search_fields = ('name', 'email')
    list_filter = ('onboarding_complete', 'fitness_level', 'primary_goal', 'training_type')


@admin.register(WorkoutPlan)
class WorkoutPlanAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'created_at')
    search_fields = ('title', 'user__email')
