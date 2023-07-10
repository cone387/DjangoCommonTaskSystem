import logging
from logging.handlers import RotatingFileHandler
from multiprocessing import set_start_method, Process
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from rest_framework import status
from rest_framework.generics import CreateAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from django.http.response import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from queue import Empty
from datetime import datetime
from django_common_objects.models import CommonCategory
from django.contrib.auth import get_user_model
from django_common_task_system.utils.foreign_key import get_model_related
from .builtins import BaseBuiltinQueues
from .models import TaskClient
import os
import sys
import subprocess


SYS_ENCODING = sys.getdefaultencoding()
UserModel = get_user_model()


def run_in_subprocess(cmd):
    logs = []
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    if out:
        logs.append(out.decode(SYS_ENCODING))
    if err:
        logs.append(err.decode(SYS_ENCODING))
    return not err, logs


@receiver(post_delete, sender=TaskClient)
def delete_process(sender, instance: TaskClient, **kwargs):
    ProcessManager.kill(instance.process_id)
    if os.path.isfile(instance.log_file) and not instance.log_file.endswith('system-process-default.log'):
        os.remove(instance.log_file)


@receiver(post_save, sender=TaskClient)
def add_process(sender, instance: TaskClient, created, **kwargs):
    if instance.run_in_docker:
        # pull image
        image = instance.docker_image
        if not image:
            raise ValueError('docker image is required')
        err, logs = run_in_subprocess(f'docker pull {image}')
        if err:
            raise RuntimeError('pull docker image failed: %s' % image)
        # run container
        name = 'system-process-default'
        log_file = os.path.join(os.getcwd(), 'logs', f'{name}.log')
        cmd = f'docker run -d --name {name} -v {log_file}:/logs/{name}.log {image}'
        err, logs = run_in_subprocess(cmd)
        if err:
            raise RuntimeError('run docker container failed: %s' % image)
        # get container id
        cmd = f'docker ps -a | grep {name} | awk \'{{print $1}}\''
        err, logs = run_in_subprocess(cmd)
        if err:
            raise RuntimeError('get docker container id failed: %s' % image)
    else:
        set_start_method('spawn', True)
        os.environ['TASK_CLIENT_SETTINGS_MODULE'] = instance.settings_file.replace(
            os.getcwd(), '').replace(os.sep, '.').strip('.py')
        try:
            from task_system_client.main import start_task_system
        except ImportError:
            os.system('pip install common-task-system-client')
            try:
                from task_system_client.main import start_task_system
            except ImportError:
                raise ImportError('common-task-system-client install failed')
        from task_system_client.settings import logger
        logger.handlers.clear()
        if os.path.isfile(instance.log_file):
            os.remove(instance.log_file)
        handler = RotatingFileHandler(instance.log_file, maxBytes=1024 * 1024 * 10, encoding='utf-8', backupCount=5)
        formatter = logging.Formatter('[%(asctime)s][%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        p = Process(target=start_task_system, daemon=True)
        p.start()
        instance.process_id = p.pid
        instance.status = p.is_alive()


class TaskScheduleQueueAPI(object):

    def __init__(self, schedule_mode, log_model, queues: BaseBuiltinQueues,
                 serializer, consumer_permissions, permission_validator=None):
        self.schedule_model = schedule_mode
        self.log_model = log_model
        self.queues = queues
        self.serializer = serializer
        self.consumer_permissions = consumer_permissions
        self.permission_validator = permission_validator

    def get(self, request: Request, code: str):
        instance = self.queues.get(code, None)
        if instance is None:
            return JsonResponse({'error': '队列(%s)不存在' % code}, status=status.HTTP_404_NOT_FOUND)
        permission_validator = self.permission_validator or self.consumer_permissions.get(code, None)
        if permission_validator is not None:
            error = permission_validator.validate(request)
            if error:
                return JsonResponse({'error': error}, status=status.HTTP_403_FORBIDDEN)
        try:
            task = instance.queue.get_nowait()
        except Empty:
            return JsonResponse({'message': 'no schedule for %s' % code}, status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            return JsonResponse({'error': 'get schedule error: %s' % e}, status=status.HTTP_400_BAD_REQUEST)
        return JsonResponse(task)

    def get_by_id(self, request, pk):
        try:
            schedule = self.schedule_model.objects.get(id=pk)
            return Response(self.serializer(schedule).data)
        except self.schedule_model.DoesNotExist:
            return Response({'error': 'schedule not found'}, status=status.HTTP_404_NOT_FOUND)

    @csrf_exempt
    def retry(self, request):
        log_ids = request.GET.get('log-ids', None) or request.POST.get('log-ids', None)
        if not log_ids:
            return JsonResponse({'error': 'log-ids不能为空'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            log_ids = [int(i) for i in log_ids.split(',')]
            if len(log_ids) > 1000:
                raise Exception('log-ids不能超过1000个')
        except Exception as e:
            return JsonResponse({'error': 'logs_ids参数错误: %s' % e}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = {x: 'no such log' for x in log_ids}
            related = get_model_related(self.log_model, excludes=[UserModel, CommonCategory])
            logs = self.log_model.objects.filter(id__in=log_ids).select_related(*related)
            for log in logs:
                schedule = log.schedule
                queue = self.queues[log.queue].queue
                schedule.next_schedule_time = log.schedule_time
                schedule.generator = 'retry'
                schedule.last_log = log.result
                schedule.queue = log.queue
                data = self.serializer(schedule).data
                queue.put(data)
                result[log.id] = log.queue
            return JsonResponse(result)
        except Exception as e:
            return JsonResponse({'error': '重试失败: %s' % e}, status=status.HTTP_400_BAD_REQUEST)

    @csrf_exempt
    def put(self, request: Request):
        schedule_ids = request.GET.get('i', None) or request.POST.get('i', None)
        queues = request.GET.get('q', None) or request.POST.get('q', None)
        schedule_times = request.GET.get('t', None) or request.POST.get('t', None)
        if not schedule_ids or not queues or not schedule_times:
            return JsonResponse({'error': 'schedule_ids(i)、queues(q)、schedule_times(t)不能为空'},
                                status=status.HTTP_400_BAD_REQUEST)
        try:
            schedule_ids = [int(i) for i in schedule_ids.split(',')]
            queues = [i.strip() for i in queues.split(',')]
            schedule_times = [datetime.strptime(i, '%Y-%m-%d %H:%M:%S') for i in schedule_times.split(',')]
            assert len(schedule_ids) <= 1000, '不能超过1000个'
            if len(queues) == 1:
                q = queues[0]
                queues = [q for _ in schedule_ids]
            elif len(queues) != len(schedule_ids):
                raise Exception('ids和queues长度不一致')
            if len(schedule_times) == 1:
                t = schedule_times[0]
                schedule_times = [t for _ in schedule_ids]
            elif len(schedule_times) != len(schedule_ids):
                raise Exception('ids和schedule_times长度不一致')
        except Exception as e:
            return JsonResponse({'error': 'ids参数错误: %s' % e}, status=status.HTTP_400_BAD_REQUEST)
        try:
            schedules = self.schedule_model.objects.filter(id__in=set(schedule_ids))
            schedule_mapping = {x.id: x for x in schedules}
            result = {}
            for i, q, t in zip(schedule_ids, queues, schedule_times):
                queue_instance = self.queues.get(q, None)
                if queue_instance is None:
                    result[q] = 'no such queue: %s' % q
                    continue
                queue_result = result.setdefault(q, {})
                schedule = schedule_mapping.get(i, None)
                if schedule is None:
                    queue_result[i] = 'no such schedule: %s' % i
                    continue
                schedule_result = queue_result.setdefault(i, [])
                schedule.next_schedule_time = t
                schedule.generator = 'put'
                schedule.queue = q
                data = self.serializer(schedule).data
                queue_instance.queue.put(data)
                schedule_result.append(t.strftime('%Y-%m-%d %H:%M:%S'))
            return JsonResponse(result)
        except Exception as e:
            return JsonResponse({'error': '添加到队列失败: %s' % e}, status=status.HTTP_400_BAD_REQUEST)

    def status(self, request):
        return JsonResponse({x: y.queue.qsize() for x, y in self.queues.items()})


class ExceptionReportView(CreateAPIView):

    def perform_create(self, serializer):
        meta = self.request.META
        ip = meta.get('HTTP_X_FORWARDED_FOR') if meta.get('HTTP_X_FORWARDED_FOR') else meta.get('REMOTE_ADDR')
        serializer.save(ip=ip)


class SystemProcessView:

    @staticmethod
    def show_logs(request: Request, process_id: int):
        # 此处pk为进程id
        try:
            process = TaskClient.objects.get(process_id=process_id)
        except TaskClient.DoesNotExist:
            return HttpResponse('SystemProcess(%s)不存在' % process_id)
        if not os.path.isfile(process.log_file):
            return HttpResponse('log文件不存在')
        offset = int(request.GET.get('offset', 0))
        with open(process.log_file, 'r', encoding='utf-8') as f:
            f.seek(offset)
            logs = f.read(offset + 1024 * 1024 * 8)
        return HttpResponse(logs, content_type='text/plain; charset=utf-8')

    @staticmethod
    def stop_process(request: Request, process_id: int):
        try:
            process = TaskClient.objects.get(process_id=process_id)
        except TaskClient.DoesNotExist:
            return HttpResponse('SystemProcess(%s)不存在' % process_id)
        process.delete()
        return HttpResponse('SystemProcess(%s)已停止' % process_id)
