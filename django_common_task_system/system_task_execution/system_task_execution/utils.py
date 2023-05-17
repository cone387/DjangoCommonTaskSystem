from django_common_task_system.models import AbstractTaskSchedule
import requests


def put_schedule(url: str, schedule: AbstractTaskSchedule, queue: str, datetimes: list):
    batch_num = 1000
    batch = datetimes[:batch_num]
    result = {}
    error = None
    i = 0
    while batch:
        batch_result = requests.post(url, data={
            'i': ','.join([str(schedule.id)] * len(batch)),
            'q': queue,
            't': ','.join(batch)
        }).json()
        result[i] = batch_result
        if 'error' in batch_result:
            error = batch_result['error']
        i += 1
        batch = datetimes[i * batch_num: (i + 1) * batch_num]
    if error:
        raise Exception(error)
    return result


def to_model(result, model):
    obj = model()
    for f in model._meta.fields:
        name = f.name
        value = result.pop(name, None)
        if not value:
            continue
        t = f.__class__.__name__
        if t == 'ForeignKey':
            if isinstance(value, dict):
                setattr(obj, name, to_model(value, f.related_model))
            else:
                setattr(obj, name + "_id", value)
        else:
            setattr(obj, name, value)
    return obj
