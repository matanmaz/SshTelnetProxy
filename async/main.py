from select import select
import Connector

ssh_port = 5022
http_port = 5080

servers = []
clients = []
ssh2http = Connector.new_connector('ssh', 'http')
ssh2http.bind(ssh_port)
ssh2http.listen(100)

http2ssh = Connector.new_connector('http', 'ssh')
http2ssh.bind(http_port)
http2ssh.listen(100)

servers.append(http2ssh)
servers.append(ssh2http)
while servers:
    rlist, _, _ = select(servers + clients, [], [])

    for sock in rlist:
        if sock in servers:
            clients.append(sock.accept())
        else:
            buff = sock.recv()
            print sock
            print buff
