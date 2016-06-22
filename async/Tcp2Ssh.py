import optparse
import paramiko
from Connector import *


def parse_args():
    usage = """usage: %prog listen_port dest_host dest_port
    """
    parser = optparse.OptionParser(usage)
    values, args = parser.parse_args()
    return args


class Tcp2SshConnector(Connector):
    def __init__(self, listen_addr, dest_addr):
        super(Tcp2SshConnector, self).__init__(listen_addr, dest_addr)

    def get_ssh_socket(self, dest_addr, username, password):
        ssh_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ssh_socket.connect(dest_addr)
        ssh_socket.setblocking(0)
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_client.connect(None, sock=ssh_socket, username=username, password=password)
        return ssh_client

    @classmethod
    def get_server_socket(cls, listen_host, listen_port):
        tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_socket.bind((listen_host, listen_port))
        tcp_socket.listen(5)
        return tcp_socket

    def accept_client(self):
        new_tcp_socket, _ = self.server_socket.accept()
        new_tcp_socket.setblocking(0)
        return new_tcp_socket, "vyos", "vyos"

    def socket_read(self, sock):
        if sock == self.server_socket:
            new_tcp_socket, username, password = self.accept_client()
            new_ssh_client = self.get_ssh_socket(self.dest_addr, username, password)
            new_ssh_socket = new_ssh_client.invoke_shell()
            print new_ssh_socket
            new_ssh_socket.setblocking(0)
            self.lookup_map[new_tcp_socket] = new_ssh_socket
            self.lookup_map[new_ssh_socket] = new_tcp_socket
            self.sockets.append(new_tcp_socket)
            self.sockets.append(new_ssh_socket)
            self.set_direction(new_tcp_socket, Dir.A)
            self.set_direction(new_ssh_socket, Dir.B)
        else:
            other_sock = self.lookup(sock)
            buff = self.read_no_block(sock)
            print "buff: " + buff
            import ipdb
            ipdb.set_trace()
            if buff:  # read until block successful
                self.recv_send(sock, other_sock, buff)
            else:  # socket closed
                try:
                    self.sockets.remove(sock)
                    self.sockets.remove(other_sock)
                    other_sock.close()
                    sock.close()
                except:
                    #sockets have already been removed due to symmetry
                    pass


def main():
    listen_port, dest_host, dest_port = parse_args()
    dest_port = int(dest_port)
    listen_port = int(listen_port)
    connector = Tcp2SshConnector(('127.0.0.1', listen_port), (dest_host, dest_port))
    connector.forward_packets()


if __name__ == '__main__':
    main()
