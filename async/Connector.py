import select
from async_utils import *
from enum import Enum
import errno


Dir = Enum('Dir', 'A B')


class Connector(object):
    def __init__(self, listen_addr, dest_addr=None):
        self.lookup_map = {}
        self.direction_map = {}
        self.listen_addr = listen_addr
        self.dest_addr = dest_addr
        self.listen_addr = listen_addr[0]
        self.listen_port = listen_addr[1]
        self.sockets = []
        self.server_socket = None
        self.A = 1 # server side
        self.B = 2 # client side

    def lookup(self, sock):
        if self.lookup_map.has_key(sock):
            return self.lookup_map[sock]
        else:
            return None

    def append_lookup(self, sock, other_sock):
        self.lookup_map[sock] = other_sock

    def get_direction(self, sock):
        return self.direction_map[sock]

    def set_direction(self, sock, direction):
        self.direction_map[sock] = direction

    @staticmethod
    def get_server_socket(listen_host, listen_port):
        raise NotImplementedError

    def socket_read(self, sock):
        raise NotImplementedError

    def forward_packets(self):
        self.server_socket = self.__class__.get_server_socket(self.listen_addr, self.listen_port)
        self.sockets.append(self.server_socket)

        while self.server_socket:
            self.sockets = clean_sockets(self.sockets)
            try:
                rlist, _, _ = select.select(self.sockets, [], [])
            except:
                print 'error on select'
                self.sockets = clean_sockets(self.sockets)
                continue

            for sock in rlist:
                self.socket_read(sock)

    @staticmethod
    def read_no_block(sock):
        buff = ''
        while True:
            try:
                new_data = ''
                new_data = sock.recv(1024)
            except socket.error, e:
                if type(e) == socket.timeout or e.args[0] == errno.EWOULDBLOCK:
                    buff += new_data
                    return buff
                if e.errno == errno.EBADF or \
                                e.errno == errno.WSAECONNABORTED or \
                                e.args[0] == errno.WSAECONNRESET or \
                                e.message == 'Socket is closed':
                    return False
                print e.errno
                print e
                raise
            if not new_data:
                return False
            buff += new_data
        return buff

    def recv_send(self, sock, other_sock, data):
        other_sock.sendall(data)
        return data
