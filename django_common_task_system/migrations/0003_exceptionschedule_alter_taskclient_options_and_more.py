# Generated by Django 4.1.7 on 2023-08-16 14:16

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django_common_objects.fields


class Migration(migrations.Migration):

    dependencies = [
        ('django_common_task_system', '0002_alter_missingschedule_options_schedule_preserve_log_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExceptionSchedule',
            fields=[
                ('id', models.IntegerField(primary_key=True, serialize=False, verbose_name='计划ID')),
                ('schedule_time', models.DateTimeField(verbose_name='计划时间')),
                ('queue', models.CharField(max_length=100, verbose_name='队列')),
                ('reason', models.CharField(choices=[('FAILED_DIRECTLY', '执行失败'), ('SCHEDULE_LOG_NOT_FOUND', '缺失成功的计划日志'), ('MAXIMUM_RETRIES_EXCEEDED', '超过最大重试次数')], default='FAILED_DIRECTLY', max_length=100, verbose_name='异常原因')),
            ],
            options={
                'verbose_name': '异常的计划',
                'verbose_name_plural': '异常的计划',
                'ordering': ('id', '-schedule_time'),
                'managed': False,
            },
        ),
        migrations.AlterModelOptions(
            name='taskclient',
            options={'managed': False, 'verbose_name': '客户端管理', 'verbose_name_plural': '客户端管理'},
        ),
        migrations.AlterUniqueTogether(
            name='schedule',
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name='exceptionreport',
            name='group',
        ),
        migrations.AddField(
            model_name='exceptionreport',
            name='client',
            field=models.CharField(default='test', max_length=100, verbose_name='客户端'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='schedule',
            name='task',
            field=models.OneToOneField(db_constraint=False, on_delete=django.db.models.deletion.CASCADE, to=settings.TASK_MODEL, verbose_name='任务'),
        ),
        migrations.AlterField(
            model_name='schedulelog',
            name='status',
            field=django_common_objects.fields.CharField(choices=[('I', '初始化'), ('R', '运行中'), ('S', '运行成功'), ('E', '执行成功了，但是没有日志'), ('X', '运行异常'), ('F', '任务失败, 无需重试'), ('T', '超时')], max_length=1, verbose_name='运行状态'),
        ),
        migrations.CreateModel(
            name='RetrySchedule',
            fields=[
                ('exceptionschedule_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='django_common_task_system.exceptionschedule')),
            ],
            options={
                'verbose_name': '待重试计划',
                'verbose_name_plural': '待重试计划',
                'ordering': ('id', '-schedule_time'),
                'managed': False,
            },
            bases=('django_common_task_system.exceptionschedule',),
        ),
        migrations.DeleteModel(
            name='MissingSchedule',
        ),
    ]