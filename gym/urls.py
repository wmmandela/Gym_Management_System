from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('contact/', views.contact_submit, name='contact_submit'),
    path('signin/', views.signin, name='signin'),
    path('signup/', views.signup, name='signup'),
    path('onboarding/', views.onboarding, name='onboarding'),
    path('onboarding/elite-upgrade/', views.elite_upgrade_prompt, name='elite_upgrade_prompt'),
    path('onboarding/select-trainer/', views.initial_trainer_selection, name='initial_trainer_selection'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/timetable/', views.timetable_planner, name='timetable_planner'),
    path('dashboard/meal-timetable/', views.meal_timetable_planner, name='meal_timetable_planner'),
    path('dashboard/self-guided-workout/', views.self_guided_workout, name='self_guided_workout'),
    path('dashboard/progress-event/', views.progress_event, name='progress_event'),
    path('dashboard/progress-metrics/', views.progress_metrics_api, name='progress_metrics_api'),
    path('dashboard/personal-trainer/', views.personal_trainer_dashboard, name='personal_trainer_dashboard'),
    path('dashboard/trainer-page/', views.trainer_page, name='trainer_page'),
    path('dashboard/trainer-workout/', views.trainer_workout, name='trainer_workout'),
    path('dashboard/individual/', views.individual_dashboard, name='individual_dashboard'),
    path('dashboard/hybrid/', views.hybrid_dashboard, name='hybrid_dashboard'),
    path('dashboard/select-trainer/', views.select_trainer, name='select_trainer'),
    path('dashboard/create-hybrid-plan/', views.create_hybrid_plan, name='create_hybrid_plan'),
    path('logout/', views.logout, name='logout'),
]
