import socket
from base64 import b64decode


def is_socket_closed(sock):
    try:
        sock.fileno()
    except socket.error:
        return True
    return False


def basic_recv_send(sock, other_sock):
    new_data = sock.recv(1024)
    other_sock.send(new_data)
    return new_data


def clean_sockets(sockets):
    return filter(lambda x: not is_socket_closed(x), sockets)


def get_value(s):
    return b64decode(s[s.find(":"):])