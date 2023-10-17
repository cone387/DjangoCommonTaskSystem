from multiprocessing import set_start_method, Process
import os
import time


# 因为该进程是由Process(daemon=True), 所以不能在该进程中再启动子进程，需要放在外面启动
# AssertionError: daemonic processes are not allowed to have children
# from django_common_task_system.cache_service import ensure_service_available
# ensure_service_available()


class Engine(Process):
    def __init__(self):
        Process.__init__(self, daemon=True)
        super(Engine, self).__init__(name='Engine')

    def run(self) -> None:
        import django
        django.setup()
        from django_common_task_system.producer import producer_agent
        from django_common_task_system.system_task_execution import consumer_agent

        producer_agent.start()
        consumer_agent.start()
        if producer_agent.is_running or consumer_agent.is_running:
            print("system process started, pid: %s" % os.getpid())
            while True:
                time.sleep(10)
        else:
            print("system process started already, ignored")

    def start(self):
        from django_common_task_system import cache_service
        cache_service.ensure_service_available()
        set_start_method('spawn', force=True)
        super(Engine, self).start()


engine = Engine()
