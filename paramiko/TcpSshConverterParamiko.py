#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.internet.protocol import Protocol, Factory
from twisted.internet import reactor
from threading import Thread
### Protocol Implementation

# This is just about the simplest possible protocol
class Echo(Protocol):
	def dataReceived(self, data):
		"""
		As soon as any data is received, write it back.
		"""
		
		print "Data!!! {}".format(data)
		stdin, stdout, stderr = self.ssh.exec_command(data)
		return stdout.readlines()
		
	def connectionMade(self):
		import paramiko
		self.ssh = paramiko.SSHClient()
		self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
		self.ssh.connect('127.0.0.1', port=5122, username='user', password='password')
		
	def connectionLost(self, reason):
		print 'connection lost\n'
		self.ssh.close()
	def sendData(self, data):
		self.transport.write(data)

def main():
	f = Factory()
	f.protocol = Echo
	reactor.listenTCP(5080, f)
	reactor.run()

if __name__ == '__main__':
    main()
