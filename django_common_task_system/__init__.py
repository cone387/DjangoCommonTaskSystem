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


if not hasattr(settings, 'USER_TASK_MODEL'):
    setattr(settings, 'USER_TASK_MODEL', 'django_common_task_system.UserTask')

if not hasattr(settings, 'USER_SCHEDULE_MODEL'):
    setattr(settings, 'USER_SCHEDULE_MODEL', 'django_common_task_system.UserSchedule')

if not hasattr(settings, 'USER_SCHEDULE_LOG_MODEL'):
    setattr(settings, 'USER_SCHEDULE_LOG_MODEL', 'django_common_task_system.UserScheduleLog')

if not hasattr(settings, 'USER_SCHEDULE_SERIALIZER'):
    setattr(settings, 'USER_SCHEDULE_SERIALIZER', 'django_common_task_system.serializers.QueueScheduleSerializer')


def get_user_task_model():
    """
    Return the User model that is active in this project.
    """
    try:
        return django_apps.get_model(settings.USER_TASK_MODEL, require_ready=False)
    except ValueError:
        raise ImproperlyConfigured(
            "TASK_MODEL must be of the form 'app_label.model_name'"
        )
    except LookupError:
        raise ImproperlyConfigured(
            "TASK_MODEL refers to model '%s' that has not been installed"
            % settings.TASK_MODEL
        )


def get_user_schedule_model():
    """
    Return the User model that is active in this project.
    """
    try:
        return django_apps.get_model(settings.USER_SCHEDULE_MODEL, require_ready=False)
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
        return django_apps.get_model(settings.USER_SCHEDULE_LOG_MODEL, require_ready=False)
    except ValueError:
        raise ImproperlyConfigured(
            "USER_SCHEDULE_LOG_MODEL must be of the form 'app_label.model_name'"
        )
    except LookupError:
        raise ImproperlyConfigured(
            "USER_SCHEDULE_LOG_MODEL refers to model '%s' that has not been installed"
            % settings.USER_SCHEDULE_LOG_MODEL
        )


def get_user_schedule_serializer():
    """
    Return the User model that is active in this project.
    """
    return import_string(settings.USER_SCHEDULE_SERIALIZER)
