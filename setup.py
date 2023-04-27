from setuptools import setup, find_packages

setup(
    name='django-common-task-system',
    packages=find_packages(exclude=['local_tests']),
    version='1.2.5',
    install_requires=[
        "django-common-objects>=1.0.5",
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
    url='https://github.com/cone387/CommonTaskSystemServer',
    python_requires='>=3.7, <4',
)