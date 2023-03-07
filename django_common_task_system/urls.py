from django.urls import path
from . import views

urlpatterns = [
    path('task/', views.TaskListView.as_view()),
    path('task/<int:pk>/', views.TaskDetailView.as_view()),
    path('schedule/', views.TaskScheduleListView.as_view()),
    path('schedule/<int:pk>/', views.TaskScheduleDetailView.as_view()),
    path('schedule/queue/get/', views.TaskScheduleQueueAPI.get),
    path('schedule/queue/', views.TaskScheduleQueueAPI.size),
    path('schedule/queue/<int:pk>/', views.TaskScheduleQueueAPI.get_by_id),
    path('schedule/time-parse/', views.ScheduleTimeParseView.as_view()),
]
