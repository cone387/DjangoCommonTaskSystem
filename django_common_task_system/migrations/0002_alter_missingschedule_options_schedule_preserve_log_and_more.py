# Generated by Django 4.1.7 on 2023-08-02 10:04

from django.db import migrations, models
import django.utils.timezone
import django_common_objects.fields


class Migration(migrations.Migration):

    dependencies = [
        ('django_common_task_system', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='missingschedule',
            options={'managed': False, 'ordering': ('-priority', 'next_schedule_time'), 'verbose_name': '缺失调度', 'verbose_name_plural': '缺失调度'},
        ),
        migrations.AddField(
            model_name='schedule',
            name='preserve_log',
            field=models.BooleanField(default=True, verbose_name='保留日志'),
        ),
        migrations.AlterField(
            model_name='schedule',
            name='update_time',
            field=models.DateTimeField(default=django.utils.timezone.now, verbose_name='更新时间'),
        ),
        migrations.AlterField(
            model_name='schedulelog',
            name='status',
            field=django_common_objects.fields.CharField(choices=[('I', 'Init'), ('R', 'Running'), ('S', 'Succeed'), ('E', 'Empty'), ('N', 'Error But No Retry'), ('F', 'Failed'), ('D', 'Done'), ('T', 'Timeout')], max_length=1, verbose_name='运行状态'),
        ),
    ]