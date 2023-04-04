from django.urls import path
from . import views


urlpatterns = [
    path('schedule/produce/<int:pk>/', views.ScheduleProduceView.as_view(), name='system_schedule_produce'),
    path('schedule/queue/<slug:code>/get/', views.SystemScheduleQueueAPI.get, name='system_schedule_queue_get'),
    path('schedule/queue/<int:pk>/put/', views.SystemScheduleQueueAPI.put, name='system_schedule_queue_put'),
    path('schedule/retry/<int:pk>/', views.SystemScheduleQueueAPI.retry, name='system_schedule_retry'),
    path('schedule/queue/', views.SystemScheduleQueueAPI.status),
]
