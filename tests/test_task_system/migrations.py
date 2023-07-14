import os

if __name__ == '__main__':
    os.system('python manage.py makemigrations system_task')
    os.system('python manage.py migrate system_task')
