

def create_superuser():
    import os
    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_task_system.settings')
    django.setup()

    from django.contrib.auth.models import User
    username = 'cone'
    password = '3.1415926'
    user = User(
        username=username,
    )
    user.set_password(password)
    user.is_superuser = True
    user.is_staff = True
    user.save()


create_superuser()
