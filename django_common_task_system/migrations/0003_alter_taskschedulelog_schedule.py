# Generated by Django 4.1.7 on 2023-03-31 03:28

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('django_common_task_system', '0002_alter_taskschedule_unique_together'),
    ]

    operations = [
        migrations.AlterField(
            model_name='taskschedulelog',
            name='schedule',
            field=models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.CASCADE, related_name='logs', to=settings.TASK_SCHEDULE_MODEL, verbose_name='任务计划'),
        ),
    ]
