from django.apps import AppConfig


class SystemTaskConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'django_common_task_system.system_task'
    verbose_name = '系统任务'
    app_label = 'system_task'
