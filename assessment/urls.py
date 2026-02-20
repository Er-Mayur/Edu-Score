from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('candidate/login/', views.candidate_login, name='candidate_login'),
    path('candidate/logout/', views.candidate_logout, name='candidate_logout'),
    path('candidate/start/', views.start_test, name='start_test'),
    path('candidate/initialize/', views.initialize_test, name='initialize_test'),
    path('candidate/take/', views.take_test, name='take_test'),
    path('candidate/submit/', views.submit_test, name='submit_test'),
    path('candidate/save_answer/', views.save_answer, name='save_answer'),
    path('candidate/log_warning/', views.log_warning, name='log_warning'),
    path('candidate/result/<int:attempt_id>/', views.result_view, name='result_view'),
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('create-test/', views.create_test, name='create_test'),
    path('delete-test/<int:test_id>/', views.delete_test, name='delete_test'),
]
