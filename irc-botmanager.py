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
import signal
import random
import time
from twisted.words.protocols import irc
from twisted.internet import reactor, protocol
from twisted.internet import threads
from twisted.internet import defer
from urllib2 import urlopen
import cbabots
from threading import Thread, Event
from deep_eq import deep_eq


# Load default values, for when the environment is not present
config = defaultdict(list, [
    ('DEBUG', False),
    ('BOTS_REFRESH', 15),
])
for key, value in os.environ.iteritems():
    config[key] = value

if "BOTS" not in config:
    print "Error: No BOTS config found"
    os._exit(0)


class IRCConnection(irc.IRCClient):
    """Handle one connection to a server, in one or more channels"""
    CHANNEL_PREFIXES = '&#!+'
    OPS_PREFIXES = '%@&~' # Halfop, Op, Admin, and Owner

    def connectionMade(self):
        self.active_channels = set()
        self._namescallback = {}
        time.sleep(2)
        self.nick = self.nickname
        irc.IRCClient.connectionMade(self)
        self.config.bot.setConnection(self)

    def connectionLost(self, reason):
        irc.IRCClient.connectionLost(self, reason)

    def signedOn(self):
        for channel in self.config.channels:
            self.join(channel.encode('ascii', 'ignore'))
        if self.config.onconnect != "":
            time.sleep(2)
            self.sendLine(self.config.onconnect)
        self.config.bot.resumeBot()

    def getName(self):
        return self.config.getName()

    def getNick(self):
        return self.nick

    def nickChanged(self, nick):
        self.nick = nick

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
            # Hack for printing blank messages
            if len(message.split()) == 0:
                fmt = 'PRIVMSG %s :' % (channel,)
                irc.IRCClient.sendLine(self, fmt + message)
            else:
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
        else:
            for u in args:
                self.config.bot.removeOp(channel, u)

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
            username, password, onconnect, hostname, servername):
        # Data must not be unicode, otherwise Twisted will crash
        self.nickname   = nickname.encode('ascii', 'ignore')
        self.realname   = realname.encode('ascii', 'ignore')
        self.hostname   = hostname.encode('ascii', 'ignore')
        self.servername = servername.encode('ascii', 'ignore')
        self.username   = username
        if username is not None:
            self.username   = self.username.encode('ascii', 'ignore')
        self.password   = password
        if password is not None:
            self.password   = self.password.encode('ascii', 'ignore')
        self.onconnect  = onconnect
        if onconnect is not None:
            self.onconnect  = self.onconnect.encode('ascii', 'ignore')
        self.channels   = []
        self.connection = None
        self.config     = None
        self.should_reconnect = True
        self.clock      = None
        self.bot        = None
        self.name       = ""
        for channel in channels:
            self.channels.append(channel.encode('ascii', 'ignore'))

    def setBot(self, bot):
        if self.bot is not None:
            self.bot.pauseBot()
        self.bot = bot

    def setConnection(self, connection):
        self.connection = connection

    def setConfig(self, config):
        self.config = config

    def setName(self, name):
        self.name = name

    def getConnection(self):
        return self.connection

    def getConfig(self):
        return self.config

    def getName(self):
        return self.name

    def stopReconnecting(self):
        self.should_reconnect = False

    def stopBot(self):
        if self.bot is not None:
            self.bot.pauseBot()

    def buildProtocol(self, addr):
        p = IRCConnection()
        p.config = self
        p.nickname = self.nickname
        p.realname = self.realname
        p.username = self.username
        p.password = self.password
        p.hostname = self.hostname
        p.servername = self.servername
        return p

    def clientConnectionLost(self, connector, reason):
        print "Connection lost"
        self.retry(connector)

    def clientConnectionFailed(self, connector, reason):
        print "Connection failed"
        self.retry(connector)

    def retry(self, connector, delay=60):
        jitter = 0
        def reconnector():
            self._callID = None
            if self.should_reconnect:
                print "Reconnecting"
                connector.connect()
            else:
                print "Not reconnecting"

        delay = random.normalvariate(delay, delay * 0.11)

        if self.clock is None:
            from twisted.internet import reactor
            self.clock = reactor
        self._callID = self.clock.callLater(delay, reconnector)


