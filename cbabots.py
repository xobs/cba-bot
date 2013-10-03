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

    def __init__(self, connection, interval, variance):
        self.name       = self.__class__.__name__
        self.connection = connection
        self.running    = False
        self.interval   = interval
        self.variance   = variance
        self.opsets     = {}
        print "BotPersonality activate!  Form of: " + self.name

    def setConnection(self, connection):
        self.connection = connection

    def pauseBot(self):
        """Stop a bot from making updates (e.g. if a connection fails)"""
        print "Pausing BotPersonality " + self.name
        self.running = False
        self.fetch_thread.cancel()

    def resumeBot(self):
        """Resume a bot (e.g. when connecting, or when reconnecting)"""
        print "Resuming BotPersonality " + self.name
        self.running = True
        self.queueBot()

    def joinedChannel(self, channel, users):
        """Called when we join a channel"""
        pass

    def setOpList(self, channel, op_set):
        self.opsets[channel] = op_set

    def addOp(self, channel, user):
        self.opsets[channel].add(user)

    def removeOp(self, channel, user):
        if user in self.opsets[channel]:
            self.opsets[channel].remove(user)

    def isOp(self, user, channel=None):
        """Determine if a given user is op in a particular channel"""
        if channel is not None:
            return user in self.opsets[channel]

        for ch in self.opsets:
            if user in self.opsets[ch]:
                return True
        return False

    def sendMessage(self, message):
        """Send a message to the configured channel"""
        self.connection.sendMessage(self, message)

    def sendPrivateMessage(self, user, message):
        """Send a direct message to a user (or a specific channel)"""
        self.connection.sendDirectMessage(self, user, message)

    def receiveMessage(self, user, message):
        """Called when a user or channel emits a message"""
        pass

    def receivePrivateMessage(self, user, message):
        """Called when another user sends a direct message"""
        pass

    def queueBot(self):
        """Queue the fetch function to run agan after 'interval' seconds"""
        # Retrigger this function, if we're still running
        if (self.running):
            delay = self.interval + random.randrange(self.variance)
            self.fetch_thread = threading.Timer(delay, self.doWorkRequeue)
            self.fetch_thread.start()

    def doWorkRequeue(self):
        self.queueBot() # Requeue in case of crash
        self.doWork()

    def doWork(self):
        print "Error: doWork not implemented"

    def parseArgsYield(self, s):
        gen = iter(s.split('"'))
        for unquoted in gen:
            for part in unquoted.split():
                yield part
            yield gen.next().join('""')

    def parseArgs(self, cmdline):
        l = []
        for a in self.parseArgsYield(cmdline):
            l.append(a.lstrip('"').rstrip('"'))
        return l


class DonBot(BotPersonality):
    """Monitor donations and announce them as they come in"""
    seen_keys = set()
    new_data = []

    def __init__(self, connection, interval, variance,
            url, reportlast=5, ignoreolderthan=3600):
        BotPersonality.__init__(self, connection, interval, variance)
        self.url                = url
        self.reportlast         = reportlast
        self.ignoreolderthan    = ignoreolderthan
        random.seed()

    def doWork(self):
        """Fetch donations from the server and announce new entries"""

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


class MicroTron(BotPersonality):
    """Act as a microphone, and make regular announcements"""

    def __init__(self, connection, interval, variance, message):
        BotPersonality.__init__(self, connection, interval, variance)
        self.message    = message

    def doWork(self):
        self.sendMessage(self.message)


