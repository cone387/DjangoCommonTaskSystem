

def create_schedules():
    import os
    import django
    from datetime import datetime
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_task_system.settings')
    django.setup()
    from django_common_task_system.system_task import models
    from django_common_task_system.system_task.choices import SystemTaskType
    from django.contrib.auth.models import User

    from django_common_task_system.system_task.models import builtins

    # builtins.schedules;
    # return
    user, created = User.objects.get_or_create(username='test', is_superuser=True)
    if created:
        user.set_password('3.1415926')
        user.save()
    return user

    models.SystemTask.objects.filter(user=user).delete()
    models.SystemSchedule.objects.filter(task__user=user).delete()
    models.SystemScheduleLog.objects.filter(schedule__task__user=user).delete()

    queue = models.SystemScheduleQueue.objects.get_or_create(
        name='测试队列',
        code='test',
        status=True,
    )[0]

    log_task = models.SystemTask.objects.get_or_create(
        name='定期删除一个月前日志',
        task_type=SystemTaskType.SQL_TASK_EXECUTION.value,
        config={
                'sql': 'delete from %s where create_time < date_sub(now(), interval 1 month);' %
                   models.SystemScheduleLog._meta.db_table
            },
        user=user
    )[0]
    log_schedule = models.SystemSchedule.objects.get_or_create(
        task=log_task,
        next_schedule_time=datetime.now(),
        # 每天1点执行
        config={
          "T": {
            "DAY": {
              "period": 1
            },
            "time": "01:00:00",
            "type": "DAY"
          },
          "base_on_now": True,
          "schedule_type": "T"
        },
        user=user
    )[0]

    test_sql_execution_task = models.SystemTask.objects.get_or_create(
        name='测试SQL执行任务',
        task_type=SystemTaskType.SQL_TASK_EXECUTION.value,
        config={
            'sql': 'select * from %s limit 10;' % models.SystemScheduleLog._meta.db_table
        },
        user=user
    )[0]
    test_sql_execution_schedule = models.SystemSchedule.objects.get_or_create(
        task=test_sql_execution_task,
        next_schedule_time=datetime.now(),
        config={
            "S": {
                "period": 60,
                "schedule_start_time": "2023-04-04 13:31:00"
            },
            "base_on_now": True,
            "schedule_type": "S"
        },
        user=user
    )[0]

    test_sql_produce_task = models.SystemTask.objects.get_or_create(
        name='测试SQL生产任务',
        task_type=SystemTaskType.SQL_TASK_PRODUCE.value,
        config={
            'sql': 'select * from %s limit 10;' % models.SystemScheduleLog._meta.db_table,
            'queue': queue.code
        },
        user=user
    )[0]
    test_sql_produce_schedule = models.SystemSchedule.objects.get_or_create(
        task=test_sql_produce_task,
        config={
            "S": {
                "period": 60,
                "schedule_start_time": "2023-04-04 13:31:00"
            },
            "base_on_now": True,
            "schedule_type": "S"
        },
        user=user
    )

    test_shell_execution_task = models.SystemTask.objects.get_or_create(
        name='测试Shell执行任务',
        task_type=SystemTaskType.SHELL_EXECUTION.value,
        config={
            'shell': 'echo "hello world"'
        },
        user=user
    )[0]
    test_shell_execution_schedule = models.SystemSchedule.objects.get_or_create(
        task=test_shell_execution_task,
        next_schedule_time=datetime.now(),
        config={
            "S": {
                "period": 60,
                "schedule_start_time": "2023-04-04 13:31:00"
            },
            "base_on_now": True,
            "schedule_type": "S"
        },
        user=user
    )[0]


create_schedules()
