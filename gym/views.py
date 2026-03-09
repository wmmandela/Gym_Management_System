from django.contrib import messages
from django.contrib.auth import authenticate, login, logout as auth_logout
from django.contrib.auth.models import User
from django.db import DatabaseError
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from datetime import date, timedelta
from django.utils import timezone

from .models import MemberProfile, WorkoutPlan, TimetablePlan, MealTimetablePlan, WorkoutSessionEvent

TRAINER_CATALOG = [
    {
        'id': 'amina-njeri',
        'name': 'Amina Njeri',
        'gender': 'female',
        'styles': ['supportive', 'mixed'],
        'specialties': ['lose_weight', 'general_fitness', 'increase_flexibility'],
        'levels': ['beginner', 'intermediate'],
        'times': ['7:00 AM', '12:30 PM', '6:30 PM'],
    },
    {
        'id': 'brian-otieno',
        'name': 'Brian Otieno',
        'gender': 'male',
        'styles': ['strict', 'mixed'],
        'specialties': ['build_muscle', 'general_fitness'],
        'levels': ['intermediate', 'advanced'],
        'times': ['6:00 AM', '5:30 PM', '7:30 PM'],
    },
    {
        'id': 'carol-wanjiku',
        'name': 'Carol Wanjiku',
        'gender': 'female',
        'styles': ['strict', 'supportive'],
        'specialties': ['improve_endurance', 'lose_weight', 'general_fitness'],
        'levels': ['beginner', 'intermediate', 'advanced'],
        'times': ['8:00 AM', '1:00 PM', '6:00 PM'],
    },
    {
        'id': 'daniel-kimani',
        'name': 'Daniel Kimani',
        'gender': 'male',
        'styles': ['strict', 'mixed'],
        'specialties': ['build_muscle', 'improve_endurance'],
        'levels': ['intermediate', 'advanced'],
        'times': ['6:30 AM', '4:30 PM', '8:00 PM'],
    },
]


def _plan_capabilities_from_access(gym_access):
    access_key = (gym_access or '').strip()
    plan_map = {
        'no_access': 'basic',
        'commercial': 'pro',
        'private': 'elite',
    }
    plan = plan_map.get(access_key, 'basic')
    return {
        'plan_key': plan,
        'plan_label': {'basic': 'Basic', 'pro': 'Pro', 'elite': 'Elite'}[plan],
        'personal_trainer': plan == 'elite',
        'nutrition_plan': plan == 'elite',
        'group_classes': plan in {'pro', 'elite'},
        'sauna_spa': plan == 'elite',
        'gym_24_7': plan in {'pro', 'elite'},
    }


def _plan_capabilities(profile):
    if not profile:
        return _plan_capabilities_from_access('')
    return _plan_capabilities_from_access(profile.gym_access)


def _has_pending_elite_upgrade(request):
    return request.session.get('pending_elite_upgrade') == '1'


def _redirect_if_pending_elite_upgrade(request):
    if _has_pending_elite_upgrade(request):
        return redirect('elite_upgrade_prompt')
    return None


def home(request):
    return render(request, 'home.html', {'category_counts': _build_home_category_counts()})


def contact_submit(request):
    if request.method != 'POST':
        return redirect('home')

    name = (request.POST.get('name') or '').strip()
    email = (request.POST.get('email') or '').strip()
    subject = (request.POST.get('subject') or '').strip()
    message_body = (request.POST.get('message') or '').strip()

    if not name or not email or not subject or not message_body:
        messages.error(request, 'Please complete all contact form fields.')
        return redirect('home')

    messages.success(request, 'Thanks for reaching out. Our team will contact you shortly.')
    return redirect('home')