def createBot(connectionManager, srv):
    if srv['personality'] == "donbot":
        return cbabots.DonBot(connectionManager,
                                srv['interval'], srv['variance'],
                                srv['cmdurl'],
                                srv['url'],
                                srv['reportlast'], srv['ignoreolderthan'])
    elif srv['personality'] == "microtron":
        return cbabots.MicroTron(connectionManager,
                                srv['interval'], srv['variance'],
                                srv['cmdurl'],
                                srv['message'].encode('ascii', 'ignore'))
    elif srv['personality'] == "gavelmaster":
        return cbabots.GavelMaster(connectionManager,
                                srv['interval'], srv['variance'],
                                srv['cmdurl'])
    elif srv['personality'] == "pollboy":
        return cbabots.PollBoy(connectionManager,
                                srv['interval'], srv['variance'],
                                srv['cmdurl'])
    elif srv['personality'] == "bottob":
        return cbabots.Bottob(connectionManager,
                                srv['interval'], srv['variance'],
                                srv['cmdurl'])
    else:
        raise Exception("Unknown or missing bot personality: "
                + srv['personality'])

def reloadConfig(url, servers):
    srvdict = {}
    seen_bots = set()
    try:
        srvdict = loads(urlopen(url).read())
    except:
        print "ERROR: Couldn't load JSON from " + url
        return

    for key, srv in srvdict.iteritems():
#        try:
            seen_bots.add(key)
            # Set up defaults for parameters that are undefined in the bot
            if 'variance' not in srv:
                srv['variance'] = 1
            if 'interval' not in srv:
                srv['interval'] = 120
            if 'username' not in srv:
                srv['username'] = None
            if 'password' not in srv:
                srv['password'] = None
            if 'port' not in srv:
                srv['port'] = 6667
            if 'cmdurl' not in srv:
                srv['cmdurl'] = None
            if 'onconnect' not in srv:
                srv['onconnect'] = ""

            if key in servers:
                if deep_eq(servers[key].getConfig(), srv):
                    continue

            # Disconnect the bot, if it exists already
            if key in servers:
                print "Config changed for bot " + key + ', reloading...'
                servers[key].stopReconnecting()
                servers[key].stopFactory()
                servers[key].getConnection().disconnect()
                servers[key].stopBot()
            else:
                print "Adding bot (cfg: " + key + ")"

            servers[key] = IRCConnectionManager(key,
                    srv['channels'], srv['nick'], srv['realname'],
                    srv['username'], srv['password'],
                    srv['onconnect'],
                    srv['host'], srv['host'])

            servers[key].setBot(createBot(servers[key], srv))
            servers[key].setConnection(reactor.connectTCP(
                                    srv['host'],
                                    srv['port'],
                                    servers[key]))
            servers[key].setConfig(srv)
            servers[key].setName(key)
#        except:
#            pass

    # If a bot has disappeared from the config, disconnect it.
    for key in servers.keys():
        if not key in seen_bots:
            print "Bot " + key + " disappeared, removing"
            servers[key].stopReconnecting()
            servers[key].stopFactory()
            servers[key].getConnection().disconnect()
            servers[key].stopBot()
            servers[key].setBot(None)
            del servers[key]
    return servers


class ConfigReloader(Thread):
    def __init__(self, event, configUrl, period, servers):
        Thread.__init__(self)
        self.stopped = event
        self.configUrl = configUrl
        self.period = period
        self.servers = servers

    def run(self):
        while not self.stopped.wait(self.period):
#            try:
                print "Reloading config..."
                reloadConfig(self.configUrl, self.servers)
#            except:
                pass

if __name__ == '__main__':
    try:
        locale.setlocale(locale.LC_ALL, 'en_US.utf8')
    except:
        print "WARNING: en_US.utf8 locale not found falling back to 'C'"
        locale.setlocale(locale.LC_ALL, 'C')

    def handle_ctrlc(signal, frame):
        print 'SIGINT hit, quitting...'
        os._exit(0)
    signal.signal(signal.SIGINT, handle_ctrlc)


    # Connect to each server defined in IRCSERVERS
    servers = {} 
    reloadConfig(config["BOTS"], servers)
    reloaderEvent = Event()
    configReloader = ConfigReloader(reloaderEvent,
                                    config["BOTS"],
                                    int(config["BOTS_REFRESH"]),
                                    servers)
    configReloader.start()

    # Run all bots
    reactor.run()
