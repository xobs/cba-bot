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
from twisted.internet import defer
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
    CHANNEL_PREFIXES = '&#!+'
    OPS_PREFIXES = '%@&~' # Halfop, Op, Admin, and Owner
    _namescallback = {}

    def connectionMade(self):
        irc.IRCClient.connectionMade(self)
        self.config.bot.setConnection(self)

    def connectionLost(self, reason):
        irc.IRCClient.connectionLost(self, reason)

    def signedOn(self):
        for channel in self.config.channels:
            self.join(channel.encode('ascii', 'ignore'))
        self.config.bot.resumeBot()

    def joinedResult(things, args):
        (self, channel, users) = args
        op_set = set()
        user_set = set()

        # Strip symbols and determine ops
        for user in users:
            if len(user) > 0 and user[0] in self.OPS_PREFIXES:
                op_set.add(user.lstrip(self.OPS_PREFIXES))
            user_set.add(user.lstrip(self.OPS_PREFIXES))

        self.config.bot.joinedChannel(channel, user_set)
        self.config.bot.setOpList(channel, op_set)

    def joined(self, channel):
        self.active_channels.add(channel)
        self.names(channel).addCallback(self.joinedResult)

    def left(self, channel):
        self.active_channels.remove(channel)

    def sendMessage(self, bot, message):
        for channel in self.active_channels:
            irc.IRCClient.msg(self, channel, message)

    def sendDirectMessage(self, bot, user, message):
        irc.IRCClient.msg(self, user, message)

    def userJoined(self, user, channel):
        pass

    def modeChanged(self, user, channel, is_set, modes, args):
        if modes.find("o") == -1:
            return
        if is_set:
            for u in args:
                self.config.bot.addOp(channel, u)
                print "Added op for " + arg
        else:
            for u in args:
                self.config.bot.removeOp(channel, u)
                print "Removed op for " + arg

    def privmsg(self, user, channel, msg):
        othernick = user.split("!")[0]
        found_channel = False

        # Make sure the received message is from an active channel
        for active_channel in self.active_channels:
            if channel == active_channel:
                found_channel = True
                self.config.bot.receiveMessage(othernick, msg)
                return

        if channel == self.config.nickname:
            self.config.bot.receivePrivateMessage(othernick, msg)
            return

        # If it's not from an active channel, and it's from a real channel,
        # that's considered a bug.
        if not found_channel and not channel[0] not in self.CHANNEL_PREFIXES:
            if config['DEBUG']:
                print "ERROR: Channel " + channel + " not active!"
            return

        if config['DEBUG']:
            print "ERROR: Privmsg from " + channel + " to " + msg + \
                " message " + msg + " not handled!"
        return

    def names(self, channel):
        """Get a list of users in a channel"""
        channel = channel.lower()
        d = defer.Deferred()
        if channel not in self._namescallback:
            self._namescallback[channel] = ([], [])

        self._namescallback[channel][0].append(d)
        self.sendLine("NAMES %s" % channel)
        return d

    def irc_RPL_NAMREPLY(self, prefix, params):
        channel = params[2].lower()
        nicklist = params[3].split(' ')

        if channel not in self._namescallback:
            return

        n = self._namescallback[channel][1]
        n += nicklist

    def irc_RPL_ENDOFNAMES(self, prefix, params):
        channel = params[1].lower()
        if channel not in self._namescallback:
            return

        callbacks, namelist = self._namescallback[channel]

        for cb in callbacks:
            cb.callback((self, channel, namelist))

        del self._namescallback[channel]



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
        if 'username' not in srv:
            srv['username'] = ''
        if 'password' not in srv:
            srv['password'] = ''
        if 'port' not in srv:
            srv['port'] = 6667

        servers[key] = IRCConnectionManager(key,
                srv['channels'], srv['nick'], srv['realname'],
                srv['username'], srv['password'])

        if srv['personality'] == "donbot":
            bots[key] = cbabots.DonBot(servers[key], 
                                    srv['interval'], srv['variance'],
                                    srv['url'],
                                    srv['reportlast'], srv['ignoreolderthan'])
        elif srv['personality'] == "microtron":
            bots[key] = cbabots.MicroTron(servers[key], 
                                    srv['interval'], srv['variance'],
                                    srv['message'])
        elif srv['personality'] == "gavelmaster":
            bots[key] = cbabots.GavelMaster(servers[key], 
                                    srv['interval'], srv['variance'])
        else:
            raise Exception("Unknown or missing bot personality: "
                    + srv['personality'])

        servers[key].setBot(bots[key])
        reactor.connectTCP(srv['host'], srv['port'], servers[key])

    # Run all bots
    reactor.run()
