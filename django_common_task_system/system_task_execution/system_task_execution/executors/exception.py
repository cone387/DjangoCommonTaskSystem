from django.urls import reverse
import requests
from django_common_task_system.system_task_execution.system_task_execution.executor import (
    Executor, BaseExecutor, EmptyResult, Failed, NoRetryException, PartialFailed)
from django_common_task_system.builtins import builtins
from django_common_task_system.schedule import util as schedule_util
from django_common_task_system import get_schedule_model, get_schedule_serializer
from django_common_task_system.models import AbstractSchedule
from urllib.parse import urljoin
from django.core.paginator import Paginator
import os


Schedule: AbstractSchedule = get_schedule_model()
ScheduleSerializer = get_schedule_serializer()


@Executor.register
class ExceptionHandler(BaseExecutor):
    name = builtins.schedules.exception_handle.task.name
    last_executed_time = None

    def execute(self):
        response = requests.get(urljoin(os.environ['DJANGO_SERVER_ADDRESS'], reverse('schedule-status')))
        queue_status = response.json()
        max_retry_times = self.schedule.task.config.get('max-retry-times', 5)
        queues = self.schedule.task.config.get('queues', ['opening'])
        if not queues:
            raise Failed('queues is empty, please set queues in config or close this schedule')
        result = {}
        errors = []
        succeed = False
        total = 0
        for queue in queues:
            num = queue_status.get(queue, -1)
            if num < 0:
                raise Failed('queue %s not found' % queue)
            if num > 0:
                result[queue] = "queue %s is not free, %s tasks in queue" % (queue, num)
                errors.append(NoRetryException(result[queue]))
            else:
                records = schedule_util.get_retryable_records(queue, start_time=self.last_executed_time,
                                                              max_retry_times=max_retry_times)
                paginator = Paginator(records, 3000)
                for page in paginator.page_range:
                    page_records = paginator.page(page).object_list
                    if not page_records:
                        break
                    mapping = {}
                    for x in records:
                        mapping.setdefault(x['schedule_id'], []).append(x)
                    schedules = Schedule.objects.filter(id__in=mapping.keys())
                    data = []
                    for x in schedules:
                        for e in mapping.get(x.pk, []):
                            x.next_schedule_time = e['schedule_time']
                            x.generator = 'retry'
                            x.queue = queue
                            data.append(ScheduleSerializer(x).data)
                    url = urljoin(os.environ['DJANGO_SERVER_ADDRESS'], reverse('schedule-put-raw'))
                    put_result = requests.post(url, json={
                        'schedules': data,
                        'queue': queue
                    }).json()
                    if 'error' in put_result:
                        errors.append(NoRetryException(put_result['error']))
                    result[queue] = put_result
                    total += len(data)
                succeed = True

        if errors and not succeed:
            raise Failed(result)
        if errors and succeed:
            raise PartialFailed(result)
        # no errors, succeed is True
        if total == 0:
            raise EmptyResult('no strict schedule missing')
        return result
