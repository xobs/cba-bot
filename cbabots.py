r"""Source file for various bots used by CBA, particularly during the
IGG marathon.

It should be started with an environment set something like:

    INITTIME=0
    IRCSERVERS='{"EX": {"username": "",
                        "password": "",
                        "realname": "Example Bot",
                        "channels": ["#example"],
                        "nick": "ExampleBot",
                        "host": "irc.example.com",
                        "port": 6667}}'
    MSG="I'm just a bot.  I don't know a lot."
    MSGPERIOD="3600"
    POLLRATE="10"

To enable debugging, add a variable of "DEBUG" and set it to "True"
"""

from json import loads, dumps
from urllib2 import urlopen
import threading
import random
import strict_rfc3339


class BotPersonality():
    """Common interface for various bot personalities"""
    running = False

    def __init__(self, connection, channel, name):
        self.name = name
        self.connection = connection
        self.channel = channel
        self.running = False
        print "BotPersonality activate!  Form of: " + name

    def pauseBot(self):
        """Stop a bot from making updates (e.g. if a connection fails)"""
        print "Pausing BotPersonality " + self.name
        self.running = False

    def resumeBot(self):
        """Resume a bot (e.g. when connecting, or when reconnecting)"""
        print "Resuming BotPersonality" + self.name
        self.running = True

    def sendMessage(self, message):
        """Send a message to the configured channel"""
        self.connection.sendMessage(self, self.channel, message)


class DonBot(BotPersonality):
    """Monitor donations and announce them as they come in"""
    seen_keys = set()
    new_data = []

    def __init__(self, connection, channel, url, interval=15, variance=5):
        BotPersonality.__init__(self, connection, channel, "DonBot")
        self.url      = url
        self.interval = interval
        self.variance = variance
        random.seed()

    def pauseBot(self):
        BotPersonality.pauseBot(self)
        self.fetch_thread.cancel()

    def resumeBot(self):
        BotPersonality.resumeBot(self)
        self.queueBot()

    def queueBot(self):
        """Queue the fetch function to run agan after 'interval' seconds"""
        # Retrigger this function, if we're still running
        if (self.running):
            delay = self.interval + random.randrange(self.variance)
            self.fetch_thread = threading.Timer(delay, self.doWork)
            self.fetch_thread.start()

    def doWork(self):
        """Fetch donations from the server and announce new entries"""
        self.queueBot() # Requeue in case of crash

        if self.sendNextMessage():
            return

        # Load data from the URL.  If the primary key is new, add it to the
        # new_data list.  We'll sort this list by time afterwards and post
        # the oldest message.
        print "No data found in cache.  Fetching..."
        data = loads(urlopen(self.url).read())
        for donation in data:
            timestamp = strict_rfc3339.rfc3339_to_timestamp(donation['time'])
            donation['timestamp'] = timestamp
            if donation['pk'] not in self.seen_keys:
                self.new_data.append(donation)

        # Re-sort the data by timestamp
        self.new_data = sorted(self.new_data,
                                key=lambda donation: donation['timestamp'])
        self.sendNextMessage()


    def sendNextMessage(self):
        """Send the next message to the chat channel, if one exists.
            Return True if a message was sent, False if no message was sent."""
        if len(self.new_data) == 0:
            return False
        donation = self.new_data.pop(0)
        self.seen_keys.add(donation['pk'])

        if donation['name'] == "":
            if donation['game'] == "":
                self.sendMessage("An anonymous benefactor just doated $" 
                        + donation['amount'])
            else:
                self.sendMessage("A mysterious person just donated $" 
                        + donation['amount'] + " to play " + donation['game'])
        else:
            if donation['game'] == "":
                self.sendMessage(donation['name'] 
                        + " just donated $" + donation['amount'])
            else:
                self.sendMessage(donation['name'] 
                        + " just donated $" + donation['amount']
                        + " to play " + donation['game'])
        return True
