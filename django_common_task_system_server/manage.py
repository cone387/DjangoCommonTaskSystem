#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
import shutil
import argparse
from django.core.management import execute_from_command_line


def create_superuser(username=None, password=None):
    import django
    django.setup()
    from django.contrib.auth.models import User
    username = username or 'root'
    password = password or '3.1415926'
    user, created = User.objects.get_or_create(
        username=username,
        defaults={
            'is_superuser': True,
            'is_staff': True,
        }
    )
    if created:
        user.set_password(password)
        user.save()
        print('superuser created: %s' % username)


def init_server(args=None):
    if args and args.migrate:
        execute_from_command_line(sys.argv[:1] + ['makemigrations'])
        execute_from_command_line(sys.argv[:1] + ['migrate'])
    if args and args.createsuperuser:
        create_superuser(args.user, args.password)


def start_server(args=None):
    init_server(args)
    execute_from_command_line(sys.argv[:1] + ['runserver', args.address if args and args.address else '0.0.0.0:8000'])


def stop_server(executables=None):
    results = []
    if sys.platform == 'win32':
        executables = executables or ['django-common-task-system.exe']
        try:
            import psutil
        except ImportError:
            raise ImportError('psutil is not installed, please install it first on windows.')
        for proc in psutil.process_iter():
            name = proc.name()
            if name in executables:
                proc.kill()
                results.append("%s-%s killed" % (proc.pid, name))
    else:
        import subprocess
        executables = executables or ['django-common-task-system']
        for executable in executables:
            ret = subprocess.call(f"ps -ef | grep '{executable}' | grep -v grep | awk '{{print $2}}' | xargs kill -9",
                                  shell=True)
            results.append(f"{executable} killed, return code: {ret}")
    if results:
        for result in results:
            print(result)
    else:
        print('no matched process found of %s' % ','.join(executables))


def reload_server():
    stop_server()
    start_server()


def _start_system_process():
    import django
    django.setup()
    from django_common_task_system.schedule.backend import ScheduleThread
    from django_common_task_system.system_task_execution.main import SystemScheduleThread
    from django_common_task_system.builtins import builtins

    schedule_thread = ScheduleThread()
    schedule_thread.start()
    execution_thread = SystemScheduleThread(builtins.schedule_queues.system.queue)
    execution_thread.start()
    schedule_thread.join()
    execution_thread.join()


def start_system_process():
    from multiprocessing import Process, set_start_method
    set_start_method('spawn')
    process = Process(target=_start_system_process, daemon=True)
    process.start()
    with open('.system_process.pid', 'w') as f:
        f.write(str(process.pid))


def main():
    """Run administrative tasks."""
    DJANGO_SETTINGS_MODULE = os.environ.get('DJANGO_SETTINGS_MODULE')
    if DJANGO_SETTINGS_MODULE:
        if os.path.isfile(DJANGO_SETTINGS_MODULE):
            shutil.copy(DJANGO_SETTINGS_MODULE, os.path.abspath(
                os.path.join(os.path.dirname(__file__), 'server/custom_settings.py')
            ))
            os.environ['DJANGO_SETTINGS_MODULE'] = 'server.custom_settings'
        else:
            os.environ['DJANGO_SETTINGS_MODULE'] = DJANGO_SETTINGS_MODULE
    else:
        os.environ['DJANGO_SETTINGS_MODULE'] = 'server.settings'
    parser = argparse.ArgumentParser()
    parser.add_argument('option', nargs='?', default='')
    parser.add_argument('--migrate', action='store_true', default=False)
    parser.add_argument('--createsuperuser', action='store_true', default=False)
    parser.add_argument('--address', type=str, default='')
    parser.add_argument('-u', '--user', type=str)
    parser.add_argument('-p', '--password', type=str)
    args, _ = parser.parse_known_args()
    if args.option == 'init':
        init_server(args)
    elif args.option == 'start':
        start_system_process()
        start_server(args)
    elif args.option == 'stop':
        stop_server()
    elif args.option == 'reload':
        reload_server()
    else:
        if sys.argv[1] == 'runserver':
            start_system_process()
        execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
