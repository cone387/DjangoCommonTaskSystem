import copy
from django.core.management.commands.runserver import Command as RunServerCommand
from django_common_task_system.error_schedule import run_error_handler


NewCommand = copy.deepcopy(RunServerCommand)


class Command(NewCommand):
    help = 'Closes the specified poll for voting'

    def add_arguments(self, parser):
        parser.add_argument('--add-error-handler', action='store_true', dest='add_error_handler', default=False, )
        super().add_arguments(parser)

    def handle(self, *args, **options):
        if options['add_error_handler']:
            run_error_handler()
        super().handle(*args, **options)
