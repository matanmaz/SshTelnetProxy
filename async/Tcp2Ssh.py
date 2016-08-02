import optparse
import paramiko
from Connector import *


def parse_args():
    usage = """usage: %prog listen_port
    """
    parser = optparse.OptionParser(usage)
    values, args = parser.parse_args()
    return args


class Tcp2SshConnector(Connector):
    def __init__(self, listen_addr):
        super(Tcp2SshConnector, self).__init__(listen_addr)
        self.clients = []

    @staticmethod
    def get_ssh_socket(dest_addr, username, password):
        ssh_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ssh_socket.connect(dest_addr)
        ssh_socket.setblocking(0)
        ssh_client = paramiko.SSHClient()
        # TODO change autoadd to appropriate policy
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_client.connect(None, sock=ssh_socket, username=username, password=password)
        ssh_channel = ssh_client.invoke_shell()
        ssh_channel.setblocking(0)
        return ssh_channel, ssh_client

    @staticmethod
    def get_server_socket(listen_host, listen_port):
        tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_socket.bind((listen_host, listen_port))
        tcp_socket.listen(5)
        return tcp_socket

    def accept_client(self):
        new_tcp_socket, _ = self.server_socket.accept()
        new_tcp_socket.setblocking(0)
        return new_tcp_socket

    def get_metadata(self, sock):
        raise NotImplementedError

    def socket_read(self, sock):
        if sock == self.server_socket:
            # new tcp connection incoming
            new_tcp_socket = self.accept_client()
            self.sockets.append(new_tcp_socket)
            self.set_direction(new_tcp_socket, Dir.A)
            # not yet authenticated
        else:
            other_sock = self.lookup(sock)
            if other_sock is None:
                # recv authentication info and connect to ssh
                new_tcp_socket = sock
                dest_addr, username, password = self.get_metadata(sock)
                new_ssh_socket, new_ssh_client = self.get_ssh_socket(dest_addr, username, password)
                self.clients.append(new_ssh_client)
                self.lookup_map[new_tcp_socket] = new_ssh_socket
                self.lookup_map[new_ssh_socket] = new_tcp_socket
                self.sockets.append(new_ssh_socket)
                self.set_direction(new_ssh_socket, Dir.B)
            else:
                # already authenticated
                buff = Connector.read_no_block(sock)
                if buff:  # read successful
                    self.recv_send(sock, other_sock, buff)
                else:  # socket closed
                    try:
                        # clean up socket lists from this socket pair
                        self.sockets.remove(sock)
                        self.sockets.remove(other_sock)
                        other_sock.close()
                        sock.close()
                    except ValueError:
                        # sockets have already been removed due to symmetry
                        pass


def main():
    listen_port = parse_args()
    listen_port = int(listen_port)
    connector = Tcp2SshConnector(('127.0.0.1', listen_port))
    connector.forward_packets()


if __name__ == '__main__':
    main()
