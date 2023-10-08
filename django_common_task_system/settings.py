import os


class SystemSettings:

    LOG_PATH = os.path.join(os.getcwd(), 'logs')
    MAX_QUEUE_SIZE = 1000
    SCHEDULE_INTERVAL = 1
