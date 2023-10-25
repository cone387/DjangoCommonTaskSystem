# DjangoCommonTaskSystem

## 部署

### 安装
```shell
pip install django-common-task-system
```

### 配置
```python
INSTALLED_APPS = [
    ...
    'django_common_task_system',
    ...
]
```

### 运行/停止/重启
```shell
django-common-task-system start/stop/restart
```

### 发布
- 发布到PyPI(默认)
```shell
sh deploy.sh -t pypi
```

- 打包镜像并推送到DockerHub

```shell
sh deploy.sh -t docker
```
- 部署到服务器
```shell
sh deploy.sh -t server -s your_setting_module_path[optinal]
```


## 计划模式

### 普通模式
当任务太多，有延迟时，会跳过延迟的任务，直接执行下一个时间节点的任务

### 严格模式
严格按照计划时间来运行, 即使任务延迟了，也会产生对应时间节点的任务


## 任务分类
### 1. 系统基础
系统基础类任务不能直接创建计划，只能通过配置子任务来创建计划

### 2. 系统任务
系统任务表示系统的基础功能，如日志清理，任务生产线程，任务执行线程等，该任务状态为AUTO
为系统单独创建任务状态是因为在调度查询任务时, 可以不用查询分类表，提高查询效率

### 3. 业务任务
业务任务表示业务功能，由任务客户端消费。

#### 几个基础业务任务
1. 执行Shell命令(可以用来清理docker日志、使用curl定时调用接口等)
2. 执行SQL语句(日志清理任务可以通过建立该任务子任务来实现)
3. 执行SQL语句生产任务(可以用来生成任务, 比如将某一个表中的数据作为任务, 常见的比如由微博用户表，则可以通过该语句定时将待采集用户查询到任务队列)
4. 自定义程序(可以执行自定义脚本)

#### 自定义程序创建规范
1. 任务客户端需要安装python3.6+环境


### 4. 测试任务
测试使用


## 定时方式
- [x] crontab表达式
- [x] nlp语义解析
- [x] 连续时间段(x秒后执行)
- [x] 自选日期时间


## 任务队列

### 支持的类型
- [x] redis
- [x] thread queue
- [x] process queue
- [x] socket queue

> 目前在MacOS上使用Multiprocessing.Queue会报错


### 队列权限
- [x] 白名单设置

### 消费方式
- [x] HTTP接口轮询
- [ ] WebSocket推送


## 调度线程
### 任务生产线程
查询任务生产计划表，根据生产计划查询出对应的任务，放入任务队列中
- [x] 自定义查询任务

### 潜在的问题
配置了多个任务生产线程，可能会导致重复生产任务, 导致任务计划时间重复, 
目前只能靠人工判断避免这种情况

## 系统任务线执行程
### 待处理任务
- 处理异常任务，重试
- 严格计划模式下，处理延迟任务
- 日志清理, 删除一个月前的日志

### 异常重试任务
- [x] 可以设置最大重试次数

### 管理
-[x] 在admin中启动/停止任务线程


## 任务客户端管理
-[x] 启动/停止任务客户端 
-[ ] 上报任务客户端状态

任务客户端访问消费任务的接口也会视为一次心跳, 用来判断任务客户端是否存活
心跳信息内容包含以下字段
```json
{
  "consumer_id": "任务客户端ID",
  "machine_ip": "任务客户端IP",
}
```
将任务客户端数据存储到缓存服务中, 存储格式为
```json
{
  "client_id": {
    "machine": {
      "hostname": "",
      "internal_ip": "",
      "external_ip": ""
    },
    "process_id": "",
    "container": {
        "id": "",
        "name": "",
        "image": ""
    }
  }
}
```


## 日志
- [x] 记录计划执行日志(HTTP接口上报)
- [x] 自动删除一个月前的日志(由日志清理任务完成)

## 异常处理
- [x] 记录任务执行异常日志(HTTP接口上报)

## TODO
- [ ] 支持指定任务客户端执行任务
