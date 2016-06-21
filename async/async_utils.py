import socket
import errno

def is_socket_closed(sock):
    try:
        sock.fileno()
    except:
        return True
    return False

def read_no_block(sock, other_sock):
    buff = ''
    while True:
        try:
            new_data = sock.recv(1024)
            other_sock.send(new_data)
        except socket.error, e:
            if type(e) == socket.timeout or e.args[0] == errno.EWOULDBLOCK:
                break
            if e.errno == errno.EBADF or \
                            e.errno == errno.WSAECONNABORTED or \
                            e.args[0] == errno.WSAECONNRESET or \
                            e.message=='Socket is closed':
                return False
            import ipdb
            ipdb.set_trace()
            print e.errno
            print e
            raise
        if not new_data:
            break
    return True


def clean_sockets(sockets):
    return filter(lambda x: not is_socket_closed(x), sockets)