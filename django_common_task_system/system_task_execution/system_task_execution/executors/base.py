from django_common_task_system.system_task.models import SystemScheduleLog, SystemSchedule


class EmptyResult(Exception):
    pass


# 无需重试的异常, 发生此异常时, 任务将不会重试, 此任务状态为N
class NoRetryException(Exception):
    pass


class BaseExecutor(object):
    name = None

    def __init__(self, schedule):
        self.schedule: SystemSchedule = schedule

    def execute(self):
        raise NotImplementedError

    def start(self):
        log = SystemScheduleLog(schedule=self.schedule, result={'generator': self.schedule.generator},
                                status='S', queue=self.schedule.queue,
                                schedule_time=self.schedule.next_schedule_time)
        err = None
        try:
            log.result['result'] = self.execute()
        except EmptyResult as e:
            log.status = 'E'    # E: empty result
            log.result['msg'] = str(e)
        except NoRetryException as e:
            log.status = 'N'
            log.result['msg'] = str(e)
        except Exception as e:
            log.result['error'] = str(e)
            log.status = 'F'    # F: failed
            err = err
        try:
            log.save()
        except Exception as e:
            err = e
        return log, err
