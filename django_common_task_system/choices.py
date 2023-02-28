from django.db.models import TextChoices


class TaskStatus(TextChoices):
    ENABLE = 'E', '启用'
    DISABLE = 'D', '禁用'


class TaskScheduleStatus(TextChoices):
    OPENING = 'O', '开启'
    CLOSED = 'C', '关闭'
    DONE = 'D', '已完成'
    TEST = 'T', '测试'


class TaskScheduleType(TextChoices):
    CRONTAB = 'C', 'Crontab'
    ONETIME = 'O', '一次性'
    CONTINUOUS = 'S', '连续性'


class TaskCallbackStatus(TextChoices):
    ENABLE = 'E', '启用'
    DISABLE = 'D', '禁用'


class TaskCallbackEvent(TextChoices):
    SUCCEED = 'S', '成功'
    FAILED = 'F', '失败'
    DONE = 'D', '完成'
