from django_common_task_system.choices import ConsumerPermissionType


class _ConsumerPermissionValidator(dict):

    def __call__(self, name):
        def wrapper(cls):
            self[name] = cls
            return cls
        return wrapper


ConsumerPermissionValidator = _ConsumerPermissionValidator()


class BaseValidator:

    def __init__(self, config):
        self.config = config

    def validate(self, request):
        return None


@ConsumerPermissionValidator(name=ConsumerPermissionType.IP_WHITE_LIST)
class IPWhiteListValidator(BaseValidator):

    def __init__(self, config):
        super(IPWhiteListValidator, self).__init__(config)
        self.ip_list = config.get('ip_whitelist', [])

    def validate(self, request):
        ip = request.META.get('HTTP_X_FORWARDED_FOR') if request.META.get('HTTP_X_FORWARDED_FOR') else \
            request.META.get('REMOTE_ADDR')
        if ip not in self.ip_list:
            return "IP %s Not Allowed" % ip

