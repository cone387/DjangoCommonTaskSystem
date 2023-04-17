# Generated by Django 4.1.7 on 2023-04-13 13:28

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('system_task', '0002_remove_systemtask_task_type_systemtask_tags'),
    ]

    operations = [
        migrations.AddField(
            model_name='systemschedulequeue',
            name='config',
            field=models.JSONField(default=dict, verbose_name='配置'),
        ),
        migrations.AlterField(
            model_name='systemschedulequeue',
            name='module',
            field=models.CharField(choices=[('queue.Queue', '普通队列'), ('queue.LifoQueue', '后进先出队列'), ('queue.PriorityQueue', '优先级队列'), ('_queue.SimpleQueue', '简单队列'), ('django_common_task_system.system_task.queue.RedisListQueue', 'Redis List队列')], default='queue.Queue', max_length=100, verbose_name='队列类型'),
        ),
        migrations.CreateModel(
            name='SystemScheduleProducer',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='生产者名称')),
                ('filters', models.JSONField(verbose_name='过滤器')),
                ('lte_now', models.BooleanField(default=True, verbose_name='小于等于当前时间')),
                ('status', models.BooleanField(default=True, verbose_name='启用状态')),
                ('create_time', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('update_time', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('queue', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.CASCADE, related_name='producers', to='system_task.systemschedulequeue', verbose_name='队列')),
            ],
            options={
                'verbose_name': '计划生产',
                'verbose_name_plural': '计划生产',
                'db_table': 'system_schedule_producer',
                'abstract': False,
            },
        ),
    ]