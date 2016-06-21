import socket
import optparse
import paramiko
import select
import errno
from demo_server import SimpleSSHServer
import sys
import traceback
from async_utils import *

def parse_args():
    usage = """usage: %prog listen_port dest_host dest_port
    """
    parser = optparse.OptionParser(usage)

    values, args = parser.parse_args()

    return args


def get_ssh_socket(dest_host, dest_port):
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

def serve_ssh_client(ssh_client_socket):
    t = paramiko.Transport(ssh_client_socket)
    try:
        t.load_server_moduli()
    except:
        print('(Failed to load moduli -- gex will be unsupported.)')
        raise
    host_key = paramiko.RSAKey(filename=r"C:\Users\frisbee\Documents\GitHub\SshTelnetProxy\ssh-keys\ssh_host_rsa_key")
    t.add_server_key(host_key)
    server = SimpleSSHServer()
    try:
        t.start_server(server=server)
    except paramiko.SSHException:
        print('*** SSH negotiation failed.')
        sys.exit(1)
    return t, server


def start_ssh_session(ssh_tranport, ssh_server):
    chan = ssh_tranport.accept(20)
    if chan is None:
        print('*** No channel.')
        sys.exit(1)
    print('Authenticated!')

    ssh_server.event.wait(10)
    if not ssh_server.event.is_set():
        print('*** Client never asked for a shell.')
        sys.exit(1)
    return chan


def lookup_other_sock(sock):
    global lookup_map
    if lookup_map.has_key(sock):
        return lookup_map[sock]
    else:
        return None


def forward_packets(server_socket, dest_host, dest_port):
    global lookup_map
    sockets = [server_socket]
    authenticating_sockets = []

    while server_socket:
        try:
            rlist, wlist, xlist = select.select(sockets, [], [])
        except:
            print 'error on select'
            sockets = clean_sockets(sockets)
            continue

        for sock in rlist:
            if sock == server_socket:
                new_client_socket, _ = server_socket.accept()
                new_client_socket.setblocking(0)
                new_transport, new_ssh_server = serve_ssh_client(new_client_socket)
                authenticating_sockets.append(new_client_socket)
                sockets.append(new_client_socket)
                lookup_map[new_client_socket] = new_transport
                lookup_map[new_transport] = new_ssh_server

            elif sock in authenticating_sockets:
                ssh_transport = lookup_map[sock]
                if ssh_transport.authenticated:
                    ssh_server = lookup_map[ssh_transport]
                    authenticating_sockets.remove(sock)
                    sockets.remove(sock)
                    lookup_map.pop(sock)
                    lookup_map.pop(ssh_transport)
                    new_ssh_socket = start_ssh_session(ssh_transport, ssh_server)
                    new_ssh_socket.setblocking(0)
                    new_tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    new_tcp_socket.connect((dest_host, dest_port))
                    new_tcp_socket.setblocking(0)
                    lookup_map[new_tcp_socket] = new_ssh_socket
                    lookup_map[new_ssh_socket] = new_tcp_socket
                    sockets.append(new_tcp_socket)
                    sockets.append(new_ssh_socket)
            else:
                other_sock = lookup_other_sock(sock)
                if not read_no_block(sock, lookup_other_sock(sock)):
                    try:
                        sockets.remove(sock)
                        sockets.remove(other_sock)
                        other_sock.close()
                        sock.close()
                    except:
                        # sockets have already been removed due to symmetry
                        pass


def main():
    global lookup_map
    listen_port, dest_host, dest_port = parse_args()
    dest_port = int(dest_port)
    listen_port = int(listen_port)
    ssh_client_socket = get_ssh_socket('127.0.0.1', listen_port)
    lookup_map = {}
    forward_packets(ssh_client_socket, dest_host, dest_port)


if __name__ == '__main__':
    main()
