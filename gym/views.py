from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout as auth_logout
from django.contrib.auth.models import User
from .models import MemberProfile, WorkoutPlan

# Create your views here.
def home(request):
    return render(request, 'home.html')


def signin(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')

        if not email or not password:
            messages.error(request, 'Please enter your email and password.')
            return render(request, 'signin.html')

        user = User.objects.filter(email=email).first()
        if not user:
            messages.error(request, 'No account found for that email.')
            return render(request, 'signin.html')

        user = authenticate(request, username=user.username, password=password)
        if not user:
            messages.error(request, 'Invalid credentials.')
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

        if User.objects.filter(email=email).exists():
            messages.error(request, 'An account with that email already exists.')
            return render(request, 'signup.html')

        username = email
        user = User.objects.create_user(username=username, email=email, password=password)
        user.first_name = name.split(' ')[0]
        user.last_name = ' '.join(name.split(' ')[1:]) if len(name.split(' ')) > 1 else ''
        user.save()

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

    profile = MemberProfile.objects.filter(user=request.user).first()
    plans = WorkoutPlan.objects.filter(user=request.user).order_by('-created_at')[:3]

    context = {
        'user_name': request.user.first_name or request.user.username,
        'profile': profile,
        'plans': plans,
    }
    return render(request, 'dashboard.html', context)


def logout(request):
    auth_logout(request)
    messages.success(request, 'You have been signed out.')
    return redirect('home')


def onboarding(request):
    if not request.user.is_authenticated:
        messages.info(request, 'Please sign up before onboarding.')
        return redirect('signup')

    if request.method == 'POST':
        secondary_goals = request.POST.getlist('secondary_goals')
        tracking_metrics = request.POST.getlist('tracking_metrics')

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
                'gym_access': request.POST.get('gym_access') or '',
                'personal_coaching': request.POST.get('personal_coaching') or '',
                'coaching_style': request.POST.get('coaching_style') or '',
                'instructor_preference': request.POST.get('instructor_preference') or '',
                'tracking_metrics': ','.join(tracking_metrics),
                'progress_check_frequency': request.POST.get('progress_check_frequency') or '',
                'commitment_level': request.POST.get('commitment_level') or '',
                'consent_acknowledged': True if request.POST.get('consent_acknowledged') else False,
                'onboarding_complete': True,
                'recommendations': _build_recommendations(
                    request.POST.get('primary_goal'),
                    request.POST.get('training_type'),
                    request.POST.get('workout_frequency'),
                ),
            },
        )

        if not WorkoutPlan.objects.filter(user=request.user).exists():
            WorkoutPlan.objects.create(
                user=request.user,
                title='Starter Plan',
                summary=profile.recommendations or 'Balanced training mix for your first month.',
            )
        messages.success(request, 'Onboarding complete. Your plan is ready!')
        return redirect('dashboard')

    return render(request, 'onboarding.html')


def _build_recommendations(primary_goal, training_type, workout_frequency):
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

    return ' '.join(
        [
            goal_map.get(primary_goal, 'Balanced training mix.'),
            type_map.get(training_type, 'Flexible training environment.'),
            freq_map.get(workout_frequency, 'Stay consistent each week.'),
        ]
    )
