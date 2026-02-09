from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth import get_user_model

# Create your models here.


class MemberProfile(models.Model):
    User = get_user_model()
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('prefer_not', 'Prefer not to say'),
    ]

    FITNESS_LEVEL_CHOICES = [
        ('beginner', 'Beginner (new to training)'),
        ('intermediate', 'Intermediate (train occasionally)'),
        ('advanced', 'Advanced (train consistently)'),
    ]

    TRAINING_EXPERIENCE_CHOICES = [
        ('none', 'None'),
        ('home', 'Home workouts'),
        ('gym', 'Gym workouts'),
        ('personal_training', 'Personal training'),
    ]

    PRIMARY_GOAL_CHOICES = [
        ('lose_weight', 'Lose weight'),
        ('build_muscle', 'Build muscle'),
        ('improve_endurance', 'Improve endurance'),
        ('increase_flexibility', 'Increase flexibility'),
        ('general_fitness', 'General fitness'),
    ]

    TIMEFRAME_CHOICES = [
        ('1_3_months', '1–3 months'),
        ('3_6_months', '3–6 months'),
        ('6_plus', '6+ months'),
    ]

    TRAINING_TYPE_CHOICES = [
        ('home', 'Home training'),
        ('gym', 'Gym training'),
        ('hybrid', 'Hybrid (both)'),
    ]

    WORKOUT_FREQUENCY_CHOICES = [
        ('2_3_days', '2–3 days'),
        ('3_4_days', '3–4 days'),
        ('5_plus_days', '5+ days'),
    ]

    WORKOUT_DURATION_CHOICES = [
        ('20_30', '20–30 minutes'),
        ('30_45', '30–45 minutes'),
        ('45_60', '45–60 minutes'),
    ]

    TRAINING_TIME_CHOICES = [
        ('morning', 'Morning'),
        ('afternoon', 'Afternoon'),
        ('evening', 'Evening'),
        ('flexible', 'Flexible'),
    ]

    EQUIPMENT_CHOICES = [
        ('none', 'None'),
        ('dumbbells', 'Dumbbells'),
        ('bands', 'Resistance bands'),
        ('full_home_gym', 'Full home gym'),
    ]

    GYM_ACCESS_CHOICES = [
        ('no_access', 'No gym access'),
        ('commercial', 'Commercial gym'),
        ('private', 'Private gym'),
    ]

    COACHING_CHOICES = [
        ('yes', 'Yes'),
        ('no', 'No'),
        ('maybe', 'Maybe later'),
    ]

    COACHING_STYLE_CHOICES = [
        ('strict', 'Strict & structured'),
        ('supportive', 'Supportive & flexible'),
        ('mixed', 'Mixed'),
    ]

    INSTRUCTOR_PREFERENCE_CHOICES = [
        ('male', 'Male trainer'),
        ('female', 'Female trainer'),
        ('no_preference', 'No preference'),
    ]

    PROGRESS_CHECK_CHOICES = [
        ('weekly', 'Weekly'),
        ('bi_weekly', 'Bi-weekly'),
        ('monthly', 'Monthly'),
    ]

    COMMITMENT_CHOICES = [
        ('casual', 'Casual'),
        ('serious', 'Serious'),
        ('very_serious', 'Very serious'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='member_profile', null=True, blank=True)
    name = models.CharField(max_length=120)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=30)

    age = models.PositiveIntegerField(validators=[MinValueValidator(13), MaxValueValidator(80)])
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, blank=True)
    height_cm = models.PositiveIntegerField()
    weight_kg = models.PositiveIntegerField()

    fitness_level = models.CharField(max_length=30, choices=FITNESS_LEVEL_CHOICES)
    training_experience = models.CharField(max_length=30, choices=TRAINING_EXPERIENCE_CHOICES)
    health_considerations = models.TextField(blank=True)

    primary_goal = models.CharField(max_length=40, choices=PRIMARY_GOAL_CHOICES)
    secondary_goals = models.CharField(max_length=255, blank=True)
    target_weight_kg = models.PositiveIntegerField(null=True, blank=True)
    goal_timeframe = models.CharField(max_length=20, choices=TIMEFRAME_CHOICES)

    training_type = models.CharField(max_length=20, choices=TRAINING_TYPE_CHOICES)
    workout_frequency = models.CharField(max_length=20, choices=WORKOUT_FREQUENCY_CHOICES)
    workout_duration = models.CharField(max_length=20, choices=WORKOUT_DURATION_CHOICES)
    training_time = models.CharField(max_length=20, choices=TRAINING_TIME_CHOICES)

    equipment_home = models.CharField(max_length=20, choices=EQUIPMENT_CHOICES)
    gym_access = models.CharField(max_length=20, choices=GYM_ACCESS_CHOICES)

    personal_coaching = models.CharField(max_length=20, choices=COACHING_CHOICES)
    coaching_style = models.CharField(max_length=20, choices=COACHING_STYLE_CHOICES)
    instructor_preference = models.CharField(max_length=20, choices=INSTRUCTOR_PREFERENCE_CHOICES, blank=True)

    tracking_metrics = models.CharField(max_length=255, blank=True)
    progress_check_frequency = models.CharField(max_length=20, choices=PROGRESS_CHECK_CHOICES)
    commitment_level = models.CharField(max_length=20, choices=COMMITMENT_CHOICES)

    consent_acknowledged = models.BooleanField(default=False)
    onboarding_complete = models.BooleanField(default=False)
    recommendations = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.email})"


class WorkoutPlan(models.Model):
    User = get_user_model()

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='workout_plans')
    title = models.CharField(max_length=150)
    summary = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.user.email}"
