from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.request import HttpRequest
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from . import models, serializers, get_task_model, get_schedule_log_model
from .models import TaskSchedule
from .choices import TaskScheduleStatus
from django_common_objects.rest_view import UserListAPIView, UserRetrieveAPIView
from queue import Queue, Empty
from datetime import datetime
from jionlp_time import parse_time
from .utils.schedule_time import nlp_config_to_schedule_config

schedule_queue = Queue()

TaskModel = get_task_model()
ScheduleLogModel = get_schedule_log_model()


class TaskListView(UserListAPIView):
    queryset = TaskModel.objects.all()
    serializer_class = serializers.TaskSerializer


class TaskDetailView(UserRetrieveAPIView):
    queryset = TaskModel.objects.all()
    serializer_class = serializers.TaskSerializer


class TaskScheduleListView(UserListAPIView):
    queryset = TaskSchedule.objects.all()
    serializer_class = serializers.TaskScheduleSerializer


class TaskScheduleDetailView(UserRetrieveAPIView):
    queryset = TaskSchedule.objects.all()
    serializer_class = serializers.TaskScheduleSerializer


class ScheduleLogViewSet(ModelViewSet):
    queryset = ScheduleLogModel.objects.all()
    serializer_class = serializers.TaskScheduleLogSerializer


class TaskScheduleQueueAPI:

    @staticmethod
    def query_expiring_schedules():
        now = datetime.now()
        queryset = TaskSchedule.objects.filter(next_schedule_time__lte=now, status=TaskScheduleStatus.OPENING.value)
        for schedule in queryset:
            schedule_queue.put(serializers.QueueScheduleSerializer(schedule).data)
            schedule.generate_next_schedule()
        return queryset

    @staticmethod
    @api_view(['GET'])
    def get(request: HttpRequest):
        try:
            schedule = schedule_queue.get(block=False)
        except Empty:
            TaskScheduleQueueAPI.query_expiring_schedules()
            try:
                schedule = schedule_queue.get(block=False)
            except Empty:
                return Response({'msg': 'no schedule to run'}, status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(schedule)

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


class ScheduleTimeParseView(APIView):

    def get(self, request, *args, **kwargs):
        sentence = request.query_params.get('sentence')
        if not sentence:
            return Response({'error': 'sentence is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = parse_time(sentence)
            schedule = nlp_config_to_schedule_config(result, sentence=sentence)
            return Response({
                "jio_result": result,
                "schedule": schedule
            })
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
