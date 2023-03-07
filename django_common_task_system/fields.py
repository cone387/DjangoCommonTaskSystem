from django.core.exceptions import ValidationError
from django.db import models
import json
from datetime import datetime, time as dt_time


class DatetimeJsonEncoder(json.JSONEncoder):

    def default(self, o) -> str:
        if isinstance(o, datetime):
            return o.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(o, dt_time):
            return o.strftime("%H:%M:%S")
        return super(DatetimeJsonEncoder, self).default(o)


class ScheduleConfigField(models.JSONField):

    _default_encoder = DatetimeJsonEncoder

    def get_prep_value(self, value):
        if value is None:
            return value
        return json.dumps(value, cls=self._default_encoder)

    def validate(self, value, model_instance):
        try:
            json.dumps(value, ensure_ascii=False, indent=2, cls=self._default_encoder)
        except TypeError as e:
            raise ValidationError(
                self.error_messages["invalid"],
                code="invalid",
                params={"value": e},
            )
