# Generated by Django 4.1.7 on 2023-07-28 16:18

import datetime
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import django_common_objects.fields
import django_common_task_system.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('django_common_objects', '0003_alter_commoncategory_unique_together_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TaskClient',
            fields=[
                ('group', models.CharField(max_length=100, verbose_name='分组')),
                ('subscription_url', models.CharField(max_length=200, verbose_name='订阅地址')),
                ('subscription_kwargs', models.JSONField(default=dict, verbose_name='订阅参数')),
                ('client_id', models.IntegerField(default=0, primary_key=True, serialize=False, verbose_name='客户端ID')),
                ('process_id', models.PositiveIntegerField(blank=True, null=True, verbose_name='进程ID')),
                ('container_id', models.CharField(blank=True, max_length=100, null=True, verbose_name='容器ID')),
                ('container_name', models.CharField(blank=True, max_length=100, null=True, verbose_name='容器名称')),
                ('container_image', models.CharField(blank=True, max_length=100, null=True, verbose_name='容器镜像')),
                ('container_status', models.CharField(choices=[('None', 'None'), ('Created', 'Created'), ('Paused', 'Paused'), ('Running', 'Running'), ('Restarting', 'Restarting'), ('OOMKilled', 'Oomkilled'), ('Dead', 'Dead'), ('Exited', 'Exited')], default='None', max_length=20, verbose_name='容器状态')),
                ('run_in_container', models.BooleanField(default=True, verbose_name='是否在容器中运行')),
                ('env', models.CharField(blank=True, max_length=500, null=True, verbose_name='环境变量')),
                ('startup_status', models.CharField(choices=[('Init', '初始化'), ('Pulling', '拉取镜像中'), ('Building', '构建中'), ('Running', '启动成功'), ('Failed', '启动失败')], default='Running', max_length=500, verbose_name='启动结果')),
                ('settings', models.TextField(blank=True, null=True, verbose_name='配置')),
                ('create_time', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('startup_log', models.CharField(blank=True, max_length=2000, null=True)),
            ],
            options={
                'verbose_name': '客户端',
                'verbose_name_plural': '客户端',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='Schedule',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('priority', models.IntegerField(default=0, verbose_name='优先级')),
                ('next_schedule_time', models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='下次运行时间')),
                ('schedule_start_time', models.DateTimeField(default=datetime.datetime(1, 1, 1, 0, 0), verbose_name='开始时间')),
                ('schedule_end_time', models.DateTimeField(default=datetime.datetime(9999, 12, 31, 23, 59, 59, 999999), verbose_name='结束时间')),
                ('config', django_common_objects.fields.ConfigField(default=dict, encoder=django_common_objects.fields.DatetimeJsonEncoder, verbose_name='参数')),
                ('status', django_common_objects.fields.CharField(choices=[('O', '开启'), ('C', '关闭'), ('D', '已完成'), ('T', '测试'), ('E', '调度错误')], default='O', max_length=1, verbose_name='状态')),
                ('is_strict', models.BooleanField(default=False, verbose_name='严格模式')),
                ('create_time', models.DateTimeField(default=django.utils.timezone.now, verbose_name='创建时间')),
                ('update_time', models.DateTimeField(verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '计划中心',
                'verbose_name_plural': '计划中心',
                'db_table': 'common_schedule',
                'ordering': ('-priority', 'next_schedule_time'),
                'swappable': 'SCHEDULE_MODEL',
            },
        ),
        migrations.CreateModel(
            name='ExceptionReport',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, verbose_name='ID')),
                ('group', models.CharField(max_length=100, verbose_name='分组')),
                ('ip', models.CharField(max_length=100, verbose_name='IP')),
                ('content', models.TextField(verbose_name='内容')),
                ('create_time', models.DateTimeField(default=django.utils.timezone.now, verbose_name='创建时间')),
            ],
            options={
                'verbose_name': '异常报告',
                'verbose_name_plural': '异常报告',
                'db_table': 'exception_report',
                'ordering': ('-create_time',),
            },
        ),
        migrations.CreateModel(
            name='ScheduleQueue',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True, verbose_name='队列名称')),
                ('code', models.CharField(max_length=100, unique=True, validators=[django_common_task_system.models.code_validator], verbose_name='队列编码')),
                ('status', models.BooleanField(default=True, verbose_name='状态')),
                ('module', models.CharField(choices=[('queue.Queue', '先进先出'), ('queue.LifoQueue', '后进先出队列'), ('queue.PriorityQueue', '优先级队列'), ('_queue.SimpleQueue', '简单队列'), ('django_common_task_system.queue.RedisListQueue', 'Redis List队列')], default='queue.Queue', max_length=100, verbose_name='队列类型')),
                ('config', models.JSONField(blank=True, default=dict, null=True, verbose_name='配置')),
                ('create_time', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('update_time', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('user', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='最后更新')),
            ],
            options={
                'verbose_name': '计划队列',
                'verbose_name_plural': '计划队列',
                'db_table': 'schedule_queue',
            },
        ),
        migrations.CreateModel(
            name='MissingSchedule',
            fields=[
                ('schedule_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to=settings.SCHEDULE_MODEL)),
            ],
            options={
                'verbose_name': '缺失调度',
                'verbose_name_plural': '缺失调度',
                'managed': False,
            },
            bases=('django_common_task_system.schedule',),
        ),
        migrations.CreateModel(
            name='ScheduleProducer',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='生产名称')),
                ('filters', models.JSONField(verbose_name='过滤器')),
                ('lte_now', models.BooleanField(default=True, verbose_name='小于等于当前时间')),
                ('status', models.BooleanField(default=True, verbose_name='启用状态')),
                ('create_time', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('update_time', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('queue', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.CASCADE, related_name='producers', to='django_common_task_system.schedulequeue', verbose_name='队列')),
                ('user', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='最后更新')),
            ],
            options={
                'verbose_name': '计划生产',
                'verbose_name_plural': '计划生产',
                'db_table': 'schedule_producer',
            },
        ),
        migrations.CreateModel(
            name='ScheduleCallback',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100, verbose_name='回调')),
                ('description', models.TextField(blank=True, null=True, verbose_name='描述')),
                ('trigger_event', django_common_objects.fields.CharField(choices=[('S', '成功'), ('F', '失败'), ('D', '完成')], default='D', max_length=1, verbose_name='触发事件')),
                ('status', django_common_objects.fields.CharField(choices=[('E', '启用'), ('D', '禁用')], default='E', max_length=1, verbose_name='状态')),
                ('config', django_common_objects.fields.ConfigField(blank=True, encoder=django_common_objects.fields.DatetimeJsonEncoder, null=True, verbose_name='参数')),
                ('create_time', models.DateTimeField(default=django.utils.timezone.now, verbose_name='创建时间')),
                ('update_time', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('user', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='最后更新')),
            ],
            options={
                'verbose_name': '计划回调',
                'verbose_name_plural': '计划回调',
                'db_table': 'schedule_callback',
            },
        ),
        migrations.CreateModel(
            name='Task',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100, verbose_name='任务名')),
                ('description', models.TextField(blank=True, null=True, verbose_name='描述')),
                ('config', django_common_objects.fields.ConfigField(blank=True, default=dict, encoder=django_common_objects.fields.DatetimeJsonEncoder, null=True, verbose_name='参数')),
                ('status', django_common_objects.fields.CharField(choices=[('E', '启用'), ('D', '禁用')], default='E', max_length=1, verbose_name='状态')),
                ('create_time', models.DateTimeField(default=django.utils.timezone.now, verbose_name='创建时间')),
                ('update_time', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('category', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.DO_NOTHING, to='django_common_objects.commoncategory', verbose_name='类别')),
                ('parent', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.TASK_MODEL, verbose_name='父任务')),
                ('tags', models.ManyToManyField(blank=True, db_constraint=False, to='django_common_objects.commontag', verbose_name='标签')),
                ('user', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='最后更新')),
            ],
            options={
                'verbose_name': '任务中心',
                'verbose_name_plural': '任务中心',
                'db_table': 'common_task',
                'swappable': 'TASK_MODEL',
                'unique_together': {('name', 'parent')},
            },
        ),
        migrations.CreateModel(
            name='ScheduleLog',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('status', django_common_objects.fields.CharField(max_length=1, verbose_name='运行状态')),
                ('queue', models.CharField(default='opening', max_length=100, verbose_name='队列')),
                ('result', django_common_objects.fields.ConfigField(blank=True, encoder=django_common_objects.fields.DatetimeJsonEncoder, null=True, verbose_name='结果')),
                ('schedule_time', models.DateTimeField(verbose_name='计划时间')),
                ('create_time', models.DateTimeField(default=django.utils.timezone.now, verbose_name='创建时间')),
                ('schedule', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.CASCADE, related_name='logs', to=settings.SCHEDULE_MODEL, verbose_name='任务计划')),
            ],
            options={
                'verbose_name': '计划日志',
                'verbose_name_plural': '计划日志',
                'db_table': 'schedule_log',
                'ordering': ('-create_time',),
                'swappable': 'SCHEDULE_LOG_MODEL',
            },
        ),
        migrations.AddField(
            model_name='schedule',
            name='callback',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.SET_NULL, to='django_common_task_system.schedulecallback', verbose_name='回调'),
        ),
        migrations.AddField(
            model_name='schedule',
            name='task',
            field=models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.CASCADE, to=settings.TASK_MODEL, verbose_name='任务'),
        ),
        migrations.AddField(
            model_name='schedule',
            name='user',
            field=models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='最后更新'),
        ),
        migrations.CreateModel(
            name='ScheduleQueuePermission',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(choices=[('I', 'IP白名单')], default='I', max_length=1, verbose_name='类型')),
                ('status', models.BooleanField(default=True, verbose_name='启用状态')),
                ('config', models.JSONField(blank=True, default=dict, null=True, verbose_name='配置')),
                ('create_time', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('update_time', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('queue', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.CASCADE, to='django_common_task_system.schedulequeue', verbose_name='队列')),
                ('user', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='最后更新')),
            ],
            options={
                'verbose_name': '队列权限',
                'verbose_name_plural': '队列权限',
                'db_table': 'schedule_queue_permission',
                'unique_together': {('queue', 'status')},
            },
        ),
        migrations.AlterUniqueTogether(
            name='schedule',
            unique_together={('task', 'status')},
        ),
    ]
