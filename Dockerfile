FROM cone387/ubuntu-python311:latest

MAINTAINER cone

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
ENTRYPOINT ["/bin/bash", "entrypoint.sh"]
# demo就不用gunicorn启动了， 因为guniorn不会代理静态文件
#ENTRYPOINT python manage.py collectstatic --noinput && python manage.py start --migrate --createsuperuser

#ENTRYPOINT python manage.py collectstatic --noinput && gunicorn server.wsgi:application --bind 0.0.0.0:8000
