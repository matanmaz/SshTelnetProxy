from twisted.internet.protocol import Protocol, ServerFactory, ClientFactory, connectionDone
from twisted.internet.defer import Deferred, succeed, failure
from twisted.conch import avatar, interfaces, error
from twisted.conch.ssh import userauth, connection, keys, session, address
from twisted.conch.ssh.factory import SSHFactory
from twisted.conch.ssh.transport import SSHServerTransport
from twisted.python import components, log
from twisted.cred.portal import Portal, IRealm
from zope.interface import implements, implementer
from twisted.cred.checkers import ICredentialsChecker
from twisted.cred import credentials
from twisted.internet import defer, reactor

PRIMES = {
    2048: [(2L, 24265446577633846575813468889658944748236936003103970778683933705240497295505367703330163384138799145013634794444597785054574812547990300691956176233759905976222978197624337271745471021764463536913188381724789737057413943758936963945487690939921001501857793275011598975080236860899147312097967655185795176036941141834185923290769258512343298744828216530595090471970401506268976911907264143910697166165795972459622410274890288999065530463691697692913935201628660686422182978481412651196163930383232742547281180277809475129220288755541335335798837173315854931040199943445285443708240639743407396610839820418936574217939L)],
    4096: [(2L, 889633836007296066695655481732069270550615298858522362356462966213994239650370532015908457586090329628589149803446849742862797136176274424808060302038380613106889959709419621954145635974564549892775660764058259799708313210328185716628794220535928019146593583870799700485371067763221569331286080322409646297706526831155237865417316423347898948704639476720848300063714856669054591377356454148165856508207919637875509861384449885655015865507939009502778968273879766962650318328175030623861285062331536562421699321671967257712201155508206384317725827233614202768771922547552398179887571989441353862786163421248709273143039795776049771538894478454203924099450796009937772259125621285287516787494652132525370682385152735699722849980820612370907638783461523042813880757771177423192559299945620284730833939896871200164312605489165789501830061187517738930123242873304901483476323853308396428713114053429620808491032573674192385488925866607192870249619437027459456991431298313382204980988971292641217854130156830941801474940667736066881036980286520892090232096545650051755799297658390763820738295370567143697617670291263734710392873823956589171067167839738896249891955689437111486748587887718882564384870583135509339695096218451174112035938859L)],
    }
# Path to RSA SSH keys used by the server.
SERVER_RSA_PRIVATE = 'ssh-keys/ssh_host_rsa_key'
SERVER_RSA_PUBLIC = 'ssh-keys/ssh_host_rsa_key.pub'

# Path to RSA SSH keys accepted by the server.
CLIENT_RSA_PUBLIC = 'ssh-keys/client_rsa.pub'


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
    implements(IRealm)

    def requestAvatar(self, avatarId, mind, *interfaces):
        """
        See: L{portal.IRealm.requestAvatar}
        """
        return interfaces[0], ExampleAvatar(avatarId), lambda: None


class SSH2HTTPConverterSession(object):
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
        raise Exception("We don't support command execution sessions.")

    def openShell(self, transport):
        """
        Use our protocol as shell session.
        """
        converter = transport.session.conn.transport.factory
        protocol = SideProtocol()
        # Connect the new protocol to the transport and the transport
        # to the new protocol so they can communicate in both directions.
        protocol.makeConnection(transport)
        transport.makeConnection(session.wrapProtocol(protocol))

        converter.push_a_side(protocol)
        protocol.other_side = converter.get_b_side(protocol)
        # need to give a_side the b_side

    def eofReceived(self):
        pass

    def closed(self):
        pass


components.registerAdapter(SSH2HTTPConverterSession, ExampleAvatar, session.ISession)


class SideProtocol(Protocol):

    def __init__(self):
        self.other_side = None

    def dataReceived(self, data):
        if self.other_side is not None:
            self.other_side.sendData(data)

    def sendData(self, data):
        self.transport.write(data)

    def set_other_side(self, other_side):
        self.other_side = other_side

    def connectionLost(self, reason=connectionDone):
        if self.other_side:
            self.other_side.loseConnection()

    def loseConnection(self):
        self.transport.loseConnection()


class SideFactory(ClientFactory):
    protocol = SideProtocol


class BSideFactory(ClientFactory):

    def __init__(self, converter, a_side, protocol):
        self.converter = converter
        self.protocol = protocol
        self.a_side = a_side

    def buildProtocol(self, addr):
        p = ClientFactory.buildProtocol(self, addr)

        #give ASideServer his b_side
        self.a_side.set_b_side(p)

        d = self.converter.get_a_side(p)
        # later set ASideSession to be a_side
        d.addCallback(p.set_other_side)
        return p


