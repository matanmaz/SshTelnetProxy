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
from twisted.internet.endpoints import _WrappingFactory
from twisted.conch.endpoints import SSHCommandClientEndpoint
from twisted.conch.client.knownhosts import KnownHostsFile
from zope.interface import implements
import sys
import os
log.startLogging(sys.stderr)


class PermissiveKnownHosts(object):

    def verifyHostKey(self, ui, hostname, ip, key):
        return defer.succeed(1)


class FzTCP2SSHProtocol(protocol.Protocol):
    """
    """
    def connectionMade(self):
        script_dir = os.getcwd() #<-- absolute dir the script is in
        rel_path = "hostkeys"
        abs_file_path = os.path.join(script_dir, rel_path)
        knownHosts = KnownHostsFile.fromPath(abs_file_path)
        self.point = SSHCommandClientEndpoint.newConnection(reactor, 'cmd', 'user', '127.0.0.1', port=5122, password='password', knownHosts=knownHosts)
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
        print '****FzTCP2SSHProtocol.dataReceived'
        self.sshSide.sendMessage(data)

    def sendMessage(self, msg):
        print '****FzTCP2SSHProtocol.sendMessage'
        self.transport.write(msg)
        
        
class FzSSHClient(protocol.Protocol):
    def connectionMade(self):
        self._init = True
        
    def sendMessage(self, msg):
        print '****FzSSHClient.sendMessage'
        self.transport.write(msg)

    def dataReceived(self, data):
        print '****FzSSHClient.dataReceived'
        self.tcpSide.sendMessage(data)

    def loseConnection(self, reason):
        print '****FzSSHClient.loseConnection'
        self.transport.loseConnection()

def main():
    """This runs the protocol on port 8000"""
    factory = protocol.ServerFactory()
    factory.protocol = FzTCP2SSHProtocol
    reactor.listenTCP(5080,factory)
    reactor.run()

# this only runs if the module was *not* imported
if __name__ == '__main__':
    main()