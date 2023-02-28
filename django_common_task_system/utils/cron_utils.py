from croniter import croniter
from datetime import datetime


def get_next_cron_time(cron, start_time=None, ret_type=datetime):
    start_time = start_time or datetime.now()
    return croniter(cron, start_time, ret_type).get_next()
