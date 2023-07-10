from django.urls import path
from . import views
from rest_framework import routers
from django_common_task_system.generic.views import SystemProcessView

router = routers.DefaultRouter()
router.register(r'schedule-log', views.ScheduleLogViewSet)


urlpatterns = [
    path('schedule/produce/<int:pk>/', views.ScheduleProduceView.as_view(), name='system_schedule_produce'),
    path('schedule/queue/<slug:code>/get/', views.SystemScheduleQueueAPI.get, name='system_schedule_get'),
    path('schedule/put/', views.SystemScheduleQueueAPI.put, name='system_schedule_put'),
    path('schedule/retry/', views.SystemScheduleQueueAPI.retry, name='system_schedule_retry'),
    path('schedule/queue/status/', views.SystemScheduleQueueAPI.status, name='system_schedule_status'),
    path('process/logs/<int:process_id>/', SystemProcessView.show_logs, name='system_process_log'),
    path('process/stop/<int:process_id>/', SystemProcessView.stop_process, name='system_process_stop'),
    path('exception/report/', views.SystemExceptionReportView.as_view()),
] + router.urls
