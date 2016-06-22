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
		print data
	def connectionMade(self):
		print 'connection made\n'
		self.userInputThread = UserInputThread(self)
		self.userInputThread.start()
	def connectionLost(self, reason):
		print 'connection lost\n'
		self.userInputThread.stop()
	def sendData(self, data):
		self.transport.write(data)

class UserInputThread(Thread):
	def __init__(self, transport):
		Thread.__init__(self)
		self.transport = transport
		self._stop = False
	def run(self):
		while(not self._stop):
			self.transport.sendData(raw_input('enter data:'))
	def stop(self):
		self._stop = True

def main():
	f = Factory()
	f.protocol = Echo
	reactor.listenTCP(8000, f)
	reactor.run()

if __name__ == '__main__':
    main()
