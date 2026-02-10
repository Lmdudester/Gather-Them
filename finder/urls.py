from django.urls import path

from . import views

app_name = 'finder'

urlpatterns = [
    path('', views.index, name='index'),
    path('analyze/', views.analyze, name='analyze'),
    path('results/', views.results, name='results'),
    path('update-db/', views.update_db, name='update_db'),
]
