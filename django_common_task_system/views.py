from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.request import HttpRequest
from rest_framework.response import Response
from . import models, serializers
from .models import TaskSchedule
from .choices import TaskScheduleStatus
from django_common_objects.rest_view import UserListAPIView, UserRetrieveAPIView
from queue import PriorityQueue, Empty
from datetime import datetime

schedule_queue = PriorityQueue()


class TaskListView(UserListAPIView):
    queryset = models.Task.objects.all()
    serializer_class = serializers.TaskSerializer


class TaskDetailView(UserRetrieveAPIView):
    queryset = models.Task.objects.all()
    serializer_class = serializers.TaskSerializer


class TaskScheduleListView(UserListAPIView):
    queryset = TaskSchedule.objects.all()
    serializer_class = serializers.TaskScheduleSerializer


class TaskScheduleDetailView(UserRetrieveAPIView):
    queryset = TaskSchedule.objects.all()
    serializer_class = serializers.TaskScheduleSerializer


class TaskScheduleQueueAPI:

    @staticmethod
    def query_expiring_schedules():
        now = datetime.now()
        queryset = TaskSchedule.objects.filter(next_schedule_time__lte=now, status=TaskScheduleStatus.OPENING.value)
        for schedule in queryset:
            schedule_queue.put(schedule)
            schedule.generate_next_schedule()
        return queryset

    @staticmethod
    @api_view(['GET'])
    def get(request: HttpRequest):
        schedule = None
        try:
            schedule = schedule_queue.get(block=False)
        except Empty:
            schedules = TaskScheduleQueueAPI.query_expiring_schedules()
            if schedules:
                schedule = schedules.first()
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        if schedule:
            return Response(serializers.QueueScheduleSerializer(schedule).data)
        return Response({'msg': 'no schedule to run'}, status=status.HTTP_204_NO_CONTENT)

    @staticmethod
    @api_view(['GET'])
    def get_by_id(request, pk):
        try:
            schedule = TaskSchedule.objects.get(id=pk)
            return Response(serializers.QueueScheduleSerializer(schedule).data)
        except TaskSchedule.DoesNotExist:
            return Response({'msg': 'schedule not found'}, status=status.HTTP_404_NOT_FOUND)

    @staticmethod
    @api_view(['GET'])
    def size(request):
        return Response({'size': schedule_queue.qsize()})
