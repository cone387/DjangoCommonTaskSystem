import asyncio

#
# async def send_message(message):
#     reader, writer = await asyncio.open_connection('127.0.0.1', 8888)
#     print(f'Send: {message}')
#     writer.write(message.encode())
#     await writer.drain()
#     try:
#         text = await asyncio.wait_for(reader.read(), timeout=30)
#         print("Received:", text.decode())
#     except asyncio.TimeoutError:
#         print('client timeout ')
#
#     writer.close()
#
#
# asyncio.run(send_message('Hello World!\r\n\r\n'))

import socket

def send_message(message):
    # 创建一个 socket 对象
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # 连接到服务器
    client_socket.connect(('127.0.0.1', 8888))

    print(f'Send: {message}')
    client_socket.send(message.encode())

    # 接收服务器的响应
    response = client_socket.recv(4096)
    print("Received:", response.decode())

    # 关闭连接
    client_socket.close()

# 发送消息
send_message('Hello World!\r\n\r\n')

