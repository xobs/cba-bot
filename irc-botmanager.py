#!/usr/bin/env python
r"""CBA channel bot, designed to assist us in reporting goings-on
during the IGG marathon.

See README.md for configuration information.

To enable debugging, add a variable of "DEBUG" and set it to "True"
"""

from collections import defaultdict
from json import loads, dumps
import locale
import os
from twisted.words.protocols import irc
from twisted.internet import reactor, protocol
from twisted.internet import threads
from urllib2 import urlopen
import cbabots


# Load default values, for when the environment is not present
config = defaultdict(list, [
    ('DEBUG', False),
])
for key, value in os.environ.iteritems():
    config[key] = value



class IRCConnection(irc.IRCClient):
    """Handle one connection to a server, in one or more channels"""
    active_channels = set()
    def connectionMade(self):
        irc.IRCClient.connectionMade(self)
        self.config.bot.setConnection(self)

    def connectionLost(self, reason):
        irc.IRCClient.connectionList(self, reason)

    def signedOn(self):
        for channel in self.config.channels:
            self.join(channel.encode('ascii', 'ignore'))
        self.config.bot.resumeBot()

    def joined(self, channel):
        self.active_channels.add(channel)

    def left(self, channel):
        self.active_channels.remove(channel)

    def sendMessage(self, bot, message):
        for channel in self.active_channels:
            irc.IRCClient.msg(self, channel, message.encode('ascii', 'ignore'))

    def privmsg(self, user, channel, msg):
        print "Priv msg from " + user + " on channel " + channel + ": " + msg

class IRCConnectionManager(protocol.ClientFactory):
    """Each time there's a new IRC connection, this class will create a
    new IRCConnection to manage it."""

    def __init__(self, name, channels, nickname, realname,
            username, password):
        # Data must not be unicode, otherwise Twisted will crash
        self.nickname = nickname.encode('ascii', 'ignore')
        self.realname = realname.encode('ascii', 'ignore')
        self.username = username.encode('ascii', 'ignore')
        self.password = password.encode('ascii', 'ignore')
        self.channels = []
        for channel in channels:
            self.channels.append(channel.encode('ascii', 'ignore'))

    def setBot(self, bot):
        self.bot = bot

    def buildProtocol(self, addr):
        p = IRCConnection()
        p.config = self
        p.nickname = self.nickname
        p.realname = self.realname
        return p

    def clientConnectionLost(self, connector, reason):
        connector.connect()

    def clientConnectionFailed(self, connector, reason):
        reactor.stop()


if __name__ == '__main__':
    try:
        locale.setlocale(locale.LC_ALL, 'en_US.utf8')
    except:
        print "WARNING: en_US.utf8 locale not found falling back to 'C'"
        locale.setlocale(locale.LC_ALL, 'C')

    # Attach a signal handler in debug mode, so Ctrl-C worls
    if config['DEBUG']:
        import signal, sys
        print "Debug mode detected, installing signal handler"
        def handle_ctrlc(signal, frame):
            print 'SIGINT hit, quitting...'
            os._exit(0)
        signal.signal(signal.SIGINT, handle_ctrlc)


    # Connect to each server defined in IRCSERVERS
    servers = {} 
    bots = {}
    srvdict = loads(config["BOTS"])

    for key, srv in srvdict.iteritems():
        if 'variance' not in srv:
            srv['variance'] = 0

        servers[key] = IRCConnectionManager(key,
                srv['channels'], srv['nick'], srv['realname'],
                srv['username'], srv['password'])

        if srv['personality'] == "donbot":
            print "Found donbot"
            bots[key] = cbabots.DonBot(servers[key], 
                                    srv['interval'], srv['variance'],
                                    srv['url'],
                                    srv['reportlast'], srv['ignoreolderthan'])
        elif srv['personality'] == "microtron":
            print "Found microtron"
            bots[key] = cbabots.MicroTron(servers[key], 
                                    srv['interval'], srv['variance'],
                                    srv['message'])
        else:
            print "Unknown or missing bot personality"

        servers[key].setBot(bots[key])
        reactor.connectTCP(srv['host'], srv['port'], servers[key])

    # Run all bots
    reactor.run()
