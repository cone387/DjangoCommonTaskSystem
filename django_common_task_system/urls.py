from django.urls import path
from . import views
from rest_framework import routers
from django_common_task_system.generic import views as generic_views

router = routers.DefaultRouter()
router.register(r'schedule-log', views.ScheduleLogViewSet)


urlpatterns = [
    path('task/', views.TaskListView.as_view()),
    path('task/<int:pk>/', views.TaskDetailView.as_view()),
    path('schedule/list/', views.TaskScheduleListView.as_view()),
    path('schedule/retry/', views.TaskScheduleQueueAPI.retry, name='user-schedule-retry'),
    path('schedule/put/', views.TaskScheduleQueueAPI.put, name='user-schedule-put'),
    path('schedule/detail/<int:pk>/', views.TaskScheduleDetailView.as_view()),
    path('schedule/queue/<slug:code>/get/', views.TaskScheduleQueueAPI.get, name='user-schedule-get'),
    path('schedule/queue/detail/<int:pk>/', views.TaskScheduleQueueAPI.get_by_id),
    path('schedule/queue/status/', views.TaskScheduleQueueAPI.status, name='user-schedule-status'),
    path('schedule/time-parse/', generic_views.ScheduleTimeParseView.as_view()),
    path('exception/', views.ExceptionReportView.as_view(), name='user-exception-report'),
] + router.urls
