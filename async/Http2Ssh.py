from Tcp2Ssh import *
import optparse
from base64 import b64encode, b64decode


def parse_args():
    usage = """usage: %prog listen_port
    """
    parser = optparse.OptionParser(usage)
    values, args = parser.parse_args()
    return args


class Http2SshConnector(Tcp2SshConnector):
    def __init__(self, listen_addr):
        super(Http2SshConnector, self).__init__(listen_addr)

    def recv_send(self, sock, other_sock, data):
        if self.get_direction(sock) == Dir.A:
            # Incoming HTTP request
            _, _, _, data = self.parse_http_request(data)
            other_sock.send(data)
        elif self.get_direction(sock) == Dir.B:
            # incoming data from ssh connection
            other_sock.send(self.build_http_response(data))

    @staticmethod
    def build_http_response(data):
        return "200 OK\r\n\r\n" +\
               b64encode(data) + \
               "\r\n\r\n\r\n"

    @staticmethod
    def parse_http_request(data):
        lines = data.split("\r\n")
        username = get_value(lines[1])
        if username != 'N/A':
            password = get_value(lines[2])
            dest_addr = (get_value(lines[3]), int(get_value(lines[4])))
        else:
            password = 'N/A'
            dest_addr = ('N/A', 0)
        body = b64decode("".join(lines[lines.index(''):]))
        return username, password, dest_addr, body

    def get_metadata(self, sock):
        buff = Connector.read_no_block(sock)
        if not buff:
            # we tried reading username and such but nothing was there
            print 'error reading metadata'
        username, password, dest_addr, body = self.parse_http_request(buff)
        return dest_addr, username, password


def main():
    # listen_port = parse_args()[0]
    # listen_port = int(listen_port)
    listen_port = 5080
    connector = Http2SshConnector(('0.0.0.0', listen_port))
    connector.forward_packets()


if __name__ == '__main__':
    main()
