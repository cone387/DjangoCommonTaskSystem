# Generated by Django 4.1.7 on 2023-04-07 16:41

import datetime
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import django_common_objects.fields
import django_common_objects.models
import django_common_task_system.fields
import django_common_task_system.system_task.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('django_common_objects', '0002_alter_commoncategory_model_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SystemProcess',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, verbose_name='ID')),
                ('process_id', models.PositiveIntegerField(unique=True, verbose_name='进程ID')),
                ('process_name', models.CharField(max_length=100, verbose_name='进程名称')),
                ('env', models.CharField(blank=True, max_length=500, null=True, verbose_name='环境变量')),
                ('status', models.BooleanField(default=True, verbose_name='状态')),
                ('log_file', models.CharField(max_length=200, verbose_name='日志文件')),
                ('create_time', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('update_time', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '系统进程',
                'verbose_name_plural': '系统进程',
                'db_table': 'system_process',
            },
        ),
        migrations.CreateModel(
            name='SystemSchedule',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('priority', models.IntegerField(default=0, verbose_name='优先级')),
                ('next_schedule_time', models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='下次运行时间')),
                ('schedule_start_time', models.DateTimeField(default=datetime.datetime(1, 1, 1, 0, 0), verbose_name='开始时间')),
                ('schedule_end_time', models.DateTimeField(default=datetime.datetime(9999, 12, 31, 23, 59, 59, 999999), verbose_name='结束时间')),
                ('config', django_common_task_system.fields.ScheduleConfigField(default=dict, verbose_name='参数')),
                ('status', django_common_objects.fields.CharField(choices=[('O', '开启'), ('C', '关闭'), ('D', '已完成'), ('T', '测试'), ('E', '调度错误')], default='O', max_length=1, verbose_name='状态')),
                ('create_time', models.DateTimeField(default=django.utils.timezone.now, verbose_name='创建时间')),
                ('update_time', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '系统计划',
                'verbose_name_plural': '系统计划',
                'db_table': 'system_schedule',
                'ordering': ('-update_time',),
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='SystemScheduleQueue',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True, verbose_name='队列名称')),
                ('code', models.CharField(max_length=100, unique=True, validators=[django_common_task_system.models.code_validator], verbose_name='队列编码')),
                ('status', models.BooleanField(default=True, verbose_name='状态')),
                ('module', models.CharField(choices=[('queue.Queue', '普通队列'), ('queue.LifoQueue', '后进先出队列'), ('queue.PriorityQueue', '优先级队列'), ('_queue.SimpleQueue', '简单队列')], default='queue.Queue', max_length=100, verbose_name='队列类型')),
                ('create_time', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('update_time', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '系统队列',
                'verbose_name_plural': '系统队列',
                'db_table': 'system_schedule_queue',
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='SystemTask',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100, verbose_name='任务名')),
                ('description', models.TextField(blank=True, null=True, verbose_name='描述')),
                ('config', django_common_objects.fields.ConfigField(blank=True, null=True, verbose_name='参数')),
                ('status', django_common_objects.fields.CharField(choices=[('E', '启用'), ('D', '禁用')], default='E', max_length=1, verbose_name='状态')),
                ('create_time', models.DateTimeField(default=django.utils.timezone.now, verbose_name='创建时间')),
                ('update_time', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('task_type', models.CharField(choices=[('SQL_TASK_EXECUTION', 'SQL任务执行'), ('SQL_TASK_PRODUCE', 'SQL任务生产'), ('SHELL_EXECUTION', 'SHELL任务执行'), ('CUSTOM', '自定义任务')], default='SQL_TASK_PRODUCE', max_length=32, verbose_name='任务类型')),
                ('category', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.DO_NOTHING, to='django_common_objects.commoncategory', verbose_name='类别')),
                ('parent', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='system_task.systemtask', verbose_name='父任务')),
                ('user', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='用户')),
            ],
            options={
                'verbose_name': '系统任务',
                'verbose_name_plural': '系统任务',
                'db_table': 'system_task',
                'abstract': False,
                'unique_together': {('name', 'user', 'parent')},
            },
        ),
        migrations.CreateModel(
            name='SystemScheduleLog',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('status', django_common_objects.fields.CharField(max_length=1, verbose_name='运行状态')),
                ('result', django_common_objects.fields.ConfigField(blank=True, null=True, verbose_name='结果')),
                ('schedule_time', models.DateTimeField(verbose_name='计划时间')),
                ('create_time', models.DateTimeField(default=django.utils.timezone.now, verbose_name='创建时间')),
                ('schedule', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.CASCADE, related_name='logs', to='system_task.systemschedule', verbose_name='任务计划')),
            ],
            options={
                'verbose_name': '系统日志',
                'verbose_name_plural': '系统日志',
                'db_table': 'system_schedule_log',
                'ordering': ('-schedule_time',),
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='SystemScheduleCallback',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100, verbose_name='回调')),
                ('description', models.TextField(blank=True, null=True, verbose_name='描述')),
                ('trigger_event', django_common_objects.fields.CharField(choices=[('S', '成功'), ('F', '失败'), ('D', '完成')], default='D', max_length=1, verbose_name='触发事件')),
                ('status', django_common_objects.fields.CharField(choices=[('E', '启用'), ('D', '禁用')], default='E', max_length=1, verbose_name='状态')),
                ('config', django_common_objects.fields.ConfigField(blank=True, null=True, verbose_name='参数')),
                ('create_time', models.DateTimeField(default=django.utils.timezone.now, verbose_name='创建时间')),
                ('update_time', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('queue', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.CASCADE, related_name='callbacks', to='system_task.systemschedulequeue', verbose_name='队列')),
                ('user', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='用户')),
            ],
            options={
                'verbose_name': '系统回调',
                'verbose_name_plural': '系统回调',
                'db_table': 'system_schedule_callback',
                'abstract': False,
                'unique_together': {('name', 'user')},
            },
        ),
        migrations.AddField(
            model_name='systemschedule',
            name='callback',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.CASCADE, to='system_task.systemschedulecallback', verbose_name='回调'),
        ),
        migrations.AddField(
            model_name='systemschedule',
            name='task',
            field=models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.CASCADE, related_name='schedules', to='system_task.systemtask', verbose_name='任务'),
        ),
        migrations.AddField(
            model_name='systemschedule',
            name='user',
            field=models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='用户'),
        ),
        migrations.AlterUniqueTogether(
            name='systemschedule',
            unique_together={('task', 'status', 'user')},
        ),
    ]
