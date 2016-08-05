from Tcp2Ssh import *
import optparse
from base64 import b64encode, b64decode


def parse_args():
    usage = """usage: %prog listen_port
    """
    parser = optparse.OptionParser(usage)
    values, args = parser.parse_args()
    return args


"""
This module L{Http2SshConnector} connects two sockets of protocol HTTP and SSH.
It acts as an HTTP Server, and an SSH Client. It is designed to be asynchronous,
and so all sockets are non-blocking.

Upon a client connection, the server expects a request with the body 'auth' and
headers containing authentication information. Should look like this:
------------------
GET / HTTP/1.1
username: W
password: X
host: Y
port: Z

auth


------------------
With two empty lines at the ends of the data.
Username+password allow logging into the host at the port specified

The server responds with 200 OK and data.
Note: There may be multiple responses to one request!

"""


class Http2SshConnector(Tcp2SshConnector):
    """
    HTTP Server and SSH Client
    """
    def __init__(self, listen_addr):
        super(Http2SshConnector, self).__init__(listen_addr)

    def recv_send(self, sock, other_sock, data):
        """
        :param sock: socket where data is incoming
        :param other_sock: socket to write to
        :param data: the data read from sock, to write to other_sock

        :return: returns nothing
        """
        if self.get_direction(sock) == Dir.A:
            # Incoming HTTP request
            _, _, _, data = self.parse_http_request(data)
            other_sock.send(data)
        elif self.get_direction(sock) == Dir.B:
            # incoming data from ssh connection
            self.socket_send(other_sock, self.build_http_response(data))

    @staticmethod
    def build_http_response(data, status="200 OK"):
        """
        creates an HTTP response with the data in the response
        :param data: the data read from sock, to write to other_sock

        :return: returns a string of the response
        """
        return status + "\r\n\r\n" +\
               b64encode(data) + \
               "\r\n\r\n\r\n"

    @staticmethod
    def parse_http_request(request):
        """
        :param request: the string request
        :return: from the request, the username, password and address to connect to using SSH
        as well as the data in the body of the request
        """
        try:
            lines = request.split("\r\n")
            username = get_value(lines[1])
            password = get_value(lines[2])
            dest_addr = (get_value(lines[3]), int(get_value(lines[4])))
            body = b64decode("".join(lines[lines.index(''):]))
        except Exception,e:
            # error trying to parse
            pass
        return username, password, dest_addr, body

    def get_metadata(self, sock):
        """
        metadata is the connection data for the SSH connection. The authentication details and the address
        it is expected to be send in the first request from the HTTP client
        :param sock: http client to read from
        :return: the connection metadata
        """
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
