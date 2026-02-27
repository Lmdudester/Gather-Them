from django.urls import path

from . import views

app_name = 'finder'

urlpatterns = [
    path('', views.index, name='index'),
    path('analyze/', views.analyze, name='analyze'),
    path('results/', views.results, name='results'),
    path('update-db/', views.update_db, name='update_db'),
    path('refresh-patterns/', views.refresh_patterns, name='refresh_patterns'),
    path('admin-login/', views.admin_login, name='admin_login'),
    path('admin-logout/', views.admin_logout, name='admin_logout'),
    path('api/random-flavor/', views.random_flavor, name='random_flavor'),
]
