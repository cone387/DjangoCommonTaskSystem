from django.contrib.admin.apps import AdminConfig


class SystemAdminConfig(AdminConfig):
    default_site = 'django_common_objects.site.CommonAdminSite'
