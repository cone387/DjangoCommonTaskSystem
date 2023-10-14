from django.apps import apps as django_apps
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management.commands import runserver
from django.utils.module_loading import import_string
from django.dispatch import Signal
import os


class Command(runserver.Command):

    def run(self, **options):
        import os
        os.environ['DJANGO_SERVER_ADDRESS'] = "%(protocol)s://%(addr)s:%(port)s" % {
            'protocol': self.protocol,
            'addr': self.addr.replace('0.0.0.0', '127.0.0.1'),
            'port': self.port
        }
        super().run(**options)


runserver.Command = Command

system_initialized_signal = Signal()


if not hasattr(settings, 'TASK_MODEL'):
    setattr(settings, 'TASK_MODEL', 'django_common_task_system.Task')

if not hasattr(settings, 'SCHEDULE_MODEL'):
    setattr(settings, 'SCHEDULE_MODEL', 'django_common_task_system.Schedule')

if not hasattr(settings, 'SCHEDULE_LOG_MODEL'):
    setattr(settings, 'SCHEDULE_LOG_MODEL', 'django_common_task_system.ScheduleLog')

if not hasattr(settings, 'SCHEDULE_SERIALIZER'):
    setattr(settings, 'SCHEDULE_SERIALIZER', 'django_common_task_system.serializers.QueueScheduleSerializer')


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


def get_schedule_model():
    """
    Return the User model that is active in this project.
    """
    try:
        return django_apps.get_model(settings.SCHEDULE_MODEL, require_ready=False)
    except ValueError:
        raise ImproperlyConfigured(
            "SCHEDULE_MODEL must be of the form 'app_label.model_name'"
        )
    except LookupError:
        raise ImproperlyConfigured(
            "SCHEDULE_MODEL refers to model '%s' that has not been installed"
            % settings.SCHEDULE_MODEL
        )


def get_schedule_log_model():
    """
    Return the User model that is active in this project.
    """
    try:
        return django_apps.get_model(settings.SCHEDULE_LOG_MODEL, require_ready=False)
    except ValueError:
        raise ImproperlyConfigured(
            "SCHEDULE_LOG_MODEL must be of the form 'app_label.model_name'"
        )
    except LookupError:
        raise ImproperlyConfigured(
            "SCHEDULE_LOG_MODEL refers to model '%s' that has not been installed"
            % settings.SCHEDULE_LOG_MODEL
        )


def get_schedule_serializer():
    """
    Return the User model that is active in this project.
    """
    return import_string(settings.SCHEDULE_SERIALIZER)
