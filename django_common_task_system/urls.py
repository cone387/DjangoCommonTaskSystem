from django.urls import path
from . import views
from rest_framework import routers

router = routers.DefaultRouter()
router.register(r'schedule-log', views.ScheduleLogViewSet)


urlpatterns = [
    path('task/', views.TaskListView.as_view()),
    path('task/<int:pk>/', views.TaskDetailView.as_view()),
    path('schedule/', views.TaskScheduleListView.as_view()),
    path('schedule/retry/<int:pk>/', views.TaskScheduleQueueAPI.retry, name='task_schedule_retry'),
    path('schedule/<int:pk>/', views.TaskScheduleDetailView.as_view()),
    path('schedule/queue/get/', views.TaskScheduleQueueAPI.get),
    path('schedule/queue/', views.TaskScheduleQueueAPI.status),
    path('schedule/queue/<int:pk>/', views.TaskScheduleQueueAPI.get_by_id),
    path('schedule/time-parse/', views.ScheduleTimeParseView.as_view()),
] + router.urls
