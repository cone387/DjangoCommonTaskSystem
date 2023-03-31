from django.apps import apps as django_apps
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from django_common_task_system.management.commands.runserver import Command
from django.core.management.commands import runserver
runserver.Command = Command


if not hasattr(settings, 'TASK_MODEL'):
    setattr(settings, 'TASK_MODEL', 'django_common_task_system.Task')

if not hasattr(settings, 'TASK_SCHEDULE_MODEL'):
    setattr(settings, 'TASK_SCHEDULE_MODEL', 'django_common_task_system.TaskSchedule')

if not hasattr(settings, 'TASK_SCHEDULE_LOG_MODEL'):
    setattr(settings, 'TASK_SCHEDULE_LOG_MODEL', 'django_common_task_system.TaskScheduleLog')


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
