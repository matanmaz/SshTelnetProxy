from Tcp2Ssh import *
import optparse
from base64 import b64encode, b64decode
import async_utils

def parse_args():
    usage = """usage: %prog listen_port dest_host dest_port
    """
    parser = optparse.OptionParser(usage)
    values, args = parser.parse_args()
    return args


class Http2SshConnector(Tcp2SshConnector):
    def __init__(self, listen_addr, dest_addr):
        super(Http2SshConnector, self).__init__(listen_addr, dest_addr)

    def recv_send(self, sock, other_sock, data):
        if self.get_direction(sock) == Dir.A:
            _, _, data = self.parse_http_request(data)
            other_sock.send(data)
        elif self.get_direction(sock) == Dir.B:
            other_sock.send(self.build_http_response(data))

    def build_http_response(self, data):
        return "200 OK\r\n\r\n" +\
               b64encode(data)

    def parse_http_request(self, data):
        lines = data.split("\r\n")
        username = get_value(lines[1])
        password = get_value(lines[2])
        body = b64decode("".join(lines[lines.index(''):]))
        return username, password, body

    def accept_client(self):
        new_tcp_socket, _ = self.server_socket.accept()
        new_tcp_socket.setblocking(0)
        buff = self.read_no_block(new_tcp_socket)
        username, password, body = self.parse_http_request(buff)
        return new_tcp_socket, username, password

def main():
    listen_port, dest_host, dest_port = parse_args()
    dest_port = int(dest_port)
    listen_port = int(listen_port)
    connector = Http2SshConnector(('127.0.0.1', listen_port), (dest_host, dest_port))
    connector.forward_packets()


if __name__ == '__main__':
    main()