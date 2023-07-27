import os
from django.core.management import execute_from_command_line

if __name__ == '__main__':
    # os.system('python manage.py makemigrations system_task')
    # os.system('python manage.py migrate system_task')

    execute_from_command_line('manage.py makemigrations'.split())
    execute_from_command_line('manage.py migrate'.split())
