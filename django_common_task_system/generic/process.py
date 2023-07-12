from multiprocessing import set_start_method, Process


def start_client(client):
    import django

    django.setup()

    set_start_method('spawn', True)
    from django_common_task_system.generic.client import start_client
    process = Process(target=start_client, args=(client,), daemon=True)
    process.start()
