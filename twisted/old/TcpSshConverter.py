#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.
from twisted.cred import portal
from twisted.cred.checkers import InMemoryUsernamePasswordDatabaseDontUse
from twisted.conch import avatar
from twisted.conch.checkers import SSHPublicKeyChecker, InMemorySSHKeyDB
from twisted.conch.ssh import factory, userauth, connection, keys, session
from twisted.conch.ssh.transport import SSHServerTransport
from twisted.internet import reactor, protocol
from twisted.python import log
from twisted.python import components
from twisted.internet.endpoints import TCP4ClientEndpoint, connectProtocol
from twisted.web.client import Agent
from twisted.web.http_headers import Headers
from twisted.internet import defer
from twisted.internet import error
from twisted.conch.endpoints import SSHCommandClientEndpoint
from twisted.conch.client.knownhosts import KnownHostsFile
from zope.interface import implements
import sys
import os
log.startLogging(sys.stderr)


def tohex(x):
    return "".join([hex(ord(c))[2:].zfill(2) for c in x])


class PermissiveKnownHosts(object):

    def verifyHostKey(self, ui, hostname, ip, key):
        return defer.succeed(1)


class FzTCP2SSHProtocol(protocol.Protocol):
    """
    """
    def connectionMade(self):
        script_dir = os.getcwd()
        rel_path = "hostkeys"
        abs_file_path = os.path.join(script_dir, rel_path)
        knownHosts = KnownHostsFile.fromPath(abs_file_path)
        self.point = SSHCommandClientEndpoint.newConnection(reactor, 'cmd', 'user', '127.0.0.1', port=5122,
                                                            password='password', knownHosts=PermissiveKnownHosts())
        self.sshSide = FzSSHClient()
        self.sshSide.tcpSide = self
        connectProtocol(self.point, self.sshSide)
        

    def connectionLost(self, reason):
        print '****FzTCP2SSHProtocol.connectionLost'
        self.sshSide.loseConnection(reason)
        
    def dataReceived(self, data):
        """
        Called when client send data over the shell session.

        Just echo the received data and and if Ctrl+C is received, close the
        session.
        """
        print '****FzTCP2SSHProtocol.dataReceived {}'.format(tohex(data))
        if data == '\r':
            data = '\r\n'
        if data == '\x03':  # ^C
            self.transport.loseConnection()
            return
        self.transport.write(data)
        self.sshSide.sendMessage(data)

    def sendMessage(self, msg):
        print '****FzTCP2SSHProtocol.sendMessage {}'.format(tohex(msg))
        self.transport.write(msg)

    def loseConnection(self, reason):
        print '****FzTCP2SSHProtocol.loseConnection {}'.format(reason)
        self.transport.loseConnection()
        
        
class FzSSHClient(protocol.Protocol):
    def connectionMade(self):
        self._init = True
        
    def sendMessage(self, msg):
        print '****FzSSHClient.sendMessage {}'.format(tohex(msg))
        self.transport.write(msg)

    def dataReceived(self, data):
        print '****FzSSHClient.dataReceived {}'.format(tohex(data))
        self.tcpSide.sendMessage(data)

    def loseConnection(self, reason):
        print '****FzTCPClient.loseConnection {}'.format(reason)
        self.transport.loseConnection()

    def connectionLost(self, reason=error.ConnectionDone()):
        print '****FzTCPClient.connectionLost {}'.format(reason)
        self.tcpSide.loseConnection(reason)

def main():
    factory = protocol.ServerFactory()
    factory.protocol = FzTCP2SSHProtocol
    reactor.listenTCP(5080,factory)
    reactor.run()

# this only runs if the module was *not* imported
if __name__ == '__main__':
    main()