from django.urls import path
from . import views


urlpatterns = [
    path('schedule/queue/<slug:code>/get/', views.SystemScheduleQueueView.as_view(), name='system_schedule_queue_get'),
]
