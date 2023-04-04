import os
import argparse
import sys


if __name__ == '__main__':
    import django
    parser = argparse.ArgumentParser()
    parser.add_argument('--system-path', type=str, required=True)
    parser.add_argument('--system-setting', type=str, required=False)
    args = parser.parse_args()
    sys.path.append(args.system_path)
    env = args.system_setting or os.environ.get('DJANGO_SETTINGS_MODULE')
    assert env, 'django settings module not found'
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', env)
    django.setup()

    from system_task_execution.executor import Runner
    runner = Runner(args.system_path, args.system_setting)
    runner.start()
