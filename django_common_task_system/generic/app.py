from django.conf import settings


class AppStr(str):

    @property
    def is_installed(self):
        return self in settings.INSTALLED_APPS


class App:

    system_task = AppStr('django_common_task_system.system_task')
    user_task = AppStr('django_common_task_system')
