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
    path('schedule/detail/<int:pk>/', views.ScheduleDetailView.as_view()),
    path('schedule/queue/<slug:code>/get/', views.ScheduleAPI.get, name='schedule-get'),
    path('schedule/queue/detail/<int:pk>/', views.ScheduleAPI.get_by_id),
    path('schedule/queue/status/', views.ScheduleAPI.status, name='schedule-status'),
    path('schedule/time-parse/', views.ScheduleTimeParseView.as_view()),
    path('exception/', views.ExceptionReportView.as_view(), name='exception-report'),
    path('client/logs/<int:client_id>/', views.TaskClientView.show_logs, name='task-client-log'),
    path('client/stop/<int:client_id>/', views.TaskClientView.stop_process, name='task-client-stop'),
] + router.urls
