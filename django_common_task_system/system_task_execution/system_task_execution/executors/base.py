from django_common_task_system.system_task.models import SystemScheduleLog, SystemSchedule


class BaseExecutor(object):
    name = None

    def __init__(self, schedule):
        self.schedule: SystemSchedule = schedule

    def execute(self):
        raise NotImplementedError

    def start(self):
        log = SystemScheduleLog(schedule=self.schedule, result={},
                                status='S', queue=self.schedule.queue,
                                schedule_time=self.schedule.next_schedule_time)
        err = None
        try:
            log.result['result'] = self.execute()
        except Exception as e:
            log.result['error'] = str(e)
            log.status = 'F'    # F: failed
            err = err
        try:
            log.save()
        except Exception as e:
            err = e
        return log, err
