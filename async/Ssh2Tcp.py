import optparse
import paramiko
from enum import Enum
from demo_server import SimpleSSHServer
import sys
import traceback
from async_utils import *
from Connector import Connector

Dir = Enum('Dir', 'A B AUTH')


def parse_args():
    usage = """usage: %prog listen_port dest_host dest_port
    """
    parser = optparse.OptionParser(usage)
    values, args = parser.parse_args()
    return args


class Ssh2TcpConnector(Connector):
    def __init__(self, listen_addr, dest_addr):
        super(Ssh2TcpConnector, self).__init__(listen_addr, dest_addr)
        self.host_key = paramiko.RSAKey(
            filename=r"C:\Users\frisbee\Documents\GitHub\SshTelnetProxy\ssh-keys\ssh_host_rsa_key")
        self.authenticating_sockets = []
        self.AUTH = 3

    @staticmethod
    def get_server_socket(dest_host, dest_port):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((dest_host, dest_port))
        except Exception as e:
            print('*** Bind failed: ' + str(e))
            traceback.print_exc()
            sys.exit(1)
        try:
            sock.listen(100)
        except Exception as e:
            print('*** Listen/accept failed: ' + str(e))
            traceback.print_exc()
            sys.exit(1)
        return sock

    def serve_ssh_client(self, ssh_client_socket):
        t = paramiko.Transport(ssh_client_socket)
        try:
            t.load_server_moduli()
        except:
            print('(Failed to load moduli -- gex will be unsupported.)')
            raise

        t.add_server_key(self.host_key)
        server = SimpleSSHServer(self)
        try:
            t.start_server(server=server)
        except paramiko.SSHException:
            print('*** SSH negotiation failed.')
            sys.exit(1)
        return t, server

    @staticmethod
    def start_ssh_session(ssh_transport, ssh_server):
        chan = ssh_transport.accept(20)
        if chan is None:
            print('*** No channel.')
            sys.exit(1)
        ssh_server.event.wait(10)
        if not ssh_server.event.is_set():
            print('*** Client never asked for a shell.')
            sys.exit(1)
        return chan, ssh_server.username, ssh_server.password

    def connect_to_server(self, dest_addr, username, password):
        new_tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        new_tcp_socket.connect(dest_addr)
        new_tcp_socket.setblocking(0)
        return new_tcp_socket

    def socket_read(self, sock):
        if sock == self.server_socket:
            # new connection incoming, pass to authentication
            new_client_socket, _ = self.server_socket.accept()
            new_client_socket.setblocking(0)
            new_transport, new_ssh_server = self.serve_ssh_client(new_client_socket)
            self.authenticating_sockets.append(new_client_socket)
            self.sockets.append(new_client_socket)
            self.append_lookup(new_client_socket, new_transport)
            self.append_lookup(new_transport, new_ssh_server)
            self.set_direction(new_client_socket, Dir.AUTH)

        elif sock in self.authenticating_sockets:
            # authentication coming in, we check to see if it is done
            ssh_transport = self.lookup_map[sock]
            if ssh_transport.authenticated:
                """
                1. remove from authenticating list
                2. lookup ssh transport and server in order to get a socket
                3. remove those from the lookup for cleanup
                4. start ssh session and get the socket
                5. connect to server, the 'other' socket
                6. set up lookup map and socket list
                """
                # 1
                self.authenticating_sockets.remove(sock)
                self.sockets.remove(sock)
                # 2
                ssh_server = self.lookup(ssh_transport)
                # 3
                self.lookup_map.pop(sock)
                self.lookup_map.pop(ssh_transport)
                # 4
                new_ssh_socket, username, password = self.__class__.start_ssh_session(ssh_transport, ssh_server)
                new_ssh_socket.setblocking(0)
                # 5
                new_tcp_socket = self.connect_to_server(self.dest_addr, username, password)
                # 6
                self.set_direction(new_ssh_socket, Dir.A)
                self.set_direction(new_tcp_socket, Dir.B)
                self.append_lookup(new_tcp_socket, new_ssh_socket)
                self.append_lookup(new_ssh_socket, new_tcp_socket)
                self.sockets.append(new_tcp_socket)
                self.sockets.append(new_ssh_socket)
        else:
            # authenticated connections, we forward
            other_sock = self.lookup(sock)
            buff = Connector.read_no_block(sock)
            if buff:  # read until block successful
                self.recv_send(sock, other_sock, buff)
            else:  # socket closed
                try:
                    self.sockets.remove(sock)
                    self.sockets.remove(other_sock)
                    other_sock.close()
                    sock.close()
                except ValueError:
                    # sockets have already been removed due to symmetry
                    pass

    def recv_send(self, sock, other_sock, buff):
        other_sock.send(buff)
        return True


def main():
    listen_port, dest_host, dest_port = parse_args()
    dest_port = int(dest_port)
    listen_port = int(listen_port)
    connector = Ssh2TcpConnector(('127.0.0.1', listen_port), (dest_host, dest_port))
    connector.forward_packets()


if __name__ == '__main__':
    main()