class GavelMaster(BotPersonality):
    """Act as auction-master"""
    def __init__(self, connection, interval, variance):
        BotPersonality.__init__(self, connection, interval, variance)
        self.hibid          = 0
        self.increment      = 0
        self.description    = ""
        self.running        = False
        self.current_winner = ""
        self.bid_history    = []

    def doWork(self):
        pass

    def receiveMessage(self, user, message):
        bid = 0
        if not self.running:
            return

        if not message.lower().startswith("bid "):
            return

        splitted = message.split(" ")
        if (len(splitted) <= 1):
            self.sendPrivateMessage(user, "To bid, say 'bid AMMOUNT'."
                    + " For example, 'bid $10'.")
            return

        try:
            bid = int(splitted[1].strip("$,").split('.')[0])
        except:
            self.sendPrivateMessage(user, "I'm sorry, I couldn't understand "
                    + "your bid amount.")
            return

        if bid < self.hibid + self.increment:
            self.sendPrivateMessage(user, "You must bid at least $"
                    + str(self.hibid + self.increment))
            return

        self.hibid = bid
        self.current_winner = user
        self.bid_history.append((user, bid))
        self.sendMessage(user + " bids $" + str(bid)
                + " and is currently winning")

    def receivePrivateMessage(self, user, message):
        # If user is op ANYWHERE, allow it
        if not self.isOp(user):
            self.sendPrivateMessage(user, "Only ops can control this bot")
            return

        argv = self.parseArgs(message)
        if not argv or len(argv) < 1:
            self.sendHelp(user)

        elif argv[0] == "help":
            self.sendHelp(user)

        elif argv[0] == "new":
            self.addNew(user, argv)

        elif argv[0] == "abort":
            self.sendMessage("Sorry folks, we're going to stop this auction "
                    + "without a winner")
            self.running = False

        elif argv[0] == "finish":
            self.endAuction()

        elif argv[0] == "increment":
            self.updateIncrement(user, argv)

        elif argv[0] == "reject":
            self.rejectBid(user, argv)

        else:
            self.sendPrivateMessage(user,
                    "Unrecognized command '" + argv[0] + '"')
            self.sendHelp(user)

    def sendHelp(self, user):
        self.sendPrivateMessage(user,
                "Commands:"
              + "\nnew [starting bid] [description]"
              + "\nincrement [minimum increment]"
              + "\nabort"
              + "\nreject"
              + "\nfinish")

    def startAuction(self):
        self.sendMessage("We're auctioning off " + self.description)
        self.sendMessage("We'll start the auction off at $" + str(self.startbid))
        self.sayAddBid()
        self.running = True

    def endAuction(self):
        if (self.current_winner == ""):
            self.sendMessage("The auction has finished, but we had no takers")
        else:
            self.sendMessage("The auction is over!  Congratulations "
                    "to the winner, " + self.current_winner + ".")
        self.running = False

    def addNew(self, user, argv):
        if len(argv) != 3:
            self.sendPrivateMessage(user,
                                "Usage: new [starting bid] [description]")
            return

        bid = 0
        try:
            bid = int(argv[1].strip("$,").split('.')[0])
        except:
            self.sendPrivateMessage(user, "I'm sorry, I couldn't "
                    + "parse that starting bid")
            return

        self.hibid          = bid
        self.startbid       = bid
        self.description    = argv[2]
        self.current_winner = ""
        self.increment      = 1
        self.bid_history    = []
        self.startAuction()

    def updateIncrement(self, user, argv):
        inc = 0

        if len(argv) != 2:
            self.sendPrivateMessage(user, "Usage: increment [dollars]")
            return

        try:
            inc = int(argv[1].strip("$,").split('.')[0])
        except:
            self.sendPrivateMessage(user, "I couldn't parse that number")
            return

        self.increment = inc
        self.sendMessage("Bids now must be at least $" + str(inc) 
                + " more than the current high bid")

    def rejectBid(self, user, argv):
        # Inform everyone that a bid has been rejected
        if len(self.bid_history) > 0:
            (rej_user, rej_bid) = self.bid_history.pop()
            self.sendMessage("Oops, the bid from " + rej_user
                    + " has been withdrawn")

        # Either post the previous high-bid, or restart the auction
        if len(self.bid_history) > 0:
            (new_user, new_bid) = self.bid_history[-1]
            self.current_winner = new_user
            self.hibid          = new_bid
            self.sendMessage("The bid from " + new_user
                    + " at $" + str(new_bid) + " is now winning")
        else:
            self.current_winner = ""
            self.hibid          = self.startbid
            self.sendMessage("We're starting over again.  "
                    + "The opening bid is $" + str(self.startbid))
        self.sayAddBid()

    def sayAddBid(self):
        self.sendMessage("Add your bid by saying 'bid [amount]'")
