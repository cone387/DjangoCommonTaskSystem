from django.urls import reverse
import requests
from django_common_task_system.system_task_execution.system_task_execution.executor import (
    Executor, BaseExecutor, EmptyResult, Failed, NoRetryException)
from django_common_task_system.builtins import builtins
from django_common_task_system.schedule import util as schedule_util
from urllib.parse import urljoin
import os


@Executor.register
class ExceptionExecutor(BaseExecutor):
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
        error = None
        for queue in queues:
            num = queue_status.get(queue, -1)
            if num < 0:
                raise Failed('queue %s not found' % queue)
            if num > 0:
                result[queue] = "queue %s is not free, %s tasks in queue" % (queue, num)
            else:
                records = schedule_util.get_retryable_records(queue, start_time=self.last_executed_time,
                                                              max_retry_times=max_retry_times)
                if not records:
                    error = EmptyResult('no retryable records in %s queue' % queue)
                    continue
                url = urljoin(os.environ['DJANGO_SERVER_ADDRESS'], reverse('schedule-put-raw'))
                put_result = requests.post(url, json={}).json()
                if 'error' in put_result:
                    raise NoRetryException(put_result['error'])
                result[queue] = put_result
        if error:
            raise error
        return result
