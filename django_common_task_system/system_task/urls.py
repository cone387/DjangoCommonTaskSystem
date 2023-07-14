from django.urls import path
from . import views
from rest_framework import routers
from django_common_task_system.generic.views import TaskClientView
from django_common_task_system.generic import views as generic_views

router = routers.DefaultRouter()
router.register(r'schedule-log', views.ScheduleLogViewSet)


urlpatterns = [
    path('schedule/produce/<int:pk>/', views.ScheduleProduceView.as_view(), name='system-schedule-produce'),
    path('schedule/queue/<slug:code>/get/', views.SystemScheduleQueueAPI.get, name='system-schedule-get'),
    path('schedule/put/', views.SystemScheduleQueueAPI.put, name='system-schedule-put'),
    path('schedule/retry/', views.SystemScheduleQueueAPI.retry, name='system-schedule-retry'),
    path('schedule/queue/status/', views.SystemScheduleQueueAPI.status, name='system-schedule-status'),
    path('schedule/time-parse/', generic_views.ScheduleTimeParseView.as_view()),
    path('client/logs/<int:client_id>/', TaskClientView.show_logs, name='system-client-log'),
    path('client/stop/<int:client_id>/', TaskClientView.stop_process, name='system-client-stop'),
    path('exception/', views.ExceptionReportView.as_view(), name='system-exception-report'),
] + router.urls
