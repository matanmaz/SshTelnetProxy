import socket
import optparse
import paramiko
import select
import errno


def parse_args():
    usage = """usage: %prog listen_port dest_host dest_port
    """
    parser = optparse.OptionParser(usage)

    values, args = parser.parse_args()

    return args


def get_ssh_socket(dest_host, dest_port):
    ssh_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    ssh_socket.connect((dest_host, dest_port))
    ssh_socket.setblocking(0)
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh_client.connect(None, sock=ssh_socket, username='user', password='password')
    return ssh_client


def get_tcp_socket(listen_addr):
    tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_socket.bind(listen_addr)
    tcp_socket.listen(5)
    return tcp_socket


def lookup_other_sock(sock):
    global lookup_map
    return lookup_map[sock]


def forward_packets(server_socket, client_socket):
    global lookup_map
    sockets = [server_socket]

    while server_socket and client_socket:
        rlist, wlist, _ = select.select(sockets, [], [])

        for sock in rlist:
            if sock == server_socket:
                new_tcp_socket, _ = server_socket.accept()
                new_tcp_socket.setblocking(0)
                new_ssh_socket = client_socket.invoke_shell()
                new_ssh_socket.setblocking(0)
                lookup_map[new_tcp_socket] = new_ssh_socket
                lookup_map[new_ssh_socket] = new_tcp_socket
                sockets.append(new_tcp_socket)
                sockets.append(new_ssh_socket)
            else:
                read_no_block(sock, lookup_other_sock(sock))


def read_no_block(sock, other_sock):
    buff = ''
    while True:
        try:
            new_data = sock.recv(1024)
            other_sock.send(new_data)
        except socket.error, e:
            if type(e) == socket.timeout or e.args[0] == errno.EWOULDBLOCK:
                break
            raise
        if not new_data:
            break
        buff += new_data
    return buff


def write_no_block(sock, buff):
    total_sent = 0
    while total_sent<len(buff):
        try:
            sent = sock.send(buff[total_sent:])
            print sock
            print "write:" + buff[total_sent:total_sent+sent]
            total_sent += sent
        except socket.error, e:
            if type(e) == socket.timeout or e.args[0] == errno.EWOULDBLOCK:
                total_sent += sent
                break
            raise
    return buff[total_sent:]



def main():
    global lookup_map
    listen_port, dest_host, dest_port = parse_args()
    dest_port = int(dest_port)
    listen_port = int(listen_port)
    tcp_server_socket = get_tcp_socket(('127.0.0.1',listen_port))
    ssh_client_socket = get_ssh_socket(dest_host, dest_port)
    lookup_map = {}
    forward_packets(tcp_server_socket, ssh_client_socket)


if __name__ == '__main__':
    main()
