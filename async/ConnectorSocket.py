import socket


class ConnectorSocket(socket.socket):
    def __init__(self):
        self.is_server = True
        self.server_sock = None

    def __init__(self, new_a_sock, block_side):
        self.is_server = False
        self.block_side = block_side
        self.a_sock = new_a_sock
        if self.block_side == 'A':
            self.a_sock.setblocking(0)
        dest_addr = self.a_sock.recv().split(':')
        dest_addr[1] = int(dest_addr[1])
        self.b_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if self.block_side == 'B':
            self.b_sock.setblocking(0)
        self.b_sock.connect(dest_addr)

    def bind(self, address):
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setblocking(0)
        return self.server_sock.bind(address)

    def accept(self):
        new_a_sock = self.server_sock.accept()
        return self.__init__(new_a_sock)

    def connect(self, address):
        raise NotImplementedError

    def fileno(self):
        if self.is_server:
            return self.server_sock.fileno()
        elif self.block_side == 'A':
            return self.b_sock.fileno()
        else:
            return self.a_sock.fileno()

    def listen(self, backlog):
        self.server_sock.listen(backlog)

    def recv(self):
        if self.block_side == 'A':
            buff = self.read_no_block(self.b_sock)
            self.a_sock.send(buff)
        else:
            buff = self.read_no_block(self.a_sock)
            self.b_sock.send(buff)
        return buff

    def send(self, buff):
        pass

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
