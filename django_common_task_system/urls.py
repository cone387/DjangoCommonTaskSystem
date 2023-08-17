from django.urls import path
from . import views
from rest_framework import routers


router = routers.DefaultRouter()
router.register(r'schedule/log', views.ScheduleLogViewSet)


urlpatterns = [
    path('task/', views.TaskListView.as_view()),
    path('task/<int:pk>/', views.TaskDetailView.as_view()),
    path('schedule/list/', views.ScheduleListView.as_view()),
    path('schedule/retry/', views.ScheduleAPI.retry, name='schedule-retry'),
    path('schedule/put/', views.ScheduleAPI.put, name='schedule-put'),
    path('schedule/put-raw/', views.ScheduleAPI.put_raw, name='schedule-put-raw'),
    path('schedule/get/<int:pk>/', views.ScheduleDetailView.as_view()),
    path('schedule/builtin/handle/<slug:name>/', views.ScheduleBuiltinHandle.as_view(), name='schedule-builtin-handle'),
    path('schedule/queue/get/<slug:code>/', views.ScheduleAPI.get, name='schedule-get'),
    path('schedule/queue/status/', views.ScheduleAPI.status, name='schedule-status'),
    path('schedule/time-parse/', views.ScheduleTimeParseView.as_view()),
    path('exception/', views.ExceptionReportView.as_view(), name='exception-report'),
    path('client/log/<int:client_id>/', views.ScheduleClientView.show_logs, name='schedule-client-log'),
    path('client/start/', views.ScheduleClientView.start_client, name='schedule-client-start'),
    path('client/stop/<int:client_id>/', views.ScheduleClientView.stop_client, name='schedule-client-stop'),
] + router.urls
