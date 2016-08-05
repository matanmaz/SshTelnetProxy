from Ssh2Tcp import *
import optparse
from base64 import b64encode, b64decode


def parse_args():
    usage = """usage: %prog listen_port dest_host dest_port
    """
    parser = optparse.OptionParser(usage)
    values, args = parser.parse_args()
    return args


class Ssh2HttpConnector(Ssh2TcpConnector):
    def __init__(self, listen_addr, dest_addr):
        super(Ssh2HttpConnector, self).__init__(listen_addr, dest_addr)

    def recv_send(self, sock, other_sock, data):
        if self.get_direction(sock) == Dir.A:
            self.socket_send(other_sock, self.build_http_request(data))
        elif self.get_direction(sock) == Dir.B:
            responses = data.split('\r\n\r\n\r\n')
            for response in responses:
                self.socket_send(other_sock, self.parse_http_response(response))

    def build_http_request(self, data):
        # '192.168.179.128'
        return "GET / HTTP/1.1\r\n" \
               "username:" + b64encode(self.username) + "\r\n" +\
               "password:" + b64encode(self.password) + "\r\n" + \
               "host:" + b64encode(self.server_addr[0]) + "\r\n" +\
               "port:" + b64encode(self.server_addr[1]) + "\r\n" +\
               "\r\n" + \
               b64encode(data) + \
               "\r\n\r\n\r\n"

    @staticmethod
    def parse_http_response(data):
        try:
            lines = data.split("\r\n")
            return b64decode("".join(lines[lines.index(''):]))
        except TypeError, t:
            print t
            raise

    def connect_to_server(self, dest_addr, ssh_side):
        self.server_addr = ssh_side.dest_addr
        self.username = ssh_side.username
        self.password = ssh_side.password
        new_tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        new_tcp_socket.connect(dest_addr)
        new_tcp_socket.setblocking(0)
        auth_data = self.build_http_request("auth")
        new_tcp_socket.sendall(auth_data)
        return new_tcp_socket


def main():
    #listen_port, dest_host, dest_port = parse_args()
    listen_port, dest_host, dest_port = (5022, '127.0.0.1', 5080)
    connector = Ssh2HttpConnector(('0.0.0.0', listen_port), (dest_host, dest_port))
    connector.forward_packets()


if __name__ == '__main__':
    main()
