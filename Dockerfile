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

## 2. 安装依赖
RUN pip config --global set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
RUN pip install asgiref>=3.6.0
RUN pip install croniter>=1.3.8
RUN pip install Django==4.1.7
RUN pip install django-common-objects>=1.0.7
RUN pip install djangorestframework>=3.14.0
RUN pip install jionlp-time>=1.0.0
RUN pip install python-dateutil>=2.8.2
RUN pip install pytz>=2022.7.1
RUN pip install six>=1.16.0
RUN pip install sqlparse>=0.4.3
RUN pip install tzdata>=2022.7
