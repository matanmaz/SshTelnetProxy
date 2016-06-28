from __builtin__ import super

from twisted.internet.protocol import Protocol, ServerFactory, ClientFactory, connectionDone
from twisted.internet import reactor


class MitmServerProtocol(Protocol):
    def dataReceived(self, data):
        self.factory.write(data)


class MitmServerFactory(ServerFactory):
    protocol = MitmServerProtocol

    def __init__(self, c_port):
        self.c_port = c_port

    def buildProtocol(self, addr):
        d_host = '192.168.192.1'
        d_port = self.get_d_port(self.c_port)
        protocol = ServerFactory.buildProtocol(self, addr)
        factory = MitmClientFactory(protocol)
        self.b_side = reactor.connectTCP(d_host, d_port, factory)
        return protocol

    @staticmethod
    def get_d_port(c_port):
        return c_port * 10

    def write(self, data):
        self.b_side.transport.write(data)


class MitmClientProtocol(Protocol):
    def dataReceived(self, data):
        self.factory.write(data)


class MitmClientFactory(ClientFactory):
    protocol = MitmClientProtocol
    def __init__(self, a_side):
        self.a_side = a_side

    def write(self, data):
        self.a_side.transport.write(data)


def main():
    c_port = 5001
    factory = MitmServerFactory(c_port)
    reactor.listenTCP(c_port, factory)
    reactor.run()


if __name__ == "__main__":
    main()
