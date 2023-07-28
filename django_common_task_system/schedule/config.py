from django_common_task_system.utils.cron_utils import get_next_cron_time
from jionlp_time import parse_time
from django_common_task_system.utils.schedule_time import nlp_config_to_schedule_config
from datetime import datetime, timedelta
from django.core.validators import ValidationError
from django_common_task_system.choices import ScheduleTimingType, ScheduleType


mdays = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


class ScheduleConfig:

    def __init__(self,
                 base_on_now=True,
                 nlp_sentence=None,
                 schedule_type=None,
                 crontab=None,
                 period_schedule=None,
                 once_schedule=None,
                 timing_type=None,
                 timing_period=None,
                 timing_time=None,
                 timing_weekday=None,
                 timing_monthday=None,
                 timing_year=None,
                 timing_datetime=None,
                 config=None,
                 **kwargs):
        self.base_on_now = base_on_now
        self.nlp_sentence = nlp_sentence
        self.schedule_type = schedule_type
        self.once_schedule = once_schedule
        self.period_schedule = period_schedule
        self.crontab = crontab
        self.timing_type = timing_type
        self.timing_period = timing_period
        self.timing_time = timing_time
        self.timing_weekday = timing_weekday
        self.timing_monthday = timing_monthday
        self.timing_year = timing_year
        self.timing_datetime = timing_datetime
        self.kwargs = kwargs
        self.config = config or self.to_config()
        if config:
            self.parse_config(config)

    def parse_config(self, config):
        schedule_type = self.schedule_type = config['schedule_type']
        self.base_on_now = config.get('base_on_now', False)
        type_config = config[schedule_type]
        if schedule_type == ScheduleType.ONCE:
            self.once_schedule = type_config['schedule_start_time']
        elif schedule_type == ScheduleType.CRONTAB:
            self.crontab = type_config['crontab']
        elif schedule_type == ScheduleType.CONTINUOUS:
            self.period_schedule = [
                type_config["schedule_start_time"],
                type_config["period"]
            ]
        elif schedule_type == ScheduleType.TIMINGS:
            timing_type = self.timing_type = type_config["type"]
            self.timing_time = datetime.strptime(type_config["time"], '%H:%M:%S')
            timing_config = type_config[timing_type]
            self.timing_period = timing_config.get('period')
            if timing_type == ScheduleTimingType.DAY:
                pass
            elif timing_type == ScheduleTimingType.WEEKDAY:
                self.timing_monthday = timing_config['weekday']
            elif timing_type == ScheduleTimingType.MONTHDAY:
                self.timing_monthday = timing_config['monthday']
            elif timing_type == ScheduleTimingType.YEAR:
                self.timing_year = timing_config['year']

    def to_config(self):
        if self.nlp_sentence:
            result = parse_time(self.nlp_sentence)
            config = nlp_config_to_schedule_config(result, sentence=self.nlp_sentence)
            self.schedule_type = config['schedule_type']
            return config
        config = {
            'schedule_type': self.schedule_type,
            'base_on_now': self.base_on_now,
        }
        schedule_type = self.schedule_type
        type_config: dict = config.setdefault(self.schedule_type, {})
        if schedule_type == ScheduleType.CRONTAB:
            if not self.crontab:
                raise ValidationError('crontab is required while type is crontab')
            type_config['crontab'] = self.crontab
        elif schedule_type == ScheduleType.CONTINUOUS:
            if not self.period_schedule:
                raise ValidationError("period_schedule is required while type is continuous")
            schedule_time, period = self.period_schedule
            if period == 0:
                raise ValidationError("period can't be 0 while type is continuous")
            type_config['period'] = period
            type_config['schedule_start_time'] = schedule_time
        elif schedule_type == ScheduleType.ONCE:
            type_config['schedule_start_time'] = self.once_schedule
        elif schedule_type == ScheduleType.TIMINGS:
            timing_type = self.timing_type
            type_config['time'] = self.timing_time.strftime('%H:%M:%S')
            type_config['type'] = timing_type
            timing_config = type_config.setdefault(timing_type, {})
            if timing_type == ScheduleTimingType.DAY:
                if self.timing_period == 0:
                    raise ValidationError("period can't be 0 while type is timing")
                timing_config['period'] = self.timing_period
            elif timing_type == ScheduleTimingType.WEEKDAY:
                if not self.timing_weekday:
                    raise ValidationError("weekdays is required while type is timing")
                timing_config['period'] = self.timing_period
                timing_config['weekday'] = self.timing_weekday
            elif timing_type == ScheduleTimingType.MONTHDAY:
                timing_config['period'] = self.timing_period
                timing_config['monthday'] = self.timing_monthday
            elif timing_type == ScheduleTimingType.YEAR:
                timing_config['period'] = self.timing_period
                timing_config['year'] = self.timing_year
            elif timing_type == ScheduleTimingType.DATETIME:
                timing_config['datetime'] = self.timing_datetime
            else:
                raise ValidationError("timing_type is invalid")
        else:
            raise ValidationError("type<%s> is invalid" % schedule_type)
        return config

    def get_current_time(self, start_time=None):
        if self.base_on_now:
            now = datetime.now()
        else:
            if start_time and start_time != datetime.min:
                now = datetime.fromtimestamp(start_time.timestamp())
            else:
                now = datetime.now()
        now_seconds = now.hour * 3600 + now.minute * 60 + now.second
        schedule_type = self.schedule_type
        type_config = self.config[schedule_type]
        schedule_time = None
        if schedule_type == ScheduleType.CONTINUOUS.value:
            schedule_time, period = self.period_schedule
            while schedule_time < now:
                schedule_time += timedelta(seconds=period)
        elif schedule_type == ScheduleType.CRONTAB.value:
            schedule_time = get_next_cron_time(type_config['crontab'], now)
        elif schedule_type == ScheduleType.TIMINGS:
            timing_type = type_config['type']
            hour, minute, second = type_config['time'].split(':')
            hour, minute, second = int(hour), int(minute), int(second)
            timing_config = type_config[timing_type]
            if timing_type == ScheduleTimingType.DAY:
                schedule_time = datetime(now.year, now.month, now.day, hour, minute, second)
                while schedule_time < now:
                    schedule_time += timedelta(days=timing_config['period'])
            elif timing_type == ScheduleTimingType.WEEKDAY:
                weekdays = timing_config['weekday']
                weekday = now.isoweekday()
                schedule_again = weekday not in weekdays
                if not schedule_again:
                    schedule_time = datetime(now.year, now.month, now.day, hour, minute, second)
                    if now > schedule_time:
                        schedule_again = True
                if schedule_again:
                    for i in weekdays:
                        if i > weekday:
                            days = i - weekday
                            delta = timedelta(days=days)
                            break
                    else:
                        days = weekday - weekdays[0]
                        delta = timedelta(days=timing_config['period'] * 7 - days)
                    schedule_time = datetime(now.year, now.month, now.day, hour, minute, second) + delta
            elif timing_type == ScheduleTimingType.MONTHDAY:
                monthdays = timing_config['monthday']
                if not monthdays:
                    raise ValidationError("monthdays is required while type is timing-monthday")
                schedule_again = now.day not in monthdays
                if not schedule_again:
                    schedule_time = datetime(now.year, now.month, now.day, hour, minute, second)
                    if now > schedule_time:
                        schedule_again = True
                if schedule_again:
                    def next_month(y, m):
                        if m == 12:
                            return y + 1, 1
                        else:
                            return y, m + 1
                    for i in monthdays:
                        if i == 0:
                            i = 1
                        elif i == 32:
                            i = mdays[now.month]
                        if i > now.day:
                            schedule_time = datetime(now.year, now.month, i, hour, minute, second)
                            break
                    else:
                        year, month = next_month(now.year, now.month)
                        schedule_time = datetime(year, month, monthdays[0], hour, minute, second)
            elif timing_type == ScheduleTimingType.YEAR:
                month_days = timing_config['year']
                if not month_days:
                    raise ValidationError("year month day is required while type is timing-datetime")
                month, day = 1, 1
                for i in month_days.split(","):
                    month, day = i.split('-')
                    month, day = int(month), int(day)
                    d = datetime(now.year, month, day, hour, minute, second)
                    if d > now:
                        schedule_time = d
                        break
                else:
                    schedule_time = datetime(now.year + timing_config['period'], month, day, hour, minute, second)
            elif timing_type == ScheduleTimingType.DATETIME:
                dates, t = timing_config['datetime']
                if not dates:
                    raise ValidationError("datetime is required while type is timing-datetime")
                if t:
                    t: datetime.time
                    seconds = t.hour * 3600 + t.minute * 60 + t.second
                else:
                    seconds = 0
                for i in dates.split(','):
                    d = datetime.strptime(i, '%Y-%m-%d')
                    if d > now or (d == now and seconds >= now_seconds):
                        break
                else:
                    raise ValidationError("cant find a datetime after now")
                schedule_time = datetime(d.year, d.month, d.day, t.hour, t.minute, t.second)
            else:
                raise ValidationError('unsupported timing_type<%s>' % timing_type)
        elif schedule_type == ScheduleType.ONCE:
            schedule_time = type_config['schedule_start_time']
        else:
            raise ValidationError("type<%s> is invalid" % schedule_type)
        if isinstance(schedule_time, str):
            schedule_time = datetime.strptime(schedule_time, '%Y-%m-%d %H:%M:%S')
        # if schedule_time < now:
        #     raise ValidationError("cant create a schedule time before now, schedule_time<%s>" % schedule_time)
        return schedule_time

    def get_next_time(self, last_time: datetime):
        schedule_type = self.schedule_type
        type_config = self.config[schedule_type]
        if self.base_on_now:
            last_time = datetime.now()
        next_time = last_time
        if schedule_type == ScheduleType.CONTINUOUS.value:
            while next_time <= last_time:
                next_time += timedelta(seconds=self.period_schedule[1])
        elif schedule_type == ScheduleType.CRONTAB.value:
            next_time = get_next_cron_time(type_config['crontab'], last_time)
        elif schedule_type == ScheduleType.TIMINGS:
            timing_type = type_config['type']
            hour, minute, second = type_config['time'].split(':')
            hour, minute, second = int(hour), int(minute), int(second)
            timing_config = type_config[timing_type]
            timing_period = timing_config.get('period', 1)
            next_time = datetime(next_time.year, next_time.month, next_time.day, hour, minute, second)
            if timing_type == ScheduleTimingType.DAY:
                while next_time <= last_time:
                    next_time += timedelta(days=timing_period)
            elif timing_type == ScheduleTimingType.WEEKDAY:
                weekdays = timing_config['weekday']
                weekday = last_time.isoweekday()
                for i in weekdays:
                    if i > weekday:
                        days = i - weekday
                        delta = timedelta(days=days)
                        break
                else:
                    days = weekday - weekdays[0]
                    delta = timedelta(days=timing_period * 7 - days)
                next_time = next_time + delta
            elif timing_type == ScheduleTimingType.MONTHDAY:
                monthdays = timing_config['monthday']
                day = 1
                for day in monthdays:
                    if day == 0:
                        day = 1
                    elif day == 32:
                        day = mdays[last_time.month]
                    next_time = datetime(last_time.year, last_time.month, day, hour, minute, second)
                    if next_time > last_time:
                        break
                else:
                    month = (last_time.month + timing_period) % 12
                    if month == 0:
                        month = 1
                    year = last_time.year + (last_time.month + timing_period) // 12
                    next_time = datetime(year, month, day, hour, minute, second)
            elif timing_type == ScheduleTimingType.YEAR:
                month_days = timing_config['year']
                if not month_days:
                    raise ValidationError("year month day is required while type is timing-datetime")
                month, day = 1, 1
                for i in month_days.split(","):
                    month, day = i.split('-')
                    month, day = int(month), int(day)
                    next_time = datetime(last_time.year, month, day, hour, minute, second)
                    if next_time > last_time:
                        break
                else:
                    next_time = datetime(last_time.year + timing_period, month, day, hour, minute, second)
            else:
                raise ValidationError("unsupported timing type: %s" % schedule_type)
        elif schedule_type == ScheduleType.ONCE:
            next_time = datetime.max
        else:
            raise ValidationError("unsupported schedule type: %s" % schedule_type)
        return next_time