class HTTPSideProtocol(SideProtocol):

    def __init__(self):
        SideProtocol.__init__(self)
        self.authenticated = Deferred()
        self.username = 'osboxes'
        self.password = 'osboxes.org'
        self.other_side = None
        self.buffer = ''

    def dataReceived(self, response):
        status, data = self.parse_http_response(response)
        if self.authenticated is not None and status==200:
            d, self.authenticated  = self.authenticated, None
            d.callback(True)
        elif self.authenticated is not None and status!=200:
            d, self.authenticated = self.authenticated, None
            d.callback(False)
        self.write_other_side(data)

    def write_other_side(self, data):
        if self.other_side:
            self.other_side.transport.write(data)
        else:
            self.buffer += data

    def set_other_side(self, other_side):
        SideProtocol.set_other_side(self, other_side)
        if len(self.buffer) > 0:
            self.write_other_side(self.buffer)
            self.buffer = ''

    def login(self, username, password):
        self.username = username
        #self.password = password
        self.sendData('auth')
        return self.authenticated

    def sendData(self, data):
        from base64 import b64encode
        request =  "GET / HTTP/1.1\r\n" \
               "username:" + b64encode(self.username) + "\r\n" + \
               "password:" + b64encode(self.password) + "\r\n" + \
               "host:" + b64encode('127.0.0.1') + "\r\n" + \
               "port:" + b64encode('22') + "\r\n" + \
               "\r\n" + \
               b64encode(data)
        self.transport.write(request)

    @staticmethod
    def parse_http_response(data):
        from base64 import b64decode
        lines = data.split("\r\n")
        if lines[0] == '200 OK':
            status = 200
        else:
            status = 400
        return status, b64decode("".join(lines[lines.index(''):]))


class ASideServer(SSHServerTransport):

    def connectionMade(self):
        # upon receiving a connection connect on towards the HTTP side
        SSHServerTransport.connectionMade(self)
        d_host = '127.0.0.1'
        d_port = 5080
        factory = BSideFactory(self.factory, self, HTTPSideProtocol)
        reactor.connectTCP(d_host, d_port, factory)

    def set_b_side(self, b_side):
        self.b_side = b_side


class SSHConverterAuthServer(userauth.SSHUserAuthServer):

    def auth_password(self, packet):
        from twisted.conch.ssh.common import getNS
        password = getNS(packet[1:])[0]
        # credential object with user input
        c = BSideUsernamePassword(self.user, password, self.transport.b_side)

        return self.portal.login(c, None, interfaces.IConchUser).addErrback(
            self._ebPassword)


@implementer(credentials.IUsernamePassword)
class BSideUsernamePassword:

    def __init__(self, username, password, b_side):
        self.username = username
        self.password = password
        self.b_side = b_side

    def checkPassword(self):
        d = self.b_side.login(self.username, self.password)
        return d#succeed(True)#self.b_side.login(self.username, self.password)


@implementer(ICredentialsChecker)
class SSH2HTTPConverterFactory(SSHFactory):
    protocol = ASideServer
    services = {
        'ssh-userauth': SSHConverterAuthServer,
        'ssh-connection': connection.SSHConnection
    }

    def __init__(self, c_port):
        self.c_port = c_port
        self.deferreds = {}
        self.a_sides = {}
        self.b_sides = {}

    def get_a_side(self, b_side):
        if b_side in self.a_sides.keys():
            return self.a_sides[b_side]
        else:
            self.deferreds[b_side] = Deferred()
            return self.deferreds[b_side]

    def push_a_side(self, a_side):
        b_side, d = self.deferreds.popitem()
        self.a_sides[b_side] = a_side
        self.b_sides[a_side] = b_side
        d.callback(a_side)

    def get_b_side(self, a_side):
        return self.b_sides[a_side]

    credentialInterfaces = (credentials.IUsernamePassword, credentials.IUsernameHashedPassword)

    def requestAvatarId(self, credentials):
        return credentials.checkPassword().addCallback(
               self._cbPasswordMatch, credentials.username)

    def _cbPasswordMatch(self, matched, username):
        if matched:
            return username
        else:
            return failure.Failure(error.UnauthorizedLogin())

    publicKeys = {
        'ssh-rsa': keys.Key.fromFile(SERVER_RSA_PUBLIC)
    }
    privateKeys = {
        'ssh-rsa': keys.Key.fromFile(SERVER_RSA_PRIVATE)
    }

    def getPrimes(self):
        """
        See: L{factory.SSHFactory}
        """
        return PRIMES

    """def getPublicKeys(self):
        return self.publicKeys

    def getPrivateKeys(self):
        return self.privateKeys"""


def main():
    import sys
    from twisted.python import log
    log.startLogging(sys.stdout)
    portal = Portal(ExampleRealm())
    c_port = 5001
    factory = SSH2HTTPConverterFactory(c_port)
    portal.registerChecker(factory)
    SSH2HTTPConverterFactory.portal = portal
    reactor.listenTCP(c_port, factory)
    reactor.run()


if __name__ == "__main__":
    main()
