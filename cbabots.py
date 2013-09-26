r"""Source file for various bots used by CBA, particularly during the
IGG marathon.
"""

from json import loads, dumps
from urllib2 import urlopen
import threading
import random
import time
import strict_rfc3339


class BotPersonality():
    """Common interface for various bot personalities"""
    running = False

    def __init__(self, connection, name):
        self.name = name
        self.connection = connection
        self.running = False
        print "BotPersonality activate!  Form of: " + name

    def setConnection(self, connection):
        self.connection = connection

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
        self.connection.sendMessage(self, message)


class DonBot(BotPersonality):
    """Monitor donations and announce them as they come in"""
    seen_keys = set()
    new_data = []

    def __init__(self, connection, url,
            interval=15, variance=5, reportlast=5, ignoreolderthan=3600):
        BotPersonality.__init__(self, connection, "DonBot")
        self.url                = url
        self.interval           = interval
        self.variance           = variance
        self.reportlast         = reportlast
        self.ignoreolderthan    = ignoreolderthan
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

        # Special startup code.  If seen_keys is empty and we have new data,
        # stuff all but the last /reportlast/ variables into the "seen_keys"
        # set, to prevent spamming the channel.
        if len(self.seen_keys) == 0:
            trimmed_list = []

            # Only allow recent donations to be posted, and limit the list
            # to /reportlast/ items.
            # If an object is ignored, put its pk in the seen_keys set.
            now = time.time()
            for obj in self.new_data:
                if (now - obj['timestamp']) < self.ignoreolderthan \
                    and len(trimmed_list) < self.reportlast:
                    trimmed_list.append(obj)
                else:
                    self.seen_keys.add(obj['pk'])

            self.new_data = trimmed_list
            
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
