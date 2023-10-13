from .thread import ScheduleConsumerThread
from django_common_task_system.program import ProgramAgent


consumer_agent = ProgramAgent(program_class=ScheduleConsumerThread)
