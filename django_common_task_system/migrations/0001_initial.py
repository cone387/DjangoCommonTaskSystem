# Generated by Django 4.1.7 on 2023-03-07 15:14

import django_common_objects.fields
import django_common_objects.models
import datetime
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import django_common_task_system.fields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('django_common_objects', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Task',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100, verbose_name='任务名')),
                ('description', models.TextField(blank=True, null=True, verbose_name='描述')),
                ('config', django_common_objects.fields.ConfigField(blank=True, default=django_common_objects.models.get_default_config('Task'), null=True, verbose_name='参数')),
                ('status', django_common_objects.fields.CharField(choices=[('E', '启用'), ('D', '禁用')], default='E', max_length=1, verbose_name='状态')),
                ('create_time', models.DateTimeField(default=django.utils.timezone.now, verbose_name='创建时间')),
                ('update_time', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('category', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.DO_NOTHING, to='django_common_objects.commoncategory', verbose_name='类别')),
                ('parent', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='django_common_task_system.task', verbose_name='父任务')),
                ('tags', models.ManyToManyField(blank=True, db_constraint=False, to='django_common_objects.commontag', verbose_name='标签')),
                ('user', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='用户')),
            ],
            options={
                'verbose_name': '任务中心',
                'verbose_name_plural': '任务中心',
                'db_table': 'taskhub',
                'unique_together': {('name', 'user', 'parent')},
            },
        ),
        migrations.CreateModel(
            name='TaskSchedule',
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
                'verbose_name': '任务计划',
                'verbose_name_plural': '任务计划',
                'db_table': 'django_common_task_system',
                'ordering': ('-priority', 'next_schedule_time'),
            },
        ),
        migrations.CreateModel(
            name='TaskScheduleLog',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('status', django_common_objects.fields.CharField(max_length=1, verbose_name='运行状态')),
                ('result', django_common_objects.fields.ConfigField(blank=True, null=True, verbose_name='结果')),
                ('schedule_time', models.DateTimeField(verbose_name='计划时间')),
                ('create_time', models.DateTimeField(default=django.utils.timezone.now, verbose_name='创建时间')),
                ('schedule', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.CASCADE, to='django_common_task_system.taskschedule', verbose_name='任务计划')),
            ],
            options={
                'verbose_name': '任务日志',
                'verbose_name_plural': '任务日志',
                'db_table': 'django_common_task_system_log',
            },
        ),
        migrations.CreateModel(
            name='TaskScheduleCallback',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100, verbose_name='回调')),
                ('description', models.TextField(blank=True, null=True, verbose_name='描述')),
                ('trigger_event', django_common_objects.fields.CharField(choices=[('S', '成功'), ('F', '失败'), ('D', '完成')], default='D', max_length=1, verbose_name='触发事件')),
                ('status', django_common_objects.fields.CharField(choices=[('E', '启用'), ('D', '禁用')], default='E', max_length=1, verbose_name='状态')),
                ('config', django_common_objects.fields.ConfigField(blank=True, default=django_common_objects.models.get_default_config('TaskCallback'), null=True, verbose_name='参数')),
                ('create_time', models.DateTimeField(default=django.utils.timezone.now, verbose_name='创建时间')),
                ('update_time', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('user', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='用户')),
            ],
            options={
                'verbose_name': '任务回调',
                'verbose_name_plural': '任务回调',
                'db_table': 'django_common_task_system_callback',
                'unique_together': {('name', 'user')},
            },
        ),
        migrations.AddField(
            model_name='taskschedule',
            name='callback',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.CASCADE, to='django_common_task_system.taskschedulecallback', verbose_name='回调'),
        ),
        migrations.AddField(
            model_name='taskschedule',
            name='task',
            field=models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.CASCADE, to='django_common_task_system.task', verbose_name='任务'),
        ),
        migrations.AddField(
            model_name='taskschedule',
            name='user',
            field=models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='用户'),
        ),
    ]
