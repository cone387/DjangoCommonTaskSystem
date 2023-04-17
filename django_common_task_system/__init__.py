from django.apps import apps as django_apps
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management.commands import runserver
from django.utils.module_loading import import_string


class Command(runserver.Command):

    def run(self, **options):
        import os
        os.environ['DJANGO_SERVER_ADDRESS'] = "%(protocol)s://%(addr)s:%(port)s" % {
            'protocol': self.protocol,
            'addr': self.addr,
            'port': self.port
        }
        super().run(**options)


runserver.Command = Command


if not hasattr(settings, 'TASK_MODEL'):
    setattr(settings, 'TASK_MODEL', 'django_common_task_system.Task')

if not hasattr(settings, 'TASK_SCHEDULE_MODEL'):
    setattr(settings, 'TASK_SCHEDULE_MODEL', 'django_common_task_system.TaskSchedule')

if not hasattr(settings, 'TASK_SCHEDULE_LOG_MODEL'):
    setattr(settings, 'TASK_SCHEDULE_LOG_MODEL', 'django_common_task_system.TaskScheduleLog')

if not hasattr(settings, 'TASK_SCHEDULE_SERIALIZER'):
    setattr(settings, 'TASK_SCHEDULE_SERIALIZER', 'django_common_task_system.serializers.TaskScheduleSerializer')


def get_task_model():
    """
    Return the User model that is active in this project.
    """
    try:
        return django_apps.get_model(settings.TASK_MODEL, require_ready=False)
    except ValueError:
        raise ImproperlyConfigured(
            "TASK_MODEL must be of the form 'app_label.model_name'"
        )
    except LookupError:
        raise ImproperlyConfigured(
            "TASK_MODEL refers to model '%s' that has not been installed"
            % settings.TASK_MODEL
        )


def get_task_schedule_model():
    """
    Return the User model that is active in this project.
    """
    try:
        return django_apps.get_model(settings.TASK_SCHEDULE_MODEL, require_ready=False)
    except ValueError:
        raise ImproperlyConfigured(
            "TASK_SCHEDULE_MODEL must be of the form 'app_label.model_name'"
        )
    except LookupError:
        raise ImproperlyConfigured(
            "TASK_SCHEDULE_MODEL refers to model '%s' that has not been installed"
            % settings.TASK_SCHEDULE_MODEL
        )


def get_schedule_log_model():
    """
    Return the User model that is active in this project.
    """
    try:
        return django_apps.get_model(settings.TASK_SCHEDULE_LOG_MODEL, require_ready=False)
    except ValueError:
        raise ImproperlyConfigured(
            "TASK_SCHEDULE_LOG_MODEL must be of the form 'app_label.model_name'"
        )
    except LookupError:
        raise ImproperlyConfigured(
            "TASK_SCHEDULE_LOG_MODEL refers to model '%s' that has not been installed"
            % settings.SCHEDULE_LOG_MODEL
        )


def get_task_schedule_serializer():
    """
    Return the User model that is active in this project.
    """
    return import_string(settings.TASK_SCHEDULE_SERIALIZER)