def signin(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')

        if not email or not password:
            messages.error(request, 'Please enter your email and password.')
            return render(request, 'signin.html')

        try:
            user = User.objects.filter(email=email).first()
            if not user:
                messages.error(request, 'No account found for that email.')
                return render(request, 'signin.html')

            user = authenticate(request, username=user.username, password=password)
            if not user:
                messages.error(request, 'Invalid credentials.')
                return render(request, 'signin.html')
        except DatabaseError:
            messages.error(request, 'Service is temporarily unavailable. Please try again shortly.')
            return render(request, 'signin.html')

        login(request, user)
        messages.success(request, 'Signed in successfully.')
        if user.is_staff:
            return redirect('/admin/')
        return redirect('dashboard')

    return render(request, 'signin.html')


def signup(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        phone = request.POST.get('phone', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')

        if password != confirm_password:
            messages.error(request, 'Passwords do not match. Please try again.')
            return render(request, 'signup.html')

        if not (name and email and phone and password):
            messages.error(request, 'Please fill out all required fields.')
            return render(request, 'signup.html')

        try:
            if User.objects.filter(email=email).exists():
                messages.error(request, 'An account with that email already exists.')
                return render(request, 'signup.html')

            username = email
            user = User.objects.create_user(username=username, email=email, password=password)
            user.first_name = name.split(' ')[0]
            user.last_name = ' '.join(name.split(' ')[1:]) if len(name.split(' ')) > 1 else ''
            user.save()
        except DatabaseError:
            messages.error(request, 'Service is temporarily unavailable. Please try again shortly.')
            return render(request, 'signup.html')

        login(request, user)
        request.session['registered_name'] = name
        request.session['registered_phone'] = phone
        messages.success(request, 'Account created. Please complete onboarding.')
        return redirect('onboarding')

    return render(request, 'signup.html')


def dashboard(request):
    if not request.user.is_authenticated:
        messages.info(request, 'Please sign in to access your dashboard.')
        return redirect('signin')
    pending_redirect = _redirect_if_pending_elite_upgrade(request)
    if pending_redirect:
        return pending_redirect

    try:
        profile = MemberProfile.objects.filter(user=request.user).first()
    except DatabaseError:
        messages.error(request, 'Service is temporarily unavailable. Please try again shortly.')
        return redirect('home')
    if not profile or not profile.onboarding_complete:
        return _render_dashboard(request, profile=profile, dashboard_variant='generic')
    capabilities = _plan_capabilities(profile)
    if profile.program_type in {'personal_trainer', 'hybrid'} and not capabilities['personal_trainer']:
        try:
            if profile.program_type != 'individual' or profile.assigned_trainer or profile.assigned_trainer_time:
                profile.program_type = 'individual'
                profile.personal_coaching = 'no'
                profile.assigned_trainer = ''
                profile.assigned_trainer_time = ''
                profile.save(update_fields=['program_type', 'personal_coaching', 'assigned_trainer', 'assigned_trainer_time'])
        except DatabaseError:
            pass
        messages.info(request, 'Personal trainer features require Elite. You are now on the individual flow.')
    if profile.program_type in {'personal_trainer', 'hybrid'} and not profile.assigned_trainer:
        return redirect('initial_trainer_selection')
    try:
        has_timetable = TimetablePlan.objects.filter(user=request.user).exists()
    except DatabaseError:
        has_timetable = False
    if not has_timetable:
        return redirect('timetable_planner')

    if profile.program_type == 'personal_trainer':
        return redirect('personal_trainer_dashboard')
    if profile.program_type == 'hybrid':
        return redirect('hybrid_dashboard')
    return redirect('individual_dashboard')


def personal_trainer_dashboard(request):
    pending_redirect = _redirect_if_pending_elite_upgrade(request)
    if pending_redirect:
        return pending_redirect
    profile = _require_profile(request)
    if not profile:
        return redirect('dashboard')
    if not _plan_capabilities(profile)['personal_trainer']:
        messages.info(request, 'Personal trainer requires Elite. Upgrade to Elite or continue without a trainer.')
        return redirect('dashboard')
    if not profile.assigned_trainer:
        return redirect('initial_trainer_selection')

    trainers = _recommend_trainers(profile)
    return _render_dashboard(
        request,
        profile=profile,
        dashboard_variant='personal_trainer',
        trainer_recommendations=trainers,
        exercise_plan=_build_exercise_recommendations(profile),
    )


def trainer_page(request):
    pending_redirect = _redirect_if_pending_elite_upgrade(request)
    if pending_redirect:
        return pending_redirect
    profile = _require_profile(request)
    if not profile:
        return redirect('dashboard')
    if not _plan_capabilities(profile)['personal_trainer']:
        messages.info(request, 'Trainer sessions require Elite. Upgrade to Elite or continue with self-guided workouts.')
        return redirect('dashboard')

    if not profile.assigned_trainer:
        messages.info(request, 'Please select a trainer first.')
        return redirect('initial_trainer_selection')

    workout_context = _build_trainer_page_workout(profile)
    workout_sequence = _build_workout_sequence(profile)
    ui_metrics = _build_ui_metrics(profile)
    progress_metrics = _build_progress_metrics(profile)
    today_checklist = _build_today_checklist(profile)
    calendar_strip = _build_calendar_strip()
    tracking_panel = _build_tracking_panel(profile, ui_metrics, progress_metrics)
    context = {
        'user_name': request.user.first_name or request.user.username,
        'profile': profile,
        'workout_context': workout_context,
        'workout_sequence': workout_sequence,
        'ui_metrics': ui_metrics,
        'progress_metrics_url': reverse('progress_metrics_api'),
        'today_checklist': today_checklist,
        'calendar_strip': calendar_strip,
        'tracking_panel': tracking_panel,
    }
    return render(request, 'trainer_page.html', context)


def trainer_workout(request):
    pending_redirect = _redirect_if_pending_elite_upgrade(request)
    if pending_redirect:
        return pending_redirect
    profile = _require_profile(request)
    if not profile:
        return redirect('dashboard')
    if not _plan_capabilities(profile)['personal_trainer']:
        messages.info(request, 'Trainer sessions require Elite. Upgrade to Elite or continue with self-guided workouts.')
        return redirect('dashboard')
    if not profile.assigned_trainer:
        messages.info(request, 'Please select a trainer first.')
        return redirect('initial_trainer_selection')

    try:
        timetable = TimetablePlan.objects.filter(user=request.user).first()
    except DatabaseError:
        timetable = None

    day_key = (request.GET.get('day') or '').strip().lower()
    day_aliases = {
        'mon': 'monday', 'monday': 'monday',
        'tue': 'tuesday', 'tues': 'tuesday', 'tuesday': 'tuesday',
        'wed': 'wednesday', 'wednesday': 'wednesday',
        'thu': 'thursday', 'thur': 'thursday', 'thurs': 'thursday', 'thursday': 'thursday',
        'fri': 'friday', 'friday': 'friday',
        'sat': 'saturday', 'saturday': 'saturday',
        'sun': 'sunday', 'sunday': 'sunday',
    }
    requested_day = day_aliases.get(day_key, date.today().strftime('%A').lower())
    schedule = _normalize_timetable_schedule(
        profile,
        timetable.schedule if timetable else None,
    )
    selected_day = next(
        (item for item in schedule if (item.get('day') or '').strip().lower().startswith(requested_day[:3])),
        None,
    )
    if not selected_day:
        selected_day = schedule[0] if schedule else {
            'day': date.today().strftime('%A'),
            'workout': 'Coach Session',
            'coaching': 'Coach-led',
            'location': 'Gym',
        }

    coaching_mode = (selected_day.get('coaching') or '').strip()
    if coaching_mode != 'Coach-led':
        messages.info(request, 'This day is self-guided. Opening your self-guided workout session.')
        return redirect(f"{reverse('self_guided_workout')}?day={(selected_day.get('day') or '').strip().lower()}")

    workout_context = _build_trainer_page_workout(profile)
    workout_sequence = _build_workout_sequence(profile)
    trainer_session_sequence = _build_trainer_session_sequence(workout_sequence)
    total_exercise_seconds = sum(item.get('duration_sec', 0) for item in trainer_session_sequence)
    total_break_seconds = sum(item.get('break_sec', 0) for item in trainer_session_sequence[:-1]) if len(trainer_session_sequence) > 1 else 0
    total_duration_minutes = max(10, (total_exercise_seconds + total_break_seconds) // 60)
    estimated_calories = max(120, int((profile.weight_kg or 70) * max(0.08, total_duration_minutes / 10)))
    ui_metrics = _build_ui_metrics(profile)
    complete_redirect_url = reverse('hybrid_dashboard') if profile.program_type == 'hybrid' else reverse('personal_trainer_dashboard')
    context = {
        'profile': profile,
        'user_name': request.user.first_name or request.user.username,
        'selected_day': selected_day.get('day', date.today().strftime('%A')),
        'selected_day_plan': selected_day,
        'workout_context': {
            **workout_context,
            'today_workout': selected_day.get('workout') or workout_context.get('today_workout'),
        },
        'workout_sequence': workout_sequence,
        'trainer_session_sequence': trainer_session_sequence,
        'ui_metrics': ui_metrics,
        'session_duration_minutes': total_duration_minutes,
        'session_estimated_calories': estimated_calories,
        'progress_event_url': reverse('progress_event'),
        'complete_redirect_url': complete_redirect_url,
    }
    return render(request, 'trainer_workout.html', context)


def individual_dashboard(request):
    pending_redirect = _redirect_if_pending_elite_upgrade(request)
    if pending_redirect:
        return pending_redirect
    profile = _require_profile(request)
    if not profile:
        return redirect('dashboard')

    return _render_dashboard(
        request,
        profile=profile,
        dashboard_variant='individual',
        exercise_plan=_build_exercise_recommendations(profile),
    )


def hybrid_dashboard(request):
    pending_redirect = _redirect_if_pending_elite_upgrade(request)
    if pending_redirect:
        return pending_redirect
    profile = _require_profile(request)
    if not profile:
        return redirect('dashboard')
    if not _plan_capabilities(profile)['personal_trainer']:
        messages.info(request, 'Hybrid trainer sessions require Elite. Upgrade to Elite or continue with individual mode.')
        return redirect('dashboard')
    if not profile.assigned_trainer:
        return redirect('initial_trainer_selection')

    return _render_dashboard(
        request,
        profile=profile,
        dashboard_variant='hybrid',
        trainer_recommendations=_recommend_trainers(profile),
        exercise_plan=_build_exercise_recommendations(profile),
    )


def self_guided_workout(request):
    pending_redirect = _redirect_if_pending_elite_upgrade(request)
    if pending_redirect:
        return pending_redirect
    profile = _require_profile(request)
    if not profile:
        return redirect('dashboard')

    try:
        timetable = TimetablePlan.objects.filter(user=request.user).first()
    except DatabaseError:
        timetable = None

    day_key = (request.GET.get('day') or '').strip().lower()
    day_aliases = {
        'mon': 'monday', 'monday': 'monday',
        'tue': 'tuesday', 'tues': 'tuesday', 'tuesday': 'tuesday',
        'wed': 'wednesday', 'wednesday': 'wednesday',
        'thu': 'thursday', 'thur': 'thursday', 'thurs': 'thursday', 'thursday': 'thursday',
        'fri': 'friday', 'friday': 'friday',
        'sat': 'saturday', 'saturday': 'saturday',
        'sun': 'sunday', 'sunday': 'sunday',
    }
    requested_day = day_aliases.get(day_key, date.today().strftime('%A').lower())
    schedule = _normalize_timetable_schedule(
        profile,
        timetable.schedule if timetable else None,
    )
    selected_day = next(
        (item for item in schedule if (item.get('day') or '').strip().lower().startswith(requested_day[:3])),
        None,
    )
    if not selected_day:
        selected_day = schedule[0] if schedule else {
            'day': date.today().strftime('%A'),
            'workout': 'Full Body',
            'coaching': 'Self-guided',
            'location': 'Home',
        }

    coaching_mode = (selected_day.get('coaching') or '').strip()
    capabilities = _plan_capabilities(profile)
    if coaching_mode == 'Coach-led':
        if not capabilities['personal_trainer']:
            messages.info(request, 'Coach-led sessions require Elite. Continuing with self-guided workout.')
            selected_day = {
                **selected_day,
                'coaching': 'Self-guided',
            }
            coaching_mode = 'Self-guided'
        elif profile.assigned_trainer:
            messages.info(request, 'This day is coach-led. Opening your trainer workout session.')
            return redirect(f"{reverse('trainer_workout')}?day={(selected_day.get('day') or '').strip().lower()}")
        else:
            messages.info(request, 'This day is coach-led. Assign a trainer first.')
            return redirect('initial_trainer_selection')

    workout_context = _build_self_guided_workout_session(profile, selected_day)
    complete_redirect_url = reverse('hybrid_dashboard') if profile.program_type == 'hybrid' else reverse('individual_dashboard')
    context = {
        'profile': profile,
        'user_name': request.user.first_name or request.user.username,
        'selected_day': selected_day.get('day', date.today().strftime('%A')),
        'workout_context': workout_context,
        'workout_sequence': workout_context['exercises'],
        'progress_event_url': reverse('progress_event'),
        'complete_redirect_url': complete_redirect_url,
    }
    return render(request, 'self_guided_workout.html', context)


def progress_event(request):
    profile = _require_profile(request)
    if not profile:
        return JsonResponse({'ok': False, 'error': 'unauthorized'}, status=401)
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'method_not_allowed'}, status=405)

    event_type = (request.POST.get('event_type') or '').strip().lower()
    if event_type not in {'start', 'complete'}:
        return JsonResponse({'ok': False, 'error': 'invalid_event_type'}, status=400)

    duration = request.POST.get('duration_minutes', '0')
    calories = request.POST.get('calories_estimated', '0')
    try:
        duration_minutes = max(0, min(240, int(float(duration))))
    except (TypeError, ValueError):
        duration_minutes = 0
    try:
        calories_estimated = max(0, min(3000, int(float(calories))))
    except (TypeError, ValueError):
        calories_estimated = 0

    try:
        WorkoutSessionEvent.objects.create(
            user=request.user,
            event_type=event_type,
            workout_name=(request.POST.get('workout_name') or '').strip()[:140],
            mode=(request.POST.get('mode') or '').strip()[:20],
            location=(request.POST.get('location') or '').strip()[:20],
            duration_minutes=duration_minutes if event_type == 'complete' else 0,
            calories_estimated=calories_estimated if event_type == 'complete' else 0,
        )
        metrics = _build_progress_metrics(profile)
    except DatabaseError:
        metrics = _empty_progress_metrics(profile)
        return JsonResponse({'ok': False, 'error': 'db_unavailable', 'metrics': metrics}, status=503)

    return JsonResponse({'ok': True, 'metrics': metrics})


def progress_metrics_api(request):
    profile = _require_profile(request)
    if not profile:
        return JsonResponse({'ok': False, 'error': 'unauthorized'}, status=401)
    if request.method != 'GET':
        return JsonResponse({'ok': False, 'error': 'method_not_allowed'}, status=405)

    metrics = _build_progress_metrics(profile)
    payload = {
        **metrics,
        'workouts_this_week_display': f"{metrics['workouts_this_week']}/{metrics['goal_sessions']}",
        'calories_this_week_display': f"{metrics['calories_this_week']} kcal",
        'consistency_display': f"{metrics['consistency_percent']}%",
        'minutes_this_month_display': f"{metrics['minutes_this_month']} mins",
        'workouts_total_trend': f"{metrics['workouts_total']} total",
        'calories_total_trend': f"{metrics['calories_total']} total",
        'sessions_started_trend': f"{metrics['sessions_started_total']} sessions started",
        'minutes_total_trend': f"{metrics['minutes_total']} mins total",
        'weekly_completion_display': f"{metrics['workouts_this_week']}/{metrics['goal_sessions']} This Week",
        'summary_display': f"{metrics['workouts_total']} completed • {metrics['sessions_started_total']} started",
        'streak_days_display': str(metrics['current_streak_days']),
    }
    return JsonResponse({'ok': True, 'metrics': payload})


def select_trainer(request):
    pending_redirect = _redirect_if_pending_elite_upgrade(request)
    if pending_redirect:
        return pending_redirect
    profile = _require_profile(request)
    if not profile:
        return redirect('dashboard')
    if not _plan_capabilities(profile)['personal_trainer']:
        messages.info(request, 'Personal trainer requires Elite. Upgrade to Elite or continue without trainer support.')
        return redirect('dashboard')

    if request.method != 'POST':
        return redirect('dashboard')

    redirect_to = request.POST.get('redirect_to', '')
    if profile.assigned_trainer:
        messages.info(request, 'Trainer already selected.')
        if redirect_to:
            return redirect(redirect_to)
        return redirect('dashboard')

    trainer_id = request.POST.get('trainer_id', '')
    selected_time = request.POST.get('trainer_time', '')
    trainer = next((item for item in TRAINER_CATALOG if item['id'] == trainer_id), None)

    if not trainer:
        messages.error(request, 'Trainer selection not recognized. Please choose again.')
        return redirect('personal_trainer_dashboard')

    if selected_time not in trainer['times']:
        selected_time = trainer['times'][0]

    profile.assigned_trainer = trainer['name']
    profile.assigned_trainer_time = selected_time
    profile.save(update_fields=['assigned_trainer', 'assigned_trainer_time'])

    messages.success(request, f"{trainer['name']} booked for {selected_time}.")
    if redirect_to == 'hybrid_dashboard':
        return redirect('hybrid_dashboard')
    if redirect_to == 'timetable_planner':
        return redirect('timetable_planner')
    return redirect('trainer_page')


def create_hybrid_plan(request):
    pending_redirect = _redirect_if_pending_elite_upgrade(request)
    if pending_redirect:
        return pending_redirect
    profile = _require_profile(request)
    if not profile:
        return redirect('dashboard')
    if not _plan_capabilities(profile)['personal_trainer']:
        messages.info(request, 'Hybrid trainer plans require Elite. Upgrade to Elite to unlock this feature.')
        return redirect('dashboard')

    if request.method != 'POST':
        return redirect('hybrid_dashboard')

    if not profile.assigned_trainer:
        messages.info(request, 'Select a trainer first to build your hybrid rotation plan.')
        return redirect('hybrid_dashboard')

    exercise_plan = _build_exercise_recommendations(profile)
    panel = _build_hybrid_integration_panel(profile, exercise_plan)
    schedule_line = ' | '.join(
        [f"{slot['day']}: {slot['mode_label']}" for slot in panel['schedule']]
    )

    summary = (
        f"Trainer: {profile.assigned_trainer} at {profile.assigned_trainer_time}. "
        f"Weekly rotation: {schedule_line}. "
        f"Mix: {panel['coach_sessions']} coach-led / {panel['self_sessions']} self-guided, "
        f"{panel['gym_sessions']} gym / {panel['home_sessions']} home."
    )

    WorkoutPlan.objects.create(
        user=request.user,
        title='Hybrid Rotation Plan',
        summary=summary,
    )
    messages.success(request, 'Hybrid rotation plan created and saved.')
    return redirect('hybrid_dashboard')


def logout(request):
    auth_logout(request)
    messages.success(request, 'You have been signed out.')
    return redirect('home')


def onboarding(request):
    if not request.user.is_authenticated:
        messages.info(request, 'Please sign up before onboarding.')
        return redirect('signup')

    access_value = ''

    if request.method == 'POST':
        secondary_goals = request.POST.getlist('secondary_goals')
        tracking_metrics = request.POST.getlist('tracking_metrics')
        program_type = request.POST.get('program_type') or 'individual'
        gym_access = (request.POST.get('gym_access') or '').strip()
        access_value = gym_access
        if gym_access not in {'no_access', 'commercial', 'private'}:
            messages.error(
                request,
                'Please choose a plan: Basic, Pro, or Elite.',
            )
            return render(request, 'onboarding.html', {'access_value': access_value})
        plan_capabilities = _plan_capabilities_from_access(gym_access)
        requested_program_type = program_type
        if requested_program_type in {'personal_trainer', 'hybrid'} and not plan_capabilities['personal_trainer']:
            program_type = 'individual'
        coaching_from_program = {
            'personal_trainer': 'yes',
            'individual': 'no',
            'hybrid': 'maybe',
        }

        try:
            profile, _ = MemberProfile.objects.update_or_create(
                user=request.user,
                defaults={
                    'name': request.session.get('registered_name', request.user.get_full_name() or request.user.username),
                    'email': request.user.email,
                    'phone': request.session.get('registered_phone', ''),
                    'age': request.POST.get('age') or None,
                    'gender': request.POST.get('gender') or '',
                    'height_cm': request.POST.get('height_cm') or None,
                    'weight_kg': request.POST.get('weight_kg') or None,
                    'fitness_level': request.POST.get('fitness_level') or '',
                    'training_experience': request.POST.get('training_experience') or '',
                    'health_considerations': request.POST.get('health_considerations') or '',
                    'primary_goal': request.POST.get('primary_goal') or '',
                    'secondary_goals': ','.join(secondary_goals),
                    'target_weight_kg': request.POST.get('target_weight_kg') or None,
                    'goal_timeframe': request.POST.get('goal_timeframe') or '',
                    'training_type': request.POST.get('training_type') or '',
                    'workout_frequency': request.POST.get('workout_frequency') or '',
                    'workout_duration': request.POST.get('workout_duration') or '',
                    'training_time': request.POST.get('training_time') or '',
                    'equipment_home': request.POST.get('equipment_home') or '',
                    'gym_access': gym_access,
                    'personal_coaching': coaching_from_program.get(program_type, 'no'),
                    'program_type': program_type,
                    'coaching_style': request.POST.get('coaching_style') or '',
                    'instructor_preference': request.POST.get('instructor_preference') or '',
                    'assigned_trainer': '',
                    'assigned_trainer_time': '',
                    'tracking_metrics': ','.join(tracking_metrics),
                    'progress_check_frequency': request.POST.get('progress_check_frequency') or '',
                    'commitment_level': request.POST.get('commitment_level') or '',
                    'consent_acknowledged': True if request.POST.get('consent_acknowledged') else False,
                    'onboarding_complete': True,
                    'recommendations': _build_recommendations(
                        request.POST.get('primary_goal'),
                        request.POST.get('training_type'),
                        request.POST.get('workout_frequency'),
                        program_type,
                    ),
                },
            )

            if not WorkoutPlan.objects.filter(user=request.user).exists():
                WorkoutPlan.objects.create(
                    user=request.user,
                    title='Starter Plan',
                    summary=profile.recommendations or 'Balanced training mix for your first month.',
                )
        except DatabaseError:
            messages.error(request, 'Could not save onboarding right now. Please try again.')
            return render(request, 'onboarding.html', {'access_value': access_value})
        if plan_capabilities['nutrition_plan']:
            try:
                MealTimetablePlan.objects.get_or_create(
                    user=request.user,
                    defaults={'schedule': _default_meal_timetable_schedule(profile)},
                )
            except DatabaseError:
                pass
        if requested_program_type in {'personal_trainer', 'hybrid'} and program_type == 'individual':
            request.session['pending_elite_upgrade'] = '1'
            request.session['pending_requested_program_type'] = requested_program_type
            request.session['pending_selected_access'] = gym_access
            messages.warning(request, 'Your selected path needs Elite. Choose upgrade or continue without trainer.')
            return redirect('elite_upgrade_prompt')
        messages.success(request, 'Onboarding complete. Your plan is ready!')
        if profile.program_type in {'personal_trainer', 'hybrid'} and not profile.assigned_trainer:
            return redirect('initial_trainer_selection')
        return redirect('timetable_planner')

    return render(request, 'onboarding.html', {'access_value': access_value})


def _require_profile(request):
    if not request.user.is_authenticated:
        messages.info(request, 'Please sign in to access your dashboard.')
        return None

    try:
        profile = MemberProfile.objects.filter(user=request.user).first()
    except DatabaseError:
        messages.error(request, 'Service is temporarily unavailable. Please try again shortly.')
        return None
    if not profile or not profile.onboarding_complete:
        messages.info(request, 'Please complete onboarding first.')
        return None
    return profile


def _render_dashboard(request, profile, dashboard_variant, trainer_recommendations=None, exercise_plan=None):
    if request.user.is_authenticated:
        try:
            plans = WorkoutPlan.objects.filter(user=request.user).order_by('-created_at')[:3]
        except DatabaseError:
            plans = []
    else:
        plans = []
    progress_metrics = _build_progress_metrics(profile) if profile else _empty_progress_metrics(profile)
    individual_home_panel = {}
    variant_panel = {}
    hybrid_panel = {}
    meal_panel = {}
    timetable_schedule = []
    plan_caps = _plan_capabilities(profile) if profile else _plan_capabilities_from_access('')
    if profile:
        try:
            timetable = TimetablePlan.objects.filter(user=request.user).first()
            timetable_schedule = _normalize_timetable_schedule(
                profile,
                timetable.schedule if timetable else None,
            )
        except DatabaseError:
            timetable_schedule = _default_timetable_schedule(profile)
    if profile and dashboard_variant == 'individual' and profile.training_type == 'home':
        individual_home_panel = _build_individual_home_panel(profile, plans, progress_metrics, timetable_schedule, plan_caps)
    elif profile and dashboard_variant in {'personal_trainer', 'hybrid', 'individual'}:
        variant_panel = _build_dashboard_variant_panel(profile, dashboard_variant, progress_metrics, timetable_schedule, plan_caps)
    if profile and dashboard_variant == 'hybrid':
        hybrid_panel = _build_hybrid_integration_panel(profile, exercise_plan or {})
    if profile:
        meal_panel = _build_meal_dashboard_panel(profile, plan_caps)

    context = {
        'user_name': request.user.first_name or request.user.username,
        'profile': profile,
        'plans': plans,
        'dashboard_variant': dashboard_variant,
        'trainer_recommendations': trainer_recommendations or [],
        'exercise_plan': exercise_plan or {},
        'individual_home_panel': individual_home_panel,
        'variant_panel': variant_panel,
        'hybrid_panel': hybrid_panel,
        'meal_panel': meal_panel,
        'plan_caps': plan_caps,
        'progress_metrics': progress_metrics,
        'progress_metrics_url': reverse('progress_metrics_api') if profile else '',
    }
    return render(request, 'dashboard.html', context)


def initial_trainer_selection(request):
    pending_redirect = _redirect_if_pending_elite_upgrade(request)
    if pending_redirect:
        return pending_redirect
    profile = _require_profile(request)
    if not profile:
        return redirect('dashboard')
    if not _plan_capabilities(profile)['personal_trainer']:
        messages.info(request, 'Personal trainer requires Elite. Upgrade to Elite or continue without trainer support.')
        return redirect('dashboard')

    if profile.program_type not in {'personal_trainer', 'hybrid'}:
        return redirect('timetable_planner')

    if profile.assigned_trainer:
        return redirect('timetable_planner')

    trainers = _recommend_trainers(profile)
    context = {
        'user_name': request.user.first_name or request.user.username,
        'profile': profile,
        'trainer_recommendations': trainers,
    }
    return render(request, 'select_trainer.html', context)


def timetable_planner(request):
    pending_redirect = _redirect_if_pending_elite_upgrade(request)
    if pending_redirect:
        return pending_redirect
    profile = _require_profile(request)
    if not profile:
        return redirect('dashboard')
    if profile.program_type in {'personal_trainer', 'hybrid'} and not profile.assigned_trainer:
        return redirect('initial_trainer_selection')
    plan_caps = _plan_capabilities(profile)

    timetable = None
    schedule = []
    persistence_available = True
    try:
        timetable, _ = TimetablePlan.objects.get_or_create(
            user=request.user,
            defaults={'schedule': _default_timetable_schedule(profile)},
        )
        schedule = _normalize_timetable_schedule(profile, timetable.schedule)
    except DatabaseError:
        persistence_available = False
        schedule = _default_timetable_schedule(profile)
        messages.error(
            request,
            'Timetable is temporarily unavailable. Please try again shortly.'
        )

    if request.method == 'POST':
        updated = []
        for idx, item in enumerate(schedule):
            day_name = request.POST.get(f'day_{idx}_day', item.get('day', ''))
            requested_coaching = request.POST.get(f'day_{idx}_coaching', item.get('coaching', 'Self-guided'))
            if requested_coaching == 'Coach-led' and not plan_caps['personal_trainer']:
                requested_coaching = 'Self-guided'
            updated.append(
                {
                    'day': day_name or item.get('day', ''),
                    'workout': request.POST.get(f'day_{idx}_workout', item.get('workout', '')),
                    'coaching': requested_coaching,
                    'location': request.POST.get(f'day_{idx}_location', item.get('location', 'Home')),
                }
            )
        schedule = _normalize_timetable_schedule(profile, updated)

        if persistence_available and timetable:
            try:
                timetable.schedule = schedule
                timetable.save(update_fields=['schedule', 'updated_at'])
                messages.success(request, 'Timetable updated successfully.')
                return redirect('dashboard')
            except DatabaseError:
                messages.error(
                    request,
                    'Could not save timetable right now. Please try again shortly.'
                )
        else:
            messages.error(request, 'Timetable cannot be saved right now. Please try again shortly.')

    context = {
        'profile': profile,
        'user_name': request.user.first_name or request.user.username,
        'schedule': schedule,
        'plan_caps': plan_caps,
    }
    return render(request, 'timetable_planner.html', context)


def meal_timetable_planner(request):
    pending_redirect = _redirect_if_pending_elite_upgrade(request)
    if pending_redirect:
        return pending_redirect
    profile = _require_profile(request)
    if not profile:
        return redirect('dashboard')
    if not _plan_capabilities(profile)['nutrition_plan']:
        messages.info(request, 'Nutrition plan is available on Elite. Upgrade to Elite to unlock meal timetable planning.')
        return redirect('dashboard')

    meal_timetable = None
    schedule = []
    persistence_available = True
    try:
        meal_timetable, _ = MealTimetablePlan.objects.get_or_create(
            user=request.user,
            defaults={'schedule': _default_meal_timetable_schedule(profile)},
        )
        schedule = _normalize_meal_timetable_schedule(profile, meal_timetable.schedule)
    except DatabaseError:
        persistence_available = False
        schedule = _default_meal_timetable_schedule(profile)
        messages.error(
            request,
            'Meal timetable is temporarily unavailable. Please try again shortly.'
        )

    if request.method == 'POST':
        updated = []
        for idx, item in enumerate(schedule):
            day_name = request.POST.get(f'day_{idx}_day', item.get('day', ''))
            updated.append(
                {
                    'day': day_name or item.get('day', ''),
                    'breakfast': request.POST.get(f'day_{idx}_breakfast', item.get('breakfast', '')),
                    'lunch': request.POST.get(f'day_{idx}_lunch', item.get('lunch', '')),
                    'dinner': request.POST.get(f'day_{idx}_dinner', item.get('dinner', '')),
                    'snack': request.POST.get(f'day_{idx}_snack', item.get('snack', '')),
                    'water_liters': request.POST.get(f'day_{idx}_water_liters', item.get('water_liters', '2.5')),
                }
            )
        schedule = _normalize_meal_timetable_schedule(profile, updated)

        if persistence_available and meal_timetable:
            try:
                meal_timetable.schedule = schedule
                meal_timetable.save(update_fields=['schedule', 'updated_at'])
                messages.success(request, 'Meal timetable updated successfully.')
                return redirect('dashboard')
            except DatabaseError:
                messages.error(
                    request,
                    'Could not save meal timetable right now. Please try again shortly.'
                )
        else:
            messages.error(request, 'Meal timetable cannot be saved right now. Please try again shortly.')

    context = {
        'profile': profile,
        'user_name': request.user.first_name or request.user.username,
        'schedule': schedule,
        'plan_caps': _plan_capabilities(profile),
    }
    return render(request, 'meal_timetable_planner.html', context)


def elite_upgrade_prompt(request):
    if not request.user.is_authenticated:
        messages.info(request, 'Please sign in to continue.')
        return redirect('signin')

    if not _has_pending_elite_upgrade(request):
        return redirect('dashboard')

    try:
        profile = MemberProfile.objects.filter(user=request.user).first()
    except DatabaseError:
        profile = None
    if not profile:
        messages.info(request, 'Please complete onboarding first.')
        return redirect('onboarding')

    requested_program_type = request.session.get('pending_requested_program_type', 'personal_trainer')
    if requested_program_type not in {'personal_trainer', 'hybrid'}:
        requested_program_type = 'personal_trainer'

    if request.method == 'POST':
        action = (request.POST.get('action') or '').strip().lower()
        if action == 'upgrade':
            coaching_by_program = {
                'personal_trainer': 'yes',
                'hybrid': 'maybe',
            }
            try:
                profile.gym_access = 'private'
                profile.program_type = requested_program_type
                profile.personal_coaching = coaching_by_program.get(requested_program_type, 'yes')
                profile.save(update_fields=['gym_access', 'program_type', 'personal_coaching'])
            except DatabaseError:
                messages.error(request, 'Could not apply upgrade right now. Please try again.')
                return redirect('elite_upgrade_prompt')

            request.session.pop('pending_elite_upgrade', None)
            request.session.pop('pending_requested_program_type', None)
            request.session.pop('pending_selected_access', None)
            messages.success(request, 'Upgraded to Elite. Personal trainer features are now unlocked.')
            if profile.program_type in {'personal_trainer', 'hybrid'} and not profile.assigned_trainer:
                return redirect('initial_trainer_selection')
            return redirect('timetable_planner')

        if action == 'continue_without':
            try:
                profile.program_type = 'individual'
                profile.personal_coaching = 'no'
                profile.assigned_trainer = ''
                profile.assigned_trainer_time = ''
                profile.save(update_fields=['program_type', 'personal_coaching', 'assigned_trainer', 'assigned_trainer_time'])
            except DatabaseError:
                messages.error(request, 'Could not update your selection right now. Please try again.')
                return redirect('elite_upgrade_prompt')

            request.session.pop('pending_elite_upgrade', None)
            request.session.pop('pending_requested_program_type', None)
            request.session.pop('pending_selected_access', None)
            messages.info(request, 'Continuing without personal trainer on your current plan.')
            return redirect('timetable_planner')

        messages.error(request, 'Please choose an option to continue.')

    context = {
        'user_name': request.user.first_name or request.user.username,
        'profile': profile,
        'requested_program_type': requested_program_type,
        'selected_access_label': _plan_capabilities(profile)['plan_label'],
    }
    return render(request, 'elite_upgrade_prompt.html', context)


def _build_recommendations(primary_goal, training_type, workout_frequency, program_type):
    goal_map = {
        'lose_weight': 'Fat loss focus with calorie burn circuits.',
        'build_muscle': 'Progressive overload strength program.',
        'improve_endurance': 'Interval and steady-state cardio mix.',
        'increase_flexibility': 'Mobility and recovery flow sessions.',
        'general_fitness': 'Balanced full-body sessions.',
    }

    type_map = {
        'home': 'Bodyweight and minimal equipment routines.',
        'gym': 'Machine and free-weight programming.',
        'hybrid': 'Blended home and gym split.',
    }

    freq_map = {
        '2_3_days': 'Aim for 3 focused sessions weekly.',
        '3_4_days': 'A 4-day split will fit you best.',
        '5_plus_days': 'A 5-day plan with recovery blocks is ideal.',
    }

    program_map = {
        'personal_trainer': 'Trainer-led sessions with guided progression.',
        'individual': 'Independent training with self-paced tracking.',
        'hybrid': 'Mix of coached and self-guided training blocks.',
    }

    return ' '.join(
        [
            goal_map.get(primary_goal, 'Balanced training mix.'),
            type_map.get(training_type, 'Flexible training environment.'),
            freq_map.get(workout_frequency, 'Stay consistent each week.'),
            program_map.get(program_type, 'Structured plan selected.'),
        ]
    )


def _build_home_category_counts():
    defaults = {
        'weight_training_programs': 24,
        'yoga_classes': 18,
        'cardio_programs': 32,
        'spinning_classes': 12,
        'crossfit_programs': 8,
        'swimming_programs': 6,
        'nutrition_plans': 15,
        'personal_trainers': 45,
    }
    try:
        workout_plan_count = WorkoutPlan.objects.count()
        timetable_count = TimetablePlan.objects.count()
        meal_timetable_count = MealTimetablePlan.objects.count()
        distinct_trainers = (
            MemberProfile.objects.exclude(assigned_trainer__isnull=True)
            .exclude(assigned_trainer='')
            .values('assigned_trainer')
            .distinct()
            .count()
        )
        member_profiles = MemberProfile.objects.count()

        return {
            'weight_training_programs': max(workout_plan_count, member_profiles),
            'yoga_classes': max(timetable_count, member_profiles // 2),
            'cardio_programs': max(workout_plan_count, timetable_count),
            'spinning_classes': max(timetable_count // 2, 0),
            'crossfit_programs': max(workout_plan_count // 2, 0),
            'swimming_programs': max(timetable_count // 3, 0),
            'nutrition_plans': max(meal_timetable_count, 0),
            'personal_trainers': max(distinct_trainers, 0),
        }
    except DatabaseError:
        return defaults


def _recommend_trainers(profile):
    desired_blocks = {
        'morning': {'6:00 AM', '6:30 AM', '7:00 AM', '8:00 AM'},
        'afternoon': {'12:30 PM', '1:00 PM'},
        'evening': {'4:30 PM', '5:30 PM', '6:00 PM', '6:30 PM', '7:30 PM', '8:00 PM'},
        'flexible': set(),
    }
    target_times = desired_blocks.get(profile.training_time, set())

    ranked = []
    for trainer in TRAINER_CATALOG:
        score = 0
        if profile.instructor_preference and profile.instructor_preference != 'no_preference':
            if profile.instructor_preference == trainer['gender']:
                score += 4
        else:
            score += 1

        if profile.coaching_style in trainer['styles']:
            score += 3
        if profile.primary_goal in trainer['specialties']:
            score += 3
        if profile.fitness_level in trainer['levels']:
            score += 2

        matched_times = [t for t in trainer['times'] if not target_times or t in target_times]
        if matched_times:
            score += 2

        ranked.append(
            {
                **trainer,
                'score': score,
                'recommended_time': matched_times[0] if matched_times else trainer['times'][0],
            }
        )

    ranked.sort(key=lambda item: item['score'], reverse=True)
    return ranked[:3]


def _build_exercise_recommendations(profile):
    goal_map = {
        'lose_weight': {
            'home': ['Bodyweight circuits', 'Low-impact cardio intervals', 'Core conditioning'],
            'gym': ['Treadmill intervals', 'Kettlebell circuits', 'Rower conditioning'],
        },
        'build_muscle': {
            'home': ['Tempo push-ups', 'Dumbbell split squats', 'Band rows'],
            'gym': ['Barbell squats', 'Bench press', 'Lat pulldown + cable rows'],
        },
        'improve_endurance': {
            'home': ['HIIT intervals', 'Jump rope rounds', 'Steady-state cardio sessions'],
            'gym': ['Incline treadmill runs', 'Bike ergometer intervals', 'Rowing endurance blocks'],
        },
        'increase_flexibility': {
            'home': ['Mobility flow', 'Yoga mobility series', 'Core stability work'],
            'gym': ['Cable mobility rotations', 'Assisted stretching', 'Light conditioning + mobility'],
        },
        'general_fitness': {
            'home': ['Full-body bodyweight circuits', 'Core + conditioning mix', 'Mobility reset'],
            'gym': ['Machine full-body split', 'Strength + cardio combo', 'Recovery mobility'],
        },
    }

    equipment_bonus = {
        'none': ['Bodyweight squat progressions', 'Plank variations'],
        'bands': ['Band pull-aparts', 'Band-resisted glute bridges'],
        'dumbbells': ['Dumbbell thrusters', 'Dumbbell Romanian deadlifts'],
        'full_home_gym': ['Home barbell deadlifts', 'Adjustable bench pressing'],
    }

    focus = goal_map.get(profile.primary_goal, goal_map['general_fitness'])
    home_exercises = list(focus['home']) + equipment_bonus.get(profile.equipment_home, [])
    gym_exercises = list(focus['gym'])

    plan_summary = f"{profile.get_workout_frequency_display()} at {profile.get_workout_duration_display()}"

    return {
        'summary': plan_summary,
        'home_exercises': home_exercises[:5],
        'gym_exercises': gym_exercises[:5],
        'focus_label': profile.get_primary_goal_display(),
        'training_type_label': profile.get_training_type_display(),
    }


def _build_trainer_page_workout(profile):
    goal_prefix = {
        'lose_weight': 'Fat-Burn Circuit',
        'build_muscle': 'Strength Builder',
        'improve_endurance': 'Endurance Intervals',
        'increase_flexibility': 'Mobility Flow',
        'general_fitness': 'Full-Body Conditioning',
    }

    training_suffix = {
        'home': 'Home Session',
        'gym': 'Gym Session',
        'hybrid': 'Hybrid Session',
    }

    duration_map = {
        '20_30': '20–30 minutes',
        '30_45': '30–45 minutes',
        '45_60': '45–60 minutes',
    }

    frequency_map = {
        '2_3_days': '2–3 days/week',
        '3_4_days': '3–4 days/week',
        '5_plus_days': '5+ days/week',
    }

    workout_name = (
        f"{goal_prefix.get(profile.primary_goal, 'Personalized Workout')} - "
        f"{training_suffix.get(profile.training_type, 'Session')}"
    )

    return {
        'today_workout': workout_name,
        'duration': duration_map.get(profile.workout_duration, profile.get_workout_duration_display()),
        'frequency': frequency_map.get(profile.workout_frequency, profile.get_workout_frequency_display()),
        'focus': profile.get_primary_goal_display(),
        'trainer_time': profile.assigned_trainer_time or 'Not scheduled',
    }


def _build_workout_sequence(profile):
    goal_blocks = {
        'lose_weight': [
            {'name': 'Warm-Up Walk + Mobility', 'detail': 'Brisk walk with dynamic mobility drills', 'sets': '1 block', 'reps': '6 min', 'rest': 'No rest'},
            {'name': 'Bodyweight Squat to Press', 'detail': 'Controlled tempo for full-body calorie burn', 'sets': '4 sets', 'reps': '12 reps', 'rest': '45 sec'},
            {'name': 'Mountain Climbers', 'detail': 'Steady pace core-cardio combo', 'sets': '4 sets', 'reps': '30 sec', 'rest': '30 sec'},
            {'name': 'Split Squat Alternating', 'detail': 'Knee tracking and upright torso focus', 'sets': '3 sets', 'reps': '10/leg', 'rest': '45 sec'},
            {'name': 'Cool-Down Stretch', 'detail': 'Hip flexor, hamstring and thoracic stretch flow', 'sets': '1 block', 'reps': '5 min', 'rest': 'No rest'},
        ],
        'build_muscle': [
            {'name': 'Activation Warm-Up', 'detail': 'Band pulls and glute activation drills', 'sets': '1 block', 'reps': '7 min', 'rest': 'No rest'},
            {'name': 'Compound Press Pattern', 'detail': 'Bench or push-up progression based on equipment', 'sets': '5 sets', 'reps': '6-8 reps', 'rest': '90 sec'},
            {'name': 'Row Variation', 'detail': 'Dumbbell/band row with full squeeze at top', 'sets': '4 sets', 'reps': '8-10 reps', 'rest': '75 sec'},
            {'name': 'Lower Body Strength', 'detail': 'Squat or split squat progression', 'sets': '4 sets', 'reps': '8 reps', 'rest': '90 sec'},
            {'name': 'Core Stability Finisher', 'detail': 'Plank + dead bug superset', 'sets': '3 rounds', 'reps': '40 sec each', 'rest': '30 sec'},
        ],
        'improve_endurance': [
            {'name': 'Cardio Prep Warm-Up', 'detail': 'Light jog and movement prep', 'sets': '1 block', 'reps': '6 min', 'rest': 'No rest'},
            {'name': 'Interval Block 1', 'detail': 'Moderate-high interval effort', 'sets': '6 rounds', 'reps': '45 sec on', 'rest': '30 sec'},
            {'name': 'Interval Block 2', 'detail': 'Sustainable pace conditioning', 'sets': '4 rounds', 'reps': '60 sec on', 'rest': '45 sec'},
            {'name': 'Strength Endurance Circuit', 'detail': 'Push, pull and lower-body circuit flow', 'sets': '3 rounds', 'reps': '12 each move', 'rest': '60 sec'},
            {'name': 'Recovery Cool-Down', 'detail': 'Breath-led cooldown and leg mobility', 'sets': '1 block', 'reps': '6 min', 'rest': 'No rest'},
        ],
        'increase_flexibility': [
            {'name': 'Joint Prep Sequence', 'detail': 'Neck, shoulder, hip and ankle rotations', 'sets': '1 block', 'reps': '5 min', 'rest': 'No rest'},
            {'name': 'Hip Mobility Flow', 'detail': 'Deep lunge mobility and controlled transitions', 'sets': '3 rounds', 'reps': '60 sec/side', 'rest': '20 sec'},
            {'name': 'Thoracic + Shoulder Flow', 'detail': 'Open-book and wall-slide progression', 'sets': '3 rounds', 'reps': '10-12 reps', 'rest': '30 sec'},
            {'name': 'Core Control Block', 'detail': 'Slow-tempo hollow holds and bird-dogs', 'sets': '3 rounds', 'reps': '40 sec', 'rest': '30 sec'},
            {'name': 'Extended Stretch', 'detail': 'Full body decompression sequence', 'sets': '1 block', 'reps': '8 min', 'rest': 'No rest'},
        ],
        'general_fitness': [
            {'name': 'General Warm-Up', 'detail': 'Mobility and pulse-raising movement', 'sets': '1 block', 'reps': '6 min', 'rest': 'No rest'},
            {'name': 'Upper Body Compound', 'detail': 'Press + pull pairing', 'sets': '4 sets', 'reps': '10 reps each', 'rest': '60 sec'},
            {'name': 'Lower Body Compound', 'detail': 'Squat/hinge pairing', 'sets': '4 sets', 'reps': '10 reps each', 'rest': '75 sec'},
            {'name': 'Cardio Booster', 'detail': 'Short high-output interval block', 'sets': '5 rounds', 'reps': '30 sec', 'rest': '30 sec'},
            {'name': 'Mobility Reset', 'detail': 'Cooldown with flexibility emphasis', 'sets': '1 block', 'reps': '5 min', 'rest': 'No rest'},
        ],
    }

    mode_adjustments = {
        'home': 'Use home setup and bodyweight/dumbbells where available.',
        'gym': 'Use gym machines/free weights for load progression.',
        'hybrid': 'Alternate home and gym variations per exercise.',
    }

    icon_cycle = ['🔥', '🏋️', '⚡', '🧠', '🧘']
    base = goal_blocks.get(profile.primary_goal, goal_blocks['general_fitness'])
    sequence = []
    for index, item in enumerate(base):
        sequence.append(
            {
                **item,
                'icon': icon_cycle[index % len(icon_cycle)],
                'instruction': mode_adjustments.get(profile.training_type, 'Train with available equipment.'),
            }
        )

    return sequence


def _build_ui_metrics(profile):
    weight = profile.weight_kg or 70
    goal_adjust = {
        'lose_weight': -220,
        'build_muscle': 260,
        'improve_endurance': 90,
        'increase_flexibility': -20,
        'general_fitness': 40,
    }
    calories_target = max(1500, int((weight * 30) + goal_adjust.get(profile.primary_goal, 0)))
    water_liters = round(max(2.0, min(4.0, weight * 0.035)), 1)
    protein_g = max(80, int(weight * 1.4))
    completion = {
        '2_3_days': 62,
        '3_4_days': 74,
        '5_plus_days': 86,
    }.get(profile.workout_frequency, 68)

    return {
        'calories_target': calories_target,
        'water_liters': water_liters,
        'protein_g': protein_g,
        'completion': completion,
    }


def _build_today_checklist(profile):
    return [
        f"Warm up 6-8 minutes before {profile.assigned_trainer_time or 'your session'}",
        f"Complete {profile.get_workout_duration_display()} training block",
        "Log form quality and effort after each workout step",
        "Finish cooldown and hydration before ending session",
    ]


def _build_calendar_strip():
    today = date.today()
    days = []
    for offset in range(-2, 3):
        d = today + timedelta(days=offset)
        days.append(
            {
                'day_name': d.strftime('%a'),
                'day_number': d.day,
                'is_today': offset == 0,
            }
        )
    return days


def _build_tracking_panel(profile, ui_metrics, progress_metrics):
    label_map = {
        'weight': 'Weight',
        'measurements': 'Body measurements',
        'workout_completion': 'Workout completion',
        'strength_progression': 'Strength progression',
    }

    selected = [item.strip() for item in (profile.tracking_metrics or '').split(',') if item.strip()]
    selected_labels = [label_map[item] for item in selected if item in label_map]

    if 'Weight' not in selected_labels:
        selected_labels.append('Weight')
    if 'Workout completion' not in selected_labels:
        selected_labels.append('Workout completion')

    tracking_items = []
    for label in selected_labels:
        if label == 'Weight':
            tracking_items.append({'name': label, 'value': f"{profile.weight_kg} kg", 'trend': '-0.2 kg this week'})
        elif label == 'Body measurements':
            tracking_items.append({'name': label, 'value': 'Waist/hip check', 'trend': 'Update every 2 weeks'})
        elif label == 'Workout completion':
            tracking_items.append(
                {
                    'name': label,
                    'value': f"{progress_metrics['consistency_percent']}%",
                    'value_key': 'consistency_display',
                    'trend': f"{progress_metrics['workouts_this_week']}/{progress_metrics['goal_sessions']} this week",
                    'trend_key': 'weekly_completion_display',
                }
            )
        elif label == 'Strength progression':
            tracking_items.append(
                {
                    'name': label,
                    'value': f"{progress_metrics['minutes_this_month']} mins",
                    'value_key': 'minutes_this_month_display',
                    'trend': f"{progress_metrics['workouts_total']} completed",
                    'trend_key': 'summary_display',
                }
            )

    tracking_items.append(
        {
            'name': 'Hydration',
            'value': f"{ui_metrics['water_liters']} L",
            'trend': 'Daily goal',
        }
    )
    return tracking_items


def _build_individual_home_panel(profile, plans, progress_metrics, timetable_schedule, plan_caps):
    today_workout_by_goal = {
        'lose_weight': 'Full Body Fat Burn',
        'build_muscle': 'Home Strength Builder',
        'improve_endurance': 'Cardio Endurance Blast',
        'increase_flexibility': 'Mobility Flow Reset',
        'general_fitness': 'Total Body Conditioning',
    }

    weekly_templates = {
        'lose_weight': ['Cardio', 'Core', 'HIIT', 'Upper Body', 'Lower Body', 'Rest', 'Stretch'],
        'build_muscle': ['Push', 'Pull', 'Legs', 'Upper Body', 'Lower Body', 'Rest', 'Mobility'],
        'improve_endurance': ['Cardio Intervals', 'Core', 'Tempo HIIT', 'Upper Body', 'Leg Endurance', 'Rest', 'Stretch'],
        'increase_flexibility': ['Mobility', 'Core', 'Yoga Flow', 'Upper Mobility', 'Lower Mobility', 'Rest', 'Stretch'],
        'general_fitness': ['Cardio', 'Core', 'HIIT', 'Upper Body', 'Lower Body', 'Rest', 'Stretch'],
    }

    schedule = _build_weekly_schedule_from_timetable(profile, timetable_schedule)
    today_schedule = _get_today_schedule_item(timetable_schedule)
    start_workout_url = _resolve_workout_url(profile, today_schedule, plan_caps)

    goal_sessions = {
        '2_3_days': 5,
        '3_4_days': 6,
        '5_plus_days': 7,
    }.get(profile.workout_frequency, 5)

    completed_sessions = progress_metrics['workouts_this_week']
    completed_or_today = min(goal_sessions, completed_sessions)
    completion_pct = progress_metrics['consistency_percent']

    base_calories = {
        '20_30': 220,
        '30_45': 340,
        '45_60': 460,
    }.get(profile.workout_duration, 300)
    calories_burned = progress_metrics['calories_this_week'] or max(0, base_calories * completed_sessions)

    weight_change = {
        'lose_weight': '-0.6 kg',
        'build_muscle': '+0.3 kg',
        'improve_endurance': '-0.2 kg',
        'increase_flexibility': '-0.1 kg',
        'general_fitness': '-0.2 kg',
    }.get(profile.primary_goal, '-0.2 kg')

    equipment_map = {
        'none': [],
        'dumbbells': [{'name': 'Dumbbells', 'icon': '🏋️'}],
        'bands': [{'name': 'Resistance Band', 'icon': '🧵'}],
        'full_home_gym': [
            {'name': 'Yoga Mat', 'icon': '🧘'},
            {'name': 'Dumbbells', 'icon': '🏋️'},
            {'name': 'Resistance Band', 'icon': '🧵'},
        ],
    }
    equipment_list = equipment_map.get(profile.equipment_home, [])
    if not equipment_list and profile.equipment_home == 'none':
        equipment_note = 'Bodyweight only workout'
    else:
        names = [item['name'] for item in equipment_list]
        if 'Yoga Mat' not in names:
            equipment_list.insert(0, {'name': 'Yoga Mat', 'icon': '🧘'})
        equipment_note = ''

    metrics = [m.strip() for m in (profile.tracking_metrics or '').split(',') if m.strip()]
    calorie_target = max(1500, int((profile.weight_kg or 70) * 30))
    nutrition_snapshot = {
        'show': bool(metrics) and plan_caps['nutrition_plan'],
        'daily_calorie_target': calorie_target,
        'water_intake': f"{round(max(2.0, min(4.0, (profile.weight_kg or 70) * 0.035)), 1)} L",
        'meal_plan_link': reverse('meal_timetable_planner'),
        'calorie_progress_pct': min(100, int((calories_burned / max(1, calorie_target)) * 100)),
    } if metrics and plan_caps['nutrition_plan'] else {'show': False}
    if not plan_caps['nutrition_plan']:
        nutrition_snapshot['upgrade_note'] = 'Nutrition plan is available on Elite.'

    achievement_tier = 'Bronze'
    if completed_sessions >= 5:
        achievement_tier = 'Silver'
    if completed_sessions >= 6:
        achievement_tier = 'Gold'

    minutes_per_session = {'20_30': 25, '30_45': 38, '45_60': 52}.get(profile.workout_duration, 30)
    total_minutes_month = progress_metrics['minutes_this_month']

    panel = {
        'today_workout': (today_schedule.get('workout') if today_schedule else '') or today_workout_by_goal.get(profile.primary_goal, 'Full Body Session'),
        'duration': profile.get_workout_duration_display(),
        'goal': profile.get_primary_goal_display(),
        'level': profile.get_fitness_level_display(),
        'streak_days': progress_metrics['current_streak_days'],
        'weekly_schedule': schedule,
        'start_workout_url': start_workout_url,
        'weekly_completion': f"{completed_or_today}/{goal_sessions} This Week",
        'weekly_completion_pct': min(100, int((completed_or_today / max(1, goal_sessions)) * 100)),
        'snapshot_cards': [
            {'title': 'Workouts This Week', 'icon': '✅', 'value': f"{completed_sessions}/{goal_sessions}", 'metric_key': 'workouts_this_week_display', 'trend': f"{progress_metrics['workouts_total']} total", 'trend_key': 'workouts_total_trend', 'trend_dir': 'up', 'subtitle': 'Weekly overview'},
            {'title': 'Calories Burned', 'icon': '🔥', 'value': f"{calories_burned} kcal", 'metric_key': 'calories_this_week_display', 'trend': f"{progress_metrics['calories_total']} total", 'trend_key': 'calories_total_trend', 'trend_dir': 'up', 'subtitle': 'Weekly overview'},
            {'title': 'Weight Change', 'icon': '⚖️', 'value': weight_change, 'trend': '-0.3 kg', 'trend_dir': 'down', 'subtitle': 'Compared to last week'},
            {'title': 'Consistency', 'icon': '📈', 'value': f"{completion_pct}%", 'metric_key': 'consistency_display', 'trend': f"{progress_metrics['sessions_started_total']} sessions started", 'trend_key': 'sessions_started_trend', 'trend_dir': 'up', 'subtitle': 'Current status'},
        ],
        'quick_actions': [
            {'label': 'View Full Plan', 'icon': '📋'},
            {'label': 'View Progress', 'icon': '📈'},
            {'label': 'Adjust Schedule', 'icon': '📅'},
            {'label': 'Change Goal', 'icon': '🎯'},
            {'label': 'Browse Programs', 'icon': '🎥'},
        ],
        'equipment_list': equipment_list,
        'equipment_note': equipment_note,
        'achievement': f"Completed {min(goal_sessions, completed_sessions)} workouts this week!",
        'motivation': 'Keep your streak alive!',
        'achievement_tier': achievement_tier,
        'nutrition': nutrition_snapshot,
        'total_minutes_month': total_minutes_month,
    }
    if plan_caps['nutrition_plan']:
        panel['quick_actions'].insert(3, {'label': 'Meal Timetable', 'icon': '🍽️'})
    return panel


def _build_dashboard_variant_panel(profile, dashboard_variant, progress_metrics, timetable_schedule, plan_caps):
    weekly_templates = {
        'lose_weight': ['Cardio', 'Core', 'HIIT', 'Upper Body', 'Lower Body', 'Rest', 'Stretch'],
        'build_muscle': ['Push', 'Pull', 'Legs', 'Upper Body', 'Lower Body', 'Rest', 'Mobility'],
        'improve_endurance': ['Cardio Intervals', 'Core', 'Tempo HIIT', 'Upper Body', 'Leg Endurance', 'Rest', 'Stretch'],
        'increase_flexibility': ['Mobility', 'Core', 'Yoga Flow', 'Upper Mobility', 'Lower Mobility', 'Rest', 'Stretch'],
        'general_fitness': ['Cardio', 'Core', 'HIIT', 'Upper Body', 'Lower Body', 'Rest', 'Stretch'],
    }

    schedule = _build_weekly_schedule_from_timetable(profile, timetable_schedule)
    today_schedule = _get_today_schedule_item(timetable_schedule)
    action_url = _resolve_workout_url(profile, today_schedule, plan_caps)
    completed = progress_metrics['workouts_this_week']
    goal_sessions = {'2_3_days': 5, '3_4_days': 6, '5_plus_days': 7}.get(profile.workout_frequency, 5)
    completion_pct = progress_metrics['consistency_percent']
    streak_days = progress_metrics['current_streak_days']

    hero_title_map = {
        'personal_trainer': 'Today: Coaching Session Focus',
        'hybrid': 'Today: Hybrid Performance Session',
        'individual': 'Today: Structured Gym Session',
    }
    action_map = {
        'personal_trainer': 'Open Trainer Session',
        'hybrid': 'Start Workout Session',
        'individual': 'Start Workout Session',
    }
    if today_schedule and today_schedule.get('coaching') == 'Coach-led' and plan_caps['personal_trainer']:
        action_map['hybrid'] = 'Open Trainer Session'

    panel = {
        'hero_title': hero_title_map.get(dashboard_variant, 'Today: Workout Session'),
        'goal': profile.get_primary_goal_display(),
        'level': profile.get_fitness_level_display(),
        'streak_days': streak_days,
        'duration': profile.get_workout_duration_display(),
        'weekly_completion': f"{completed}/{goal_sessions} This Week",
        'weekly_completion_pct': completion_pct,
        'weekly_schedule': schedule,
        'action_url': action_url,
        'action_label': action_map.get(dashboard_variant, 'Start Workout'),
        'snapshot_cards': [
            {'title': 'Workouts This Week', 'icon': '✅', 'value': f"{completed}/{goal_sessions}", 'metric_key': 'workouts_this_week_display', 'trend': f"{progress_metrics['workouts_total']} total", 'trend_key': 'workouts_total_trend', 'trend_dir': 'up', 'subtitle': 'Weekly overview'},
            {'title': 'Focus Goal', 'icon': '🎯', 'value': profile.get_primary_goal_display(), 'trend': 'On track', 'trend_dir': 'up', 'subtitle': 'Current cycle'},
            {'title': 'Level', 'icon': '📊', 'value': profile.get_fitness_level_display(), 'trend': 'Stable', 'trend_dir': 'up', 'subtitle': 'Current status'},
            {'title': 'Consistency', 'icon': '📈', 'value': f"{completion_pct}%", 'metric_key': 'consistency_display', 'trend': f"{progress_metrics['minutes_total']} mins total", 'trend_key': 'minutes_total_trend', 'trend_dir': 'up', 'subtitle': 'Current status'},
        ],
        'quick_actions': [
            {'label': 'View Full Plan', 'icon': '📋'},
            {'label': 'View Progress', 'icon': '📈'},
            {'label': 'Adjust Schedule', 'icon': '📅'},
            {'label': 'Change Goal', 'icon': '🎯'},
            {'label': 'Browse Programs', 'icon': '🎥'},
        ],
    }
    if plan_caps['nutrition_plan']:
        panel['quick_actions'].insert(3, {'label': 'Meal Timetable', 'icon': '🍽️'})
    return panel


def _build_weekly_schedule(primary_goal, weekly_templates):
    day_labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    weekly_plan = weekly_templates.get(primary_goal, weekly_templates['general_fitness'])
    today_index = date.today().weekday()

    schedule = []
    for idx, day in enumerate(day_labels):
        if idx < today_index:
            status = 'completed'
        elif idx == today_index:
            status = 'today'
        else:
            status = 'upcoming'
        if weekly_plan[idx].lower() == 'rest':
            status = 'rest'
        status_icon = {
            'completed': '✔',
            'today': '🔥',
            'upcoming': '⏳',
            'rest': '•',
        }.get(status, '•')
        schedule.append({'day': day, 'workout': weekly_plan[idx], 'status': status, 'icon': status_icon})
    return schedule


def _get_today_schedule_item(timetable_schedule):
    if not timetable_schedule:
        return None
    idx = date.today().weekday()
    if idx < len(timetable_schedule):
        return timetable_schedule[idx]
    return timetable_schedule[0]


def _resolve_workout_url(profile, schedule_item, plan_caps=None):
    if plan_caps is None:
        plan_caps = _plan_capabilities(profile)
    selected_day = (schedule_item.get('day') if schedule_item else date.today().strftime('%A'))
    selected_day = (selected_day or date.today().strftime('%A')).strip().lower()
    if schedule_item and schedule_item.get('coaching') == 'Coach-led' and plan_caps['personal_trainer']:
        return f"{reverse('trainer_workout')}?day={selected_day}"

    return f"{reverse('self_guided_workout')}?day={selected_day}"


def _build_weekly_schedule_from_timetable(profile, timetable_schedule):
    if not timetable_schedule:
        timetable_schedule = _default_timetable_schedule(profile)

    today_index = date.today().weekday()
    plan_caps = _plan_capabilities(profile)
    schedule = []
    for idx, item in enumerate(timetable_schedule[:7]):
        workout_name = (item.get('workout') or 'Workout').strip()
        if idx < today_index:
            status = 'completed'
        elif idx == today_index:
            status = 'today'
        else:
            status = 'upcoming'
        if workout_name.lower() == 'rest' or (item.get('coaching') or '').strip().lower() == 'recovery':
            status = 'rest'
        status_icon = {
            'completed': '✔',
            'today': '🔥',
            'upcoming': '⏳',
            'rest': '•',
        }.get(status, '•')
        day_name = (item.get('day') or '').strip()
        day_label = day_name[:3].title() if day_name else ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][idx]
        schedule.append(
            {
                'day': day_label,
                'workout': workout_name,
                'status': status,
                'icon': status_icon,
                'link': _resolve_workout_url(profile, item, plan_caps),
            }
        )
    return schedule


def _build_hybrid_integration_panel(profile, exercise_plan):
    goal_sessions = {'2_3_days': 4, '3_4_days': 5, '5_plus_days': 6}.get(profile.workout_frequency, 5)
    rotation_modes = [
        {'coaching': 'Coach-led', 'location': 'Gym'},
        {'coaching': 'Self-guided', 'location': 'Home'},
        {'coaching': 'Self-guided', 'location': 'Gym'},
        {'coaching': 'Coach-led', 'location': 'Home'},
    ]

    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    schedule = []
    for idx, day in enumerate(days[:goal_sessions]):
        mode = rotation_modes[idx % len(rotation_modes)]
        coaching = mode['coaching']
        location = mode['location']
        schedule.append(
            {
                'day': day,
                'coaching': coaching,
                'location': location,
                'focus': profile.get_primary_goal_display(),
                'mode_label': f"{coaching} • {location}",
            }
        )

    coach_sessions = sum(1 for item in schedule if item['coaching'] == 'Coach-led')
    self_sessions = goal_sessions - coach_sessions
    gym_sessions = sum(1 for item in schedule if item['location'] == 'Gym')
    home_sessions = goal_sessions - gym_sessions

    home_ex = (exercise_plan.get('home_exercises') or [])[:2]
    gym_ex = (exercise_plan.get('gym_exercises') or [])[:2]

    return {
        'coach_sessions': coach_sessions,
        'self_sessions': self_sessions,
        'gym_sessions': gym_sessions,
        'home_sessions': home_sessions,
        'schedule': schedule,
        'blended_workouts': [
            {'type': 'Home + Self-guided', 'items': home_ex or ['Bodyweight conditioning', 'Mobility flow']},
            {'type': 'Gym + Coach-led', 'items': gym_ex or ['Compound lift progression', 'Trainer-assisted form work']},
        ],
        'integration_note': 'Hybrid plan rotates all modes (coach/self and home/gym) for balanced progress.',
        'assigned_trainer': profile.assigned_trainer,
        'assigned_trainer_time': profile.assigned_trainer_time,
    }


def _default_timetable_schedule(profile):
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    template_by_goal = {
        'lose_weight': ['Cardio', 'Core + Mobility', 'HIIT', 'Upper Body', 'Lower Body', 'Rest', 'Stretch'],
        'build_muscle': ['Push', 'Pull', 'Legs', 'Upper Body', 'Lower Body', 'Rest', 'Mobility'],
        'improve_endurance': ['Intervals', 'Core', 'Tempo', 'Upper Body', 'Endurance Legs', 'Rest', 'Stretch'],
        'increase_flexibility': ['Mobility', 'Core Control', 'Yoga Flow', 'Upper Mobility', 'Lower Mobility', 'Rest', 'Stretch'],
        'general_fitness': ['Cardio', 'Core', 'HIIT', 'Upper Body', 'Lower Body', 'Rest', 'Stretch'],
    }
    workouts = template_by_goal.get(profile.primary_goal, template_by_goal['general_fitness'])
    plan_caps = _plan_capabilities(profile)

    schedule = []
    for idx, day in enumerate(days):
        if workouts[idx].lower() == 'rest':
            coaching = 'Recovery'
            location = 'Home'
        else:
            if profile.program_type == 'hybrid':
                coaching = 'Coach-led' if (idx % 2 == 0 and plan_caps['personal_trainer']) else 'Self-guided'
                location = 'Gym' if idx % 2 == 0 else 'Home'
            elif profile.program_type == 'personal_trainer' and plan_caps['personal_trainer']:
                coaching = 'Coach-led'
                location = 'Gym'
            else:
                coaching = 'Self-guided'
                location = 'Home' if profile.training_type == 'home' else 'Gym'

        schedule.append(
            {
                'day': day,
                'workout': workouts[idx],
                'coaching': coaching,
                'location': location,
            }
        )
    return schedule


def _normalize_timetable_schedule(profile, raw_schedule):
    default_schedule = _default_timetable_schedule(profile)
    plan_caps = _plan_capabilities(profile)
    if not isinstance(raw_schedule, list) or not raw_schedule:
        return default_schedule

    normalized = []
    for idx in range(7):
        default_item = default_schedule[idx]
        source = raw_schedule[idx] if idx < len(raw_schedule) else {}
        if not isinstance(source, dict):
            source = {}
        coaching = source.get('coaching') or default_item['coaching']
        if coaching not in {'Coach-led', 'Self-guided', 'Recovery'}:
            coaching = default_item['coaching']
        if coaching == 'Coach-led' and not plan_caps['personal_trainer']:
            coaching = 'Self-guided'
        location = source.get('location') or default_item['location']
        if location not in {'Home', 'Gym'}:
            location = default_item['location']
        normalized.append(
            {
                'day': source.get('day') or default_item['day'],
                'workout': source.get('workout') or default_item['workout'],
                'coaching': coaching,
                'location': location,
            }
        )
    return normalized


def _default_meal_timetable_schedule(profile):
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    goal_templates = {
        'lose_weight': {
            'breakfast': 'Greek yogurt + berries + chia',
            'lunch': 'Grilled chicken salad + avocado',
            'dinner': 'Baked fish + veggies + quinoa',
            'snack': 'Apple + handful of nuts',
        },
        'build_muscle': {
            'breakfast': 'Oats + banana + eggs',
            'lunch': 'Rice + lean beef + vegetables',
            'dinner': 'Chicken + sweet potato + greens',
            'snack': 'Protein shake + peanut butter toast',
        },
        'improve_endurance': {
            'breakfast': 'Oats + fruit + yogurt',
            'lunch': 'Whole grain wrap + turkey + salad',
            'dinner': 'Pasta + lean protein + vegetables',
            'snack': 'Banana + trail mix',
        },
        'increase_flexibility': {
            'breakfast': 'Smoothie bowl + seeds',
            'lunch': 'Salmon bowl + leafy greens',
            'dinner': 'Tofu stir-fry + brown rice',
            'snack': 'Carrot sticks + hummus',
        },
        'general_fitness': {
            'breakfast': 'Egg omelet + whole grain toast',
            'lunch': 'Chicken wrap + side salad',
            'dinner': 'Lean protein + mixed vegetables',
            'snack': 'Fruit + yogurt',
        },
    }
    template = goal_templates.get(profile.primary_goal, goal_templates['general_fitness'])
    # profile.weight_kg may be a string right after onboarding update_or_create.
    try:
        weight_kg = float(profile.weight_kg or 70)
    except (TypeError, ValueError):
        weight_kg = 70.0
    water_target = round(max(2.0, min(4.0, weight_kg * 0.035)), 1)

    schedule = []
    for idx, day in enumerate(days):
        snack = template['snack']
        if idx in {5, 6}:
            snack = f"{template['snack']} (lighter weekend option)"
        schedule.append(
            {
                'day': day,
                'breakfast': template['breakfast'],
                'lunch': template['lunch'],
                'dinner': template['dinner'],
                'snack': snack,
                'water_liters': f"{water_target}",
            }
        )
    return schedule


def _normalize_meal_timetable_schedule(profile, raw_schedule):
    default_schedule = _default_meal_timetable_schedule(profile)
    if not isinstance(raw_schedule, list) or not raw_schedule:
        return default_schedule

    normalized = []
    for idx in range(7):
        default_item = default_schedule[idx]
        source = raw_schedule[idx] if idx < len(raw_schedule) else {}
        if not isinstance(source, dict):
            source = {}

        water_raw = source.get('water_liters', default_item['water_liters'])
        try:
            water_value = float(water_raw)
        except (TypeError, ValueError):
            water_value = float(default_item['water_liters'])
        water_value = min(6.0, max(1.0, water_value))

        normalized.append(
            {
                'day': (source.get('day') or default_item['day']).strip()[:20],
                'breakfast': (source.get('breakfast') or default_item['breakfast']).strip()[:180],
                'lunch': (source.get('lunch') or default_item['lunch']).strip()[:180],
                'dinner': (source.get('dinner') or default_item['dinner']).strip()[:180],
                'snack': (source.get('snack') or default_item['snack']).strip()[:180],
                'water_liters': f"{water_value:.1f}",
            }
        )
    return normalized


def _build_meal_dashboard_panel(profile, plan_caps):
    if not plan_caps['nutrition_plan']:
        return {
            'enabled': False,
            'days_planned': 0,
            'planner_url': reverse('onboarding'),
            'today': {
                'day': date.today().strftime('%A'),
                'breakfast': 'Upgrade to Elite to unlock personalized nutrition.',
                'lunch': 'Upgrade to Elite to unlock personalized nutrition.',
                'dinner': 'Upgrade to Elite to unlock personalized nutrition.',
                'snack': 'Upgrade to Elite to unlock personalized nutrition.',
                'water_liters': '2.5',
            },
            'upgrade_message': 'Nutrition plan is available on Elite. Upgrade from onboarding to unlock this feature.',
        }
    try:
        meal_timetable, _ = MealTimetablePlan.objects.get_or_create(
            user=profile.user,
            defaults={'schedule': _default_meal_timetable_schedule(profile)},
        )
        schedule = _normalize_meal_timetable_schedule(profile, meal_timetable.schedule)
    except DatabaseError:
        schedule = _default_meal_timetable_schedule(profile)

    today_idx = date.today().weekday()
    today_meal = schedule[today_idx] if today_idx < len(schedule) else schedule[0]

    return {
        'enabled': True,
        'today': today_meal,
        'days_planned': len([item for item in schedule if item.get('breakfast') or item.get('lunch') or item.get('dinner')]),
        'schedule': schedule,
        'planner_url': reverse('meal_timetable_planner'),
    }


def _empty_progress_metrics(profile):
    goal_sessions = {'2_3_days': 5, '3_4_days': 6, '5_plus_days': 7}.get(
        getattr(profile, 'workout_frequency', ''),
        5,
    ) if profile else 5
    return {
        'sessions_started_total': 0,
        'workouts_total': 0,
        'workouts_this_week': 0,
        'minutes_total': 0,
        'minutes_this_month': 0,
        'calories_total': 0,
        'calories_this_week': 0,
        'current_streak_days': 0,
        'consistency_percent': 0,
        'goal_sessions': goal_sessions,
    }


def _build_progress_metrics(profile):
    metrics = _empty_progress_metrics(profile)
    if not profile or not profile.user_id:
        return metrics
    try:
        now = timezone.localtime()
        today = now.date()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)

        started_qs = WorkoutSessionEvent.objects.filter(user=profile.user, event_type='start')
        complete_qs = WorkoutSessionEvent.objects.filter(user=profile.user, event_type='complete')

        metrics['sessions_started_total'] = started_qs.count()
        metrics['workouts_total'] = complete_qs.count()
        metrics['workouts_this_week'] = complete_qs.filter(occurred_at__date__gte=week_start).count()

        totals = complete_qs.aggregate(
            minutes=Sum('duration_minutes'),
            calories=Sum('calories_estimated'),
        )
        metrics['minutes_total'] = totals['minutes'] or 0
        metrics['calories_total'] = totals['calories'] or 0

        month_totals = complete_qs.filter(occurred_at__date__gte=month_start).aggregate(
            minutes=Sum('duration_minutes'),
        )
        metrics['minutes_this_month'] = month_totals['minutes'] or 0

        week_totals = complete_qs.filter(occurred_at__date__gte=week_start).aggregate(
            calories=Sum('calories_estimated'),
        )
        metrics['calories_this_week'] = week_totals['calories'] or 0

        goal = max(1, metrics['goal_sessions'])
        metrics['consistency_percent'] = min(100, int((metrics['workouts_this_week'] / goal) * 100))

        session_dates = set(
            complete_qs.values_list('occurred_at__date', flat=True)
        )
        if not session_dates:
            metrics['current_streak_days'] = 0
            return metrics

        cursor = today
        if cursor not in session_dates:
            if (cursor - timedelta(days=1)) in session_dates:
                cursor = cursor - timedelta(days=1)
            else:
                metrics['current_streak_days'] = 0
                return metrics

        streak = 0
        while cursor in session_dates:
            streak += 1
            cursor = cursor - timedelta(days=1)
        metrics['current_streak_days'] = streak
        return metrics
    except DatabaseError:
        return metrics


def _build_trainer_session_sequence(workout_sequence):
    sequence = []
    for idx, item in enumerate(workout_sequence, start=1):
        name = (item.get('name') or '').lower()
        reps_time = (item.get('reps') or '').lower()
        rest_text = (item.get('rest') or '').lower()

        if 'warm' in name or 'cool' in name:
            duration_sec = 60
        elif 'interval' in name or 'cardio' in name or 'climber' in name:
            duration_sec = 45
        elif 'stretch' in name or 'mobility' in name:
            duration_sec = 50
        else:
            duration_sec = 40

        if 'min' in reps_time:
            duration_sec = 60

        digits = ''.join(ch for ch in rest_text if ch.isdigit())
        break_sec = int(digits) if digits else 25
        break_sec = max(15, min(90, break_sec))

        demo = 'squat'
        if 'press' in name or 'push' in name:
            demo = 'press'
        elif 'row' in name or 'pull' in name:
            demo = 'row'
        elif 'deadlift' in name:
            demo = 'deadlift'
        elif 'lunge' in name or 'split' in name:
            demo = 'lunge'
        elif 'plank' in name:
            demo = 'plank'
        elif 'mountain' in name:
            demo = 'mountain_climber'
        elif 'stretch' in name or 'mobility' in name:
            demo = 'stretch'
        elif 'interval' in name or 'walk' in name or 'cardio' in name:
            demo = 'run'

        sequence.append(
            {
                'step': idx,
                'name': item.get('name', f'Exercise {idx}'),
                'instruction': item.get('instruction') or item.get('detail') or 'Follow trainer cue and keep clean form.',
                'duration_sec': duration_sec,
                'break_sec': break_sec,
                'demo': demo,
            }
        )
    return sequence


def _build_self_guided_workout_session(profile, day_plan):
    workout_name = (day_plan.get('workout') or 'Full Body').strip()
    location = (day_plan.get('location') or 'Home').strip().title()
    focus = workout_name.lower()
    if focus == 'rest':
        focus = 'recovery'

    home_routines = {
        'cardio': [
            {'name': 'Jumping Jacks', 'duration_sec': 40, 'break_sec': 20, 'demo': 'jumping_jacks', 'instruction': 'Land softly and keep a steady rhythm.'},
            {'name': 'High Knees', 'duration_sec': 35, 'break_sec': 20, 'demo': 'high_knees', 'instruction': 'Drive knees up to hip height with active arms.'},
            {'name': 'Mountain Climbers', 'duration_sec': 40, 'break_sec': 25, 'demo': 'mountain_climber', 'instruction': 'Keep hips level and core tight.'},
            {'name': 'Skater Hops', 'duration_sec': 35, 'break_sec': 25, 'demo': 'lunge', 'instruction': 'Push laterally and stabilize on landing.'},
        ],
        'core': [
            {'name': 'Forearm Plank', 'duration_sec': 45, 'break_sec': 20, 'demo': 'plank', 'instruction': 'Neutral spine and strong glute squeeze.'},
            {'name': 'Dead Bug', 'duration_sec': 40, 'break_sec': 20, 'demo': 'core', 'instruction': 'Move opposite arm/leg while lower back stays down.'},
            {'name': 'Bicycle Crunch', 'duration_sec': 40, 'break_sec': 25, 'demo': 'core', 'instruction': 'Rotate through the torso, not the neck.'},
            {'name': 'Side Plank', 'duration_sec': 35, 'break_sec': 20, 'demo': 'plank', 'instruction': 'Stack shoulders and keep hips lifted.'},
        ],
        'hiit': [
            {'name': 'Burpees', 'duration_sec': 35, 'break_sec': 30, 'demo': 'burpee', 'instruction': 'Control each phase and breathe on standing.'},
            {'name': 'Squat Jumps', 'duration_sec': 30, 'break_sec': 30, 'demo': 'squat', 'instruction': 'Explode up and absorb landing softly.'},
            {'name': 'Push-up + Shoulder Tap', 'duration_sec': 35, 'break_sec': 25, 'demo': 'pushup', 'instruction': 'Keep hips steady during taps.'},
            {'name': 'Fast Feet', 'duration_sec': 30, 'break_sec': 25, 'demo': 'high_knees', 'instruction': 'Quick light steps on the balls of your feet.'},
        ],
        'upper': [
            {'name': 'Push-Ups', 'duration_sec': 40, 'break_sec': 30, 'demo': 'pushup', 'instruction': 'Keep elbows at a 45-degree angle.'},
            {'name': 'Pike Push-Ups', 'duration_sec': 35, 'break_sec': 30, 'demo': 'press', 'instruction': 'Drive crown of head down then press away.'},
            {'name': 'Band Rows', 'duration_sec': 40, 'break_sec': 25, 'demo': 'row', 'instruction': 'Lead with elbows and squeeze shoulder blades.'},
            {'name': 'Triceps Dips', 'duration_sec': 35, 'break_sec': 25, 'demo': 'press', 'instruction': 'Control descent and keep chest lifted.'},
        ],
        'lower': [
            {'name': 'Bodyweight Squats', 'duration_sec': 45, 'break_sec': 25, 'demo': 'squat', 'instruction': 'Sit hips back and keep heels planted.'},
            {'name': 'Reverse Lunges', 'duration_sec': 40, 'break_sec': 25, 'demo': 'lunge', 'instruction': 'Step back softly and maintain upright torso.'},
            {'name': 'Glute Bridge', 'duration_sec': 40, 'break_sec': 20, 'demo': 'bridge', 'instruction': 'Drive through heels and pause at top.'},
            {'name': 'Calf Raises', 'duration_sec': 35, 'break_sec': 20, 'demo': 'squat', 'instruction': 'Move through full ankle range with control.'},
        ],
        'mobility': [
            {'name': 'Hip Flexor Stretch', 'duration_sec': 45, 'break_sec': 15, 'demo': 'stretch', 'instruction': 'Tuck pelvis slightly and breathe slowly.'},
            {'name': 'World’s Greatest Stretch', 'duration_sec': 45, 'break_sec': 15, 'demo': 'stretch', 'instruction': 'Rotate thoracic spine toward front leg.'},
            {'name': 'Cat-Cow Flow', 'duration_sec': 40, 'break_sec': 15, 'demo': 'yoga', 'instruction': 'Coordinate spine movement with breath.'},
            {'name': 'Thoracic Rotations', 'duration_sec': 40, 'break_sec': 15, 'demo': 'stretch', 'instruction': 'Keep hips stable while rotating upper back.'},
        ],
        'recovery': [
            {'name': 'Breathing Reset', 'duration_sec': 60, 'break_sec': 15, 'demo': 'yoga', 'instruction': 'Inhale 4 sec, exhale 6 sec.'},
            {'name': 'Gentle Yoga Flow', 'duration_sec': 60, 'break_sec': 15, 'demo': 'yoga', 'instruction': 'Move slowly and stay in pain-free range.'},
            {'name': 'Light Mobility', 'duration_sec': 60, 'break_sec': 20, 'demo': 'stretch', 'instruction': 'Focus on tight areas from the week.'},
        ],
    }
    gym_routines = {
        'cardio': [
            {'name': 'Treadmill Intervals', 'duration_sec': 60, 'break_sec': 30, 'demo': 'run', 'instruction': 'Increase pace on work intervals.'},
            {'name': 'Row Erg Sprints', 'duration_sec': 45, 'break_sec': 30, 'demo': 'row', 'instruction': 'Leg drive first, then pull and recover.'},
            {'name': 'Bike Intervals', 'duration_sec': 50, 'break_sec': 30, 'demo': 'bike', 'instruction': 'Maintain smooth cadence throughout.'},
            {'name': 'Battle Rope Waves', 'duration_sec': 35, 'break_sec': 30, 'demo': 'press', 'instruction': 'Brace core and generate waves from shoulders.'},
        ],
        'core': [
            {'name': 'Cable Crunch', 'duration_sec': 40, 'break_sec': 25, 'demo': 'core', 'instruction': 'Flex through spine and control return.'},
            {'name': 'Hanging Knee Raise', 'duration_sec': 35, 'break_sec': 30, 'demo': 'core', 'instruction': 'Avoid swinging; keep reps strict.'},
            {'name': 'Plank', 'duration_sec': 45, 'break_sec': 20, 'demo': 'plank', 'instruction': 'Neck neutral and ribs down.'},
            {'name': 'Russian Twist', 'duration_sec': 40, 'break_sec': 20, 'demo': 'core', 'instruction': 'Rotate torso and keep feet grounded.'},
        ],
        'hiit': [
            {'name': 'Assault Bike Sprint', 'duration_sec': 30, 'break_sec': 30, 'demo': 'bike', 'instruction': 'Drive hard through full body each sprint.'},
            {'name': 'Kettlebell Swings', 'duration_sec': 35, 'break_sec': 30, 'demo': 'deadlift', 'instruction': 'Hinge pattern, explosive hip extension.'},
            {'name': 'Burpee Box Step-over', 'duration_sec': 35, 'break_sec': 30, 'demo': 'burpee', 'instruction': 'Keep transitions smooth and controlled.'},
            {'name': 'Row Sprint', 'duration_sec': 35, 'break_sec': 30, 'demo': 'row', 'instruction': 'Maintain consistent stroke power.'},
        ],
        'upper': [
            {'name': 'Bench Press', 'duration_sec': 45, 'break_sec': 45, 'demo': 'press', 'instruction': 'Shoulders packed and bar path controlled.'},
            {'name': 'Lat Pulldown', 'duration_sec': 40, 'break_sec': 35, 'demo': 'row', 'instruction': 'Pull elbows down and avoid momentum.'},
            {'name': 'Seated Shoulder Press', 'duration_sec': 40, 'break_sec': 35, 'demo': 'press', 'instruction': 'Press through full range without arching.'},
            {'name': 'Cable Row', 'duration_sec': 40, 'break_sec': 30, 'demo': 'row', 'instruction': 'Pause at contraction for better tension.'},
        ],
        'lower': [
            {'name': 'Goblet Squat', 'duration_sec': 45, 'break_sec': 40, 'demo': 'squat', 'instruction': 'Keep chest tall and knees tracking toes.'},
            {'name': 'Romanian Deadlift', 'duration_sec': 45, 'break_sec': 40, 'demo': 'deadlift', 'instruction': 'Hinge hips back and keep bar close.'},
            {'name': 'Walking Lunge', 'duration_sec': 40, 'break_sec': 30, 'demo': 'lunge', 'instruction': 'Step long enough to keep front shin vertical.'},
            {'name': 'Leg Press', 'duration_sec': 40, 'break_sec': 35, 'demo': 'squat', 'instruction': 'Drive evenly through feet, full control.'},
        ],
        'mobility': home_routines['mobility'],
        'recovery': home_routines['recovery'],
    }

    if 'core' in focus:
        routine_key = 'core'
    elif 'hiit' in focus or 'interval' in focus or 'tempo' in focus:
        routine_key = 'hiit'
    elif 'upper' in focus or 'push' in focus or 'pull' in focus:
        routine_key = 'upper'
    elif 'lower' in focus or 'legs' in focus:
        routine_key = 'lower'
    elif 'mobility' in focus or 'stretch' in focus or 'yoga' in focus:
        routine_key = 'mobility'
    elif 'rest' in focus or 'recovery' in focus:
        routine_key = 'recovery'
    else:
        routine_key = 'cardio'

    routines = gym_routines if location == 'Gym' else home_routines
    sequence = list(routines.get(routine_key, routines['cardio']))
    for idx, item in enumerate(sequence, start=1):
        item['step'] = idx

    total_exercise_seconds = sum(item['duration_sec'] for item in sequence)
    total_break_seconds = sum(item['break_sec'] for item in sequence[:-1])
    total_seconds = total_exercise_seconds + total_break_seconds

    return {
        'title': f"{workout_name} • {location}",
        'location': location,
        'coaching': day_plan.get('coaching', 'Self-guided'),
        'focus': profile.get_primary_goal_display(),
        'level': profile.get_fitness_level_display(),
        'workout_name': workout_name,
        'estimated_duration': f"{max(10, total_seconds // 60)} min",
        'total_duration_minutes': max(10, total_seconds // 60),
        'estimated_calories': max(120, int((profile.weight_kg or 70) * max(0.08, total_seconds / 1200))),
        'tips': [
            'Warm up for 3-5 minutes before starting.',
            'Keep water close and take controlled breaths during sets.',
            'Prioritize form quality over speed.',
            'Use the break timer fully before the next effort.',
        ],
        'exercises': sequence,
    }
