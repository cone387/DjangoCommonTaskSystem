import socket
from urllib.request import urlopen


# 获取内网IP
def get_intranet_ip():
    return socket.gethostbyname(socket.gethostname())


# 获取外网IP
def get_internet_ip():
    request = urlopen('https://checkip.amazonaws.com/')
    ip = request.read().decode('utf8').strip()
    request.close()
    return ip
