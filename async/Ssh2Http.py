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
            other_sock.send(self.build_http_request(data))
        elif self.get_direction(sock) == Dir.B:
            other_sock.send(self.parse_http_response(data))

    @staticmethod
    def build_http_request(data, username='NaN', password='Nan'):
        # '192.168.179.128'
        return "GET / HTTP/1.1\r\n" \
               "username:" + b64encode(username) + "\r\n" +\
               "password:" + b64encode(password) + "\r\n" + \
               "host:" + b64encode('127.0.0.1') + "\r\n" +\
               "port:" + b64encode('22') + "\r\n" +\
               "\r\n" + \
               b64encode(data)

    @staticmethod
    def parse_http_response(data):
        lines = data.split("\r\n")
        return b64decode("".join(lines[lines.index(''):]))

    def connect_to_server(self, dest_addr, username, password):
        new_tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        new_tcp_socket.connect(dest_addr)
        new_tcp_socket.setblocking(0)
        auth_data = self.build_http_request("auth", username, password)
        new_tcp_socket.sendall(auth_data)
        return new_tcp_socket


def main():
    listen_port, dest_host, dest_port = parse_args()
    #listen_port, dest_host, dest_port = (5022, '127.0.0.1', '5080')
    dest_port = int(dest_port)
    listen_port = int(listen_port)
    connector = Ssh2HttpConnector(('0.0.0.0', listen_port), (dest_host, dest_port))
    connector.forward_packets()


if __name__ == '__main__':
    main()
