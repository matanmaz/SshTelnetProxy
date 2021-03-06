#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.
import ipdb

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
from zope.interface import implements
import telnetlib
import sys
log.startLogging(sys.stderr)

"""
Example of running a custom protocol as a shell session over an SSH channel.

Warning! This implementation is here to help you understand how Conch SSH
server works. You should not use this code in production.

Re-using a private key is dangerous, generate one.

For this example you can use:

$ ckeygen -t rsa -f ssh-keys/ssh_host_rsa_key
$ ckeygen -t rsa -f ssh-keys/client_rsa

Re-using DH primes and having such a short primes list is dangerous, generate
your own primes.

In this example the implemented SSH server identifies itself using an RSA host
key and authenticates clients using username "user" and password "password" or
using a SSH RSA key.

# Clean the previous server key as we should now have a new one
$ ssh-keygen -f ~/.ssh/known_hosts -R [localhost]:5022
# Connect with password
$ ssh -p 5022 -i ssh-keys/client_rsa user@localhost
# Connect with the SSH client key.
$ ssh -p 5022 -i ssh-keys/client_rsa user@localhost
"""

# Path to RSA SSH keys used by the server.
SERVER_RSA_PRIVATE = 'ssh-keys/ssh_host_rsa_key'
SERVER_RSA_PUBLIC = 'ssh-keys/ssh_host_rsa_key.pub'

# Path to RSA SSH keys accepted by the server.
CLIENT_RSA_PUBLIC = 'ssh-keys/client_rsa.pub'


# Pre-computed big prime numbers used in Diffie-Hellman Group Exchange as
# described in RFC4419.
# This is a short list with a single prime member and only for keys of size
# 1024 and 2048.
# You would need a list for each SSH key size that you plan to support in your
# server implementation.
# You can use OpenSSH ssh-keygen to generate these numbers.
# See the MODULI GENERATION section from the ssh-keygen man pages.
# See moduli man pages to find out more about the format used by the file
# generated using ssh-keygen.
# For Conch SSH server we only need the last 3 values:
# * size
# * generator
# * modulus
#
# The format required by the Conch SSH server is:
#
# {
#   size1: [(generator1, modulus1), (generator1, modulus2)],
#   size2: [(generator4, modulus3), (generator1, modulus4)],
# }
#
# twisted.conch.openssh_compat.primes.parseModuliFile provides a parser for
# reading OpenSSH moduli file.
#
# Warning! Don't use these numbers in production.
# Generate your own data.
# Avoid 1024 bit primes https://weakdh.org
#
PRIMES = {
    2048: [(2L, 24265446577633846575813468889658944748236936003103970778683933705240497295505367703330163384138799145013634794444597785054574812547990300691956176233759905976222978197624337271745471021764463536913188381724789737057413943758936963945487690939921001501857793275011598975080236860899147312097967655185795176036941141834185923290769258512343298744828216530595090471970401506268976911907264143910697166165795972459622410274890288999065530463691697692913935201628660686422182978481412651196163930383232742547281180277809475129220288755541335335798837173315854931040199943445285443708240639743407396610839820418936574217939L)],
    4096: [(2L, 889633836007296066695655481732069270550615298858522362356462966213994239650370532015908457586090329628589149803446849742862797136176274424808060302038380613106889959709419621954145635974564549892775660764058259799708313210328185716628794220535928019146593583870799700485371067763221569331286080322409646297706526831155237865417316423347898948704639476720848300063714856669054591377356454148165856508207919637875509861384449885655015865507939009502778968273879766962650318328175030623861285062331536562421699321671967257712201155508206384317725827233614202768771922547552398179887571989441353862786163421248709273143039795776049771538894478454203924099450796009937772259125621285287516787494652132525370682385152735699722849980820612370907638783461523042813880757771177423192559299945620284730833939896871200164312605489165789501830061187517738930123242873304901483476323853308396428713114053429620808491032573674192385488925866607192870249619437027459456991431298313382204980988971292641217854130156830941801474940667736066881036980286520892090232096545650051755799297658390763820738295370567143697617670291263734710392873823956589171067167839738896249891955689437111486748587887718882564384870583135509339695096218451174112035938859L)],
    }

