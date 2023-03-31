
from django.db.models import TextChoices


class SystemTaskType(TextChoices):
    SQL = 'SQL', 'SQL脚本'
    SCRIPT = 'SHELL', 'Shell脚本'
    TASK_PRODUCE = 'TASK_PRODUCE', '任务生产'

