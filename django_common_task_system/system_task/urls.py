from django.urls import path
from . import views
from rest_framework import routers
from django_common_task_system.generic.views import TaskClientView

router = routers.DefaultRouter()
router.register(r'schedule-log', views.ScheduleLogViewSet)


urlpatterns = [
    path('schedule/produce/<int:pk>/', views.ScheduleProduceView.as_view(), name='system_schedule_produce'),
    path('schedule/queue/<slug:code>/get/', views.SystemScheduleQueueAPI.get, name='system_schedule_get'),
    path('schedule/put/', views.SystemScheduleQueueAPI.put, name='system_schedule_put'),
    path('schedule/retry/', views.SystemScheduleQueueAPI.retry, name='system_schedule_retry'),
    path('schedule/queue/status/', views.SystemScheduleQueueAPI.status, name='system_schedule_status'),
    path('client/logs/<int:client_id>/', TaskClientView.show_logs, name='system_client_log'),
    path('client/stop/<int:client_id>/', TaskClientView.stop_process, name='system_client_stop'),
    path('exception/report/', views.SystemExceptionReportView.as_view()),
] + router.urls