INIT_MESSAGE = '''\xff\xfd\x03\xff\xfb\x18\xff\xfb\x1f\xff\xfb\x20\xff\xfb\x21\xff\xfb\x22\xff\xfb\x27\xff\xfd\x05\xff\xfb\x23'''
INIT_MESSAGE2 = '''\xff\xfc\x25\xff\xfd\x01\xff\xfa\x1f\x00\x50\x00\x18\xff\xf0\xff\xfb\x00\xff\xfd\x00\xff\xfa\x27\x00\x00\x44\x49\x53\x50\x4c\x41\x59\x01\x6f\x73\x62\x6f\x78\x65\x73\x3a\x30\xff\xf0\xff\xfa\x27\x00\xff\xf0'''
LOGON_SUCCESS = '''\xff\xfa\x18\x01\xff\xf0'''
LOGON_MESSAGE = '''\xff\xfa\x18\x00\x78\x74\x65\x72\x6d\xff\xf0'''

class ExampleAvatar(avatar.ConchUser):
    """
    The avatar is used to configure SSH services/sessions/subsystems for
    an account.

    This account will use L{session.SSHSession} to handle a channel of
    type I{session}.
    """
    def __init__(self, username):
        avatar.ConchUser.__init__(self)
        self.username = username
        self.channelLookup.update({'session':session.SSHSession})



class ExampleRealm(object):
    """
    When using Twisted Cred, the pluggable authentication framework, the
    C{requestAvatar} method should return a L{avatar.ConchUser} instance
    as required by the Conch SSH server.
    """
    implements(portal.IRealm)

    def requestAvatar(self, avatarId, mind, *interfaces):
        """
        See: L{portal.IRealm.requestAvatar}
        """
        return interfaces[0], ExampleAvatar(avatarId), lambda: None


class FzSsh2TelnetProtocol(protocol.Protocol):
	"""
	Passes on the SSH data to a telnet server through simple TCP
	"""
	def connectionMade(self):
		self.point = TCP4ClientEndpoint(reactor, "127.0.0.1", 5080)
		self.telnetSide = FzTelnetClient()
		self.telnetSide.sshSide = self
		connectProtocol(self.point, self.telnetSide)

	def connectionLost(self, reason):
		self.telnetSide.loseConnection(reason)
		
	def dataReceived(self, data):
		"""
		Called when client send data over the shell session.

		Just echo the received data and and if Ctrl+C is received, close the
		session.
		"""
		if data == '\r':
			data = '\r\n'
		elif data == '\x03': #^C
			self.transport.loseConnection()
			return
		self.telnetSide.sendMessage(data)

	def sendMessage(self, msg):
		self.transport.write(msg)
		
		
class FzTelnetClient(protocol.Protocol):
	def connectionMade(self):
		self._init = True
	def sendMessage(self, msg):
		self.transport.write(msg)

	def dataReceived(self, data):
		global INIT_MESSAGE
		if(self._init and data[0] == '\xff'):
			self.sendMessage(INIT_MESSAGE)
			self.sendMessage(INIT_MESSAGE2)
			self._init = False
		elif(data == LOGON_SUCCESS):
			self.sendMessage(LOGON_MESSAGE)
		else:
			self.sshSide.sendMessage(data)
	
	def loseConnection(self, reason):
		self.transport.loseConnection()

		
class FzSsh2HTTPProtocol(protocol.Protocol):
	"""
	"""
	def connectionMade(self):
		self.point = HTTPClientEndpoint(reactor, "127.0.0.1", 5080)
		self.httpSide = FzHTTPClient()
		self.httpSide.sshSide = self
		connectProtocol(self.point, self.httpSide)

	def connectionLost(self, reason):
		self.httpSide.loseConnection(reason)
		
	def dataReceived(self, data):
		"""
		Called when client send data over the shell session.

		Just echo the received data and and if Ctrl+C is received, close the
		session.
		"""
		if data == '\r':
			data = '\r\n'
		elif data == '\x03': #^C
			self.transport.loseConnection()
			return
		
		self.httpSide.sendMessage(data)

	def sendMessage(self, msg):
		self.transport.write(msg)
		
		
class FzTClient(protocol.Protocol):
	def connectionMade(self):
		self._init = True
	def sendMessage(self, msg):
		agent = Agent(reactor)
		agent.request('GET', 'http://127.0.0.1:5080/', Headers({'User-Agent': ['Twisted Web Client Example']}), None)
		#self.transport.request(msg)

	def dataReceived(self, data):
		self.sshSide.sendMessage(data)
		
	def loseConnection(self, reason):
		self.transport.loseConnection()

