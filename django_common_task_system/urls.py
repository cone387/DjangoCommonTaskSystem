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
    path('schedule/queue/get/<slug:code>/', views.ScheduleAPI.get, name='schedule-get'),
    path('schedule/queue/status/', views.ScheduleAPI.status, name='schedule-status'),
    path('schedule/time-parse/', views.ScheduleTimeParseView.as_view()),
    path('exception/', views.ExceptionReportView.as_view(), name='exception-report'),

    path('system/producer/<slug:action>/', views.ProducerView.as_view(), name='producer-action'),
    path('system/consumer/<slug:action>/', views.ConsumerView.as_view(), name='consumer-action'),
    path('client/<slug:action>/', views.ClientView.as_view(), name='client-action'),

] + router.urls
