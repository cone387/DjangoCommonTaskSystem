from setuptools import setup, find_packages

setup(
    name='django-common-task-system',
    packages=find_packages(exclude=['local_tests', 'tests']),
    version='2.0.0',
    install_requires=[
        "django-common-objects>=1.0.8",
        "django>=3.2.18",
        "croniter>=1.3.8",
        "djangorestframework>=3.14.0",
        "PyMySQL>=1.0.2",
        "jionlp-time>=1.0.0",
    ],
    include_package_data=True,
    author='cone387',
    maintainer_email='1183008540@qq.com',
    license='MIT',
    url='https://github.com/cone387/DjangoCommonTaskSystem.git',
    python_requires='>=3.7, <4',
    entry_points={
        'console_scripts': [
            'django-common-task-system=django_common_task_system_server.manage:main',
        ],
    },
)
