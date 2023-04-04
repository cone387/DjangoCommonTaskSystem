from django.contrib.admin.apps import AdminConfig


class TestTaskSystemAdminConfig(AdminConfig):
    default_site = 'django_common_objects.site.CommonAdminSite'