class FzSsh2TCPProtocol(protocol.Protocol):
	"""
	"""
	def connectionMade(self):
		self.point = TCP4ClientEndpoint(reactor, "127.0.0.1", 5080)
		self.tcpSide = FzTCPClient()
		self.tcpSide.sshSide = self
		connectProtocol(self.point, self.tcpSide)

	def connectionLost(self, reason):
		self.tcpSide.loseConnection(reason)
		
	def dataReceived(self, data):
		"""
		Called when client send data over the shell session.

		Just echo the received data and and if Ctrl+C is received, close the
		session.
		"""
		if data == '\r':
			data = '\r\n'
		elif data == '\x03': #^C
			self.transport.loseConnection()
			return
		
		self.tcpSide.sendMessage(data)

	def sendMessage(self, msg):
		self.transport.write(msg)
		
		
class FzTCPClient(protocol.Protocol):
	def connectionMade(self):
		self._init = True
	def sendMessage(self, msg):
		self.transport.request(msg)

	def dataReceived(self, data):
		self.sshSide.sendMessage(data)
		
	def loseConnection(self, reason):
		self.transport.loseConnection()

		
class HTTPClientEndpoint(TCP4ClientEndpoint):
    """
    """
	
    def __init__(self, reactor, host, port):
        super(HTTPClientEndpoint, self).__init__(reactor, host, port, 30, None)
	
    def connect(self, protocolFactory):
        """
        Implement L{IStreamClientEndpoint.connect} to connect via TCP.
        """
        try:
            wf = _WrappingFactory(protocolFactory)
            self.agent = Agent(self._reactor)
            return wf._onConnection
        except:
            return defer.fail()
		
class ExampleSession(object):
    """
    This selects what to do for each type of session which is requested by the
    client via the SSH channel of type I{session}.
    """

    def __init__(self, avatar):
        """
        In this example the avatar argument is not used for session selection,
        but for example you can use it to limit I{shell} or I{exec} access
        only to specific accounts.
        """

    def getPty(self, term, windowSize, attrs):
        """
        We don't support pseudo-terminal sessions.
        """


    def execCommand(self, proto, cmd):
        """
        We don't support command execution sessions.
        """
        raise Exception("not executing commands")

    def openShell(self, transport):
        """
        Use our protocol as shell session.
        """
        self.protocol = FzSsh2TCPProtocol()
        # Connect the new protocol to the transport and the transport
        # to the new protocol so they can communicate in both directions.
        self.protocol.makeConnection(transport)
        transport.makeConnection(session.wrapProtocol(self.protocol))
	self.protocol.session = self

    def eofReceived(self):
        pass

    def closed(self):
        pass



components.registerAdapter(ExampleSession, ExampleAvatar, session.ISession)



class ExampleFactory(factory.SSHFactory):
    """
    This is the entry point of our SSH server implementation.

    The SSH transport layer is implemented by L{SSHTransport} and is the
    protocol of this factory.

    Here we configure the server's identity (host keys) and handlers for the
    SSH services:
    * L{connection.SSHConnection} handles requests for the channel multiplexing
      service.
    * L{userauth.SSHUserAuthServer} handlers requests for the user
      authentication service.
    """
    protocol = SSHServerTransport
    # Server's host keys.
    # To simplify the example this server is defined only with a host key of
    # type RSA.
    publicKeys = {
        'ssh-rsa': keys.Key.fromFile(SERVER_RSA_PUBLIC)
    }
    privateKeys = {
        'ssh-rsa': keys.Key.fromFile(SERVER_RSA_PRIVATE)
    }
    # Service handlers.
    services = {
        'ssh-userauth': userauth.SSHUserAuthServer,
        'ssh-connection': connection.SSHConnection
    }

    def getPrimes(self):
        """
        See: L{factory.SSHFactory}
        """
        return PRIMES


portal = portal.Portal(ExampleRealm())
passwdDB = InMemoryUsernamePasswordDatabaseDontUse()
passwdDB.addUser('user', 'password')
#sshDB = SSHPublicKeyChecker(InMemorySSHKeyDB({'user': [keys.Key.fromFile(CLIENT_RSA_PUBLIC)]}))
portal.registerChecker(passwdDB)
#portal.registerChecker(sshDB)
ExampleFactory.portal = portal

if __name__ == '__main__':
    reactor.listenTCP(5022, ExampleFactory())
    reactor.run()
