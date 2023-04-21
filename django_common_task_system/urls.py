from django.urls import path
from . import views
from rest_framework import routers

router = routers.DefaultRouter()
router.register(r'schedule-log', views.ScheduleLogViewSet)


urlpatterns = [
    path('task/', views.TaskListView.as_view()),
    path('task/<int:pk>/', views.TaskDetailView.as_view()),
    path('schedule/list/', views.TaskScheduleListView.as_view()),
    path('schedule/retry/', views.TaskScheduleQueueAPI.retry, name='task_schedule_retry'),
    path('schedule/put/', views.TaskScheduleQueueAPI.put, name='task_schedule_put'),
    path('schedule/detail/<int:pk>/', views.TaskScheduleDetailView.as_view()),
    path('schedule/queue/<slug:code>/get/', views.TaskScheduleQueueAPI.get, name='task_schedule_get'),
    path('schedule/queue/detail/<int:pk>/', views.TaskScheduleQueueAPI.get_by_id),
    path('schedule/queue/status/', views.TaskScheduleQueueAPI.status),
    path('schedule/time-parse/', views.ScheduleTimeParseView.as_view()),
    path('exception/report/', views.ExceptionReportView.as_view()),
] + router.urls
