from . import models
import os
from django import forms
from django_common_objects.widgets import JSONWidget
from django.conf import settings
from django_common_task_system.generic import forms as generic_forms


class InitialFileStr(str):

    @property
    def url(self):
        return self


class SystemTaskForm(generic_forms.TaskForm):
    config = forms.JSONField(
        label='配置',
        widget=JSONWidget(attrs={'style': 'width: 70%;'}),
        initial={},
        required=False,
    )
    queue = forms.ModelChoiceField(
        queryset=models.SystemScheduleQueue.objects.all(),
        required=False,
        label='任务队列',
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    include_meta = forms.BooleanField(
        label='包含元数据',
        required=False,
        initial=True
    )

    script = forms.CharField(
        label='脚本',
        widget=forms.Textarea(attrs={'style': 'width: 70%;'}),
        required=False
    )
    sql_config = generic_forms.SqlConfigField(required=False, label="SQL源", help_text="仅支持MySQL, 默认当前数据库")
    # 不知道为什么这里使用validators时，在admin新增任务时如果validator没通过，第一次会报错，第二次就不会报错了
    custom_program = generic_forms.CustomProgramField(required=False, help_text='仅支持zip、python、shell格式')

    executable_path = os.path.join(settings.STATIC_ROOT or os.path.join(os.getcwd(), 'static'), 'executable')

    def __init__(self, *args, **kwargs):
        super(SystemTaskForm, self).__init__(*args, **kwargs)
        if self.instance.id:
            config = self.instance.config
            queue = config.get('queue')
            if queue:
                self.initial['queue'] = models.SystemScheduleQueue.objects.get(code=queue)
            self.initial['script'] = config.get('script')
            self.initial['include_meta'] = config.get('include_meta')
            custom_program = config.get('custom_program')
            if custom_program:
                self.initial['custom_program'] = [
                    InitialFileStr(custom_program.get('executable', '').replace(self.executable_path, '')),
                    custom_program.get('args'),
                    custom_program.get('docker_image'),
                    custom_program.get('run_in_docker', False),
                ]
            sql_config = config.get('sql_config')
            if sql_config:
                self.initial['sql_config'] = [
                    sql_config.get('host'),
                    sql_config.get('port'),
                    sql_config.get('database'),
                    sql_config.get('user'),
                    sql_config.get('password'),
                ]

    def clean(self):
        cleaned_data = super(SystemTaskForm, self).clean()
        if self.errors:
            return None
        parent = cleaned_data.get('parent')
        required_fields = parent.config.get('required_fields', []) if parent else []
        config = cleaned_data.setdefault('config', {})
        if not config:
            config = cleaned_data['config'] = {}
        for field in required_fields:
            value = cleaned_data.pop(field, None) or config.pop(field, None)
            if not value:
                self.add_error('name', '%s不能为空' % field)
                break
            if field == 'queue':
                config[field] = value.code
            elif field == 'sql_config':
                host, port, database, user, password = value
                if host:
                    config[field] = {
                        'host': host,
                        'port': port,
                        'database': database,
                        'user': user,
                        'password': password,
                    }
            elif field == 'custom_program':
                bytesio, args, docker_image, run_in_docker = value
                if not bytesio:
                    custom_program = config.pop(field, None)
                    if not custom_program or not custom_program.get('executable'):
                        self.add_error('custom_program', '自定义程序不能为空')
                    else:
                        config[field] = {
                            'executable': custom_program.get('executable'),
                            'args': args,
                            'docker_image': docker_image,
                            'run_in_docker': run_in_docker,
                        }
                    break
                max_size = parent.config.get('max_size', 5 * 1024 * 1024)
                bytesio, args, docker_image, run_in_docker = value
                if bytesio.size > max_size:
                    self.add_error('custom_program', '文件大小不能超过%sM' % round(max_size / 1024 / 1024))
                    break
                path = os.path.join(self.executable_path, get_md5(cleaned_data['name']))
                if not os.path.exists(path):
                    os.makedirs(path)
                file = os.path.join(path, 'main%s' % os.path.splitext(bytesio.name)[-1])
                with open(file, 'wb') as f:
                    trunk = bytesio.read(bytesio.DEFAULT_CHUNK_SIZE)
                    while trunk:
                        f.write(trunk)
                        trunk = bytesio.read(bytesio.DEFAULT_CHUNK_SIZE)
                config[field] = {
                    'executable': file,
                    'args': args,
                    'docker_image': docker_image,
                    'run_in_docker': run_in_docker,
                }
            else:
                config[field] = value
        return cleaned_data

    class Meta:
        model = models.SystemTask
        fields = '__all__'


class SystemScheduleQueueForm(generic_forms.TaskScheduleQueueForm):

    class Meta(generic_forms.TaskScheduleQueueForm.Meta):
        model = models.SystemScheduleQueue


class SystemScheduleProducerForm(generic_forms.TaskScheduleProducerForm):

    class Meta(generic_forms.TaskScheduleProducerForm.Meta):
        model = models.SystemScheduleProducer
