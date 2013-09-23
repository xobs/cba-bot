r"""CBA channel bot, designed to assist us in reporting goings-on
during the IGG marathon.

It should be started with an environment set something like::

    INITTIME=0
    IRCSERVERS='{"EX": {"username": "", "password": "", "realname": "Example Bot", "channels": ["#example"], "nick": "ExampleBot", "host": "irc.example.com", "port": 6667}}'
    MSG="I'm just a bot.  I don't know a lot."
    MSGPERIOD="3600"
    POLLRATE="10"

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


# Load default values, for when the environment is not present
config = defaultdict(list, [
    ('DEBUG', False),
    ('INITTIME', '0'),
    ('IRCSERVERS', '{"TTV": {"username": "", "password": "", "realname": "CBA Bot", "channels": ["#cba"], "nick": "QQMore", "host": "127.0.0.1", "port": 6667}}'),
    ('IRCSUBS', "[]"),
    ('MSG', "I'm just a bot.  I don't know a lot."),
    ('MSGPERIOD', "15"),
    ('POLLRATE', "10"),
])
for key, value in os.environ.iteritems():
    config[key] = value

class IRCConnection(irc.IRCClient):
    """Handle one connection to a server, in one or more channels"""
    def connectionMade(self):
        irc.IRCClient.connectionMade(self)

    def connectionLost(self, reason):
        irc.IRCClient.connectionList(self, reason)

    def signedOn(self):
        for channel in self.config.channels:
            self.join(channel.encode('ascii', 'ignore'))

    def joined(self, channel):
        irc.IRCClient.msg(self, channel, "Hello, there " + channel)
        irc.IRCClient.msg(self, channel, config['MSG'])

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
    srvdict = loads(config["IRCSERVERS"])

    for key, srv in srvdict.iteritems():
        servers[key] = IRCConnectionManager(key,
                srv['channels'], srv['nick'], srv['realname'],
                srv['username'], srv['password'])
        reactor.connectTCP(srv['host'], srv['port'], servers[key])

    # Run all bots
    reactor.run()
