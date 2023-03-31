from django.urls import path
from . import views


urlpatterns = [
    path('schedule/queue/<slug:code>/get/', views.SystemScheduleQueueView.as_view()),
]
