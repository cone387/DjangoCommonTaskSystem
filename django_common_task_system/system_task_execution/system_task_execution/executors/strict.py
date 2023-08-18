from urllib.parse import urljoin
from django.urls import reverse
from django_common_task_system.system_task_execution.system_task_execution.executor import (
    Executor, BaseExecutor, Failed, EmptyResult, NoRetryException, PartialFailed)
from django_common_task_system.builtins import builtins
from django_common_task_system.schedule import util as schedule_util
from django_common_task_system import get_schedule_model, get_schedule_serializer
from django_common_task_system.choices import ScheduleStatus
from django.core.paginator import Paginator
from typing import Dict, Union
import logging
import requests
import os


logger = logging.getLogger(__name__)
Schedule = get_schedule_model()
ScheduleSerializer = get_schedule_serializer()


@Executor.register
class StrictScheduleHandler(BaseExecutor):
    name = builtins.tasks.strict_schedule_handle.name
    last_executed_time = None

    def execute(self):
        response = requests.get(urljoin(os.environ['DJANGO_SERVER_ADDRESS'], reverse('schedule-status')))
        queue_status = response.json()
        queues = self.schedule.task.config.get('queues', ['opening'])
        if not queues:
            raise Failed('queues is empty, please set queues in config or close this schedule')
        schedules = Schedule.objects.filter(is_strict=True, status=ScheduleStatus.OPENING)
        result: Dict[str, Union[Dict, str]] = {}
        total = 0
        errors = []
        succeed = False
        for queue in queues:
            queue_num = queue_status.get(queue, -1)
            if queue_num < 0:
                raise Failed('queue %s not found' % queue)
            elif queue_num > 0:
                result[queue] = 'queue %s is not free, %s tasks in queue' % (queue, queue_num)
                errors.append(NoRetryException(result[queue]))
            else:
                paginator = Paginator(schedules, 3000)
                for page in paginator.page_range:
                    page_schedules = paginator.page(page).object_list
                    queue_result = result[queue] = {}
                    missing_mapping = schedule_util.get_missing_schedules_mapping(queue, page_schedules,
                                                                                  start_time=self.last_executed_time)
                    for schedule_id, missing in missing_mapping.items():
                        if missing:
                            response = requests.post(
                                urljoin(os.environ['DJANGO_SERVER_ADDRESS'], reverse('schedule-put-raw')),
                                json={
                                    'schedules': ScheduleSerializer(missing, many=True).data,
                                    'queue': queue
                                }).json()
                            if 'error' in response:
                                queue_result[schedule_id] = response['error']
                            else:
                                queue_result[schedule_id] = 'put %s tasks' % len(missing)
                        total += len(missing)
                succeed = True
        if errors and not succeed:
            raise Failed(result)
        if errors and succeed:
            raise PartialFailed(result)
        # no errors, succeed is True
        if total == 0:
            raise EmptyResult('no strict schedule missing')
        return result
