FROM ubuntu:22.04

MAINTAINER cone

ENV TZ=Asia/Shanghai
ENV LANG zh_CN.UTF-8

# 1. 安装Python3.11
RUN apt-get update -y
RUN apt-get install -y python3.11
# 重命名python3.11为python3, pip3.11为pip3
RUN mv /usr/bin/python3.11 /usr/bin/python

RUN apt-get install curl -y
RUN curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
RUN python get-pip.py

ENV PROJECT_DIR /home/django-common-task-system
ENV PYTHONPATH "${PYTHONPATH}:$PROJECT_DIR"

# 设置工作目录
WORKDIR $PROJECT_DIR

# 复制项目文件到容器
COPY . $PROJECT_DIR

## 2. 安装依赖
RUN pip config --global set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
# 安装项目依赖
RUN pip install -r requirements.txt

#WORKDIR $PROJECT_DIR/django_common_task_system_server
ENTRYPOINT ./entrypoint.sh
# demo就不用gunicorn启动了， 因为guniorn不会代理静态文件
#ENTRYPOINT python manage.py collectstatic --noinput && python manage.py start --migrate --createsuperuser

#ENTRYPOINT python manage.py collectstatic --noinput && gunicorn server.wsgi:application --bind 0.0.0.0:8000
