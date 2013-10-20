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

    def __init__(self, connection, interval, variance, cmdurl):
        self.name         = self.__class__.__name__
        self.connection   = connection
        self.running      = False
        self.interval     = interval
        self.variance     = variance
        self.opsets       = {}
        self.cmdurl       = cmdurl
        self.lastid       = 0
        self.fetch_thread = None
        print "BotPersonality activate!  Form of: " + self.name

    def setConnection(self, connection):
        self.connection = connection

    def pauseBot(self):
        """Stop a bot from making updates (e.g. if a connection fails)"""
        print "Pausing BotPersonality " + self.name
        self.running = False
        if self.fetch_thread is not None:
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
        self.connection.sendMessage(self, message.encode('ascii', 'ignore'))

    def sendPrivateMessage(self, user, message):
        """Send a direct message to a user (or a specific channel)"""
        if user is None:
            # This happens e.g. when a command comes from the web
            print "Message not delivered, user was None:"
            print message
            return
        self.connection.sendDirectMessage(self, user, message.encode('ascii', 'ignore'))

    def receiveMessage(self, user, message):
        """Called when a user or channel emits a message"""
        pass

    def receivePrivateMessage(self, user, message):
        """Called when another user sends a direct message"""
        pass

    def queueBot(self):
        """Queue the fetch function to run agan after 'interval' seconds"""
        delay = self.interval + random.randrange(self.variance)
        self.fetch_thread = threading.Timer(delay, self.doWorkRequeue)
        self.fetch_thread.start()

    def doWorkRequeue(self):
        if (self.running):
            self.queueBot() # Requeue in case of crash
            self.executeCmd()
            self.doWork()

    def doWork(self):
        print "Error: doWork not implemented"

    def executeCmd(self):
        cmds = {}
        if self.cmdurl is None:
            return

        try:
            cmds = loads(urlopen(self.cmdurl).read())
        except:
            print "Couldn't load JSON"
            return

        # Re-sort the data by timestamp
        cmds = sorted(cmds, key=lambda cmd: int(cmd['id']))

        # Ignore the very first command.  Since IDs are monotonically
        # increasing, this will allow us to ignore all commands that
        # actually happened in the past.
        if self.lastid == 0:
            if len(cmds) > 0:
                self.lastid = int(cmds[-1]["id"])
            return

        if len(cmds) == 0:
            return

        # Make sure the new command is, indeed, new
        if int(cmds[-1]["id"]) <= self.lastid:
            return

        # Success.  Execute the command.
        self.lastid = int(cmds[-1]["id"])
        arr = []
        for arg in cmds[-1]["command"]:
            arr.append(arg.encode('ascii', 'ignore'))
        return self.adminCommand(None, arr)

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

    def adminCommand(self, user, args):
        return


class DonBot(BotPersonality):
    """Monitor donations and announce them as they come in"""
    seen_keys = set()
    new_data = []

    def __init__(self, connection, interval, variance, cmdurl,
            url, reportlast=5, ignoreolderthan=3600):
        BotPersonality.__init__(self, connection, interval, variance, cmdurl)
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
        data = loads(urlopen(self.url).read())
        for donation in data:
            timestamp = strict_rfc3339.rfc3339_to_timestamp(donation['time'] \
                    + "-07:00")
            donation['timestamp'] = timestamp
            if donation['pk'] not in self.seen_keys:
                self.new_data.append(donation)

        # Re-sort the data by timestamp
        self.new_data = sorted(self.new_data,
                                key=lambda donation: donation['timestamp'])
        self.new_data.reverse()

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
                newobj = {}
                newobj['timestamp'] = obj['timestamp']
                newobj['name']      = obj['name'].encode('ascii', 'ignore')
                newobj['amount']    = obj['amount'].encode('ascii', 'ignore')
                newobj['game']      = obj['game'].encode('ascii', 'ignore')
                newobj['pk']        = obj['pk']
                if (now - float(obj['timestamp'])) >= self.ignoreolderthan:
                    self.seen_keys.add(obj['pk'])
                elif len(trimmed_list) >= self.reportlast:
                    self.seen_keys.add(obj['pk'])
                else:
                    trimmed_list.append(newobj)

            self.new_data = trimmed_list
            self.new_data.reverse()
            
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

    def __init__(self, connection, interval, variance, cmdurl, message):
        BotPersonality.__init__(self, connection, interval, variance, cmdurl)
        self.message    = message

    def doWork(self):
        self.sendMessage(self.message)


class GavelMaster(BotPersonality):
    """Act as auction-master"""
    isRunning = False
    bidAmountNotFound = "To bid, say 'bid AMMOUNT'. For example, 'bid $10'."
    bidErrorString = "I'm sorry, I couldn't understand your bid amount."
    bidNotEnough = "You must bid at least $%s"
    bidNewLeader = "%s bids $%s and is currently winning"
    youAreNotOps = "Only ops can control this bot"
    abortAuction = "Sorry folks, we're going to stop this auction without a winner"
    startAuction1 = "We're auctioning off %s"
    startAuction2 = "We'll start the auction off at $%s"
    endAuctionNoWinner = "The auction has finished, but we had no takers"
    endAuctionWinner = "The auction is over!  Congratulations to the winner, %s."
    newIncrement = "Bids now must be at least $%s more than the current high bid"
    withdrawBid = "Oops, the bid from %s has been withdrawn"
    withdrawBidNewWinner = "The bid from %s at $%s is now winning"
    withdrawBidStartOver = "We're starting over again.  The opening bid is $%s"

    # These two must match
    addBidMessage = "Add your bid by saying 'bid [amount]'"
    bidPrefix = "bid"

    def __init__(self, connection, interval, variance, cmdurl):
        BotPersonality.__init__(self, connection, interval, variance, cmdurl)
        self.hibid          = 0
        self.increment      = 0
        self.description    = ""
        self.isRunning      = False
        self.current_winner = ""
        self.bid_history    = []

    def doWork(self):
        pass

    def auctionActive(self):
        if self.isRunning == True:
            return True
        return False

    def setAuctionActive(self, isRunning):
        self.isRunning = isRunning

    def receiveMessage(self, user, message):
        bid = 0
        if not self.auctionActive():
            return

        if not message.lower().startswith(self.bidPrefix + " "):
            return

        splitted = message.split(" ")
        if (len(splitted) <= 1):
            self.sendPrivateMessage(user, self.bidAmountNotFound)
            return

        try:
            bid = int(splitted[1].strip("$,").split('.')[0])
        except:
            self.sendPrivateMessage(user, self.bidErrorString)
            return

        if bid == self.hibid and len(self.bid_history) == 0:
            pass
        elif bid < self.hibid + self.increment:
            self.sendPrivateMessage(user, self.bidNotEnough %
                    + str(self.hibid + self.increment))
            return

        self.hibid = bid
        self.current_winner = user
        self.bid_history.append((user, bid))
        self.sendMessage(self.bidNewLeader % (user, str(bid)))

    def receivePrivateMessage(self, user, message):
        # If user is op ANYWHERE, allow it
        if not self.isOp(user):
            self.sendPrivateMessage(user, self.youAreNotOps)
            return

        return self.adminCommand(user, self.parseArgs(message))

    def adminCommand(self, user, argv):
        if not argv or len(argv) < 1:
            self.sendHelp(user)

        elif argv[0] == "help":
            self.sendHelp(user)

        elif argv[0] == "new":
            self.addNew(user, argv)

        elif argv[0] == "abort":
            self.sendMessage(self.abortAuction)
            self.setAuctionActive(False)

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
        self.sendMessage(self.startAuction1 % self.description)
        self.sendMessage(self.startAuction2 % str(self.startbid))
        self.sayAddBid()
        self.setAuctionActive(True)

    def endAuction(self):
        if (self.current_winner == ""):
            self.sendMessage(self.endAuctionNoWinner)
        else:
            self.sendMessage(self.endAuctionWinner % self.current_winner)
        self.setAuctionActive(False)

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
        self.sendMessage(self.newIncrement % str(inc))

    def rejectBid(self, user, argv):
        # Inform everyone that a bid has been rejected
        if len(self.bid_history) > 0:
            (rej_user, rej_bid) = self.bid_history.pop()
            self.sendMessage(self.withdrawBid % rej_user)

        # Either post the previous high-bid, or restart the auction
        if len(self.bid_history) > 0:
            (new_user, new_bid) = self.bid_history[-1]
            self.current_winner = new_user
            self.hibid          = new_bid
            self.sendMessage(self.withdrawBidNewWinner % (new_user, str(new_bid)))
        else:
            self.current_winner = ""
            self.hibid          = self.startbid
            self.sendMessage(self.withdrawBidStartOver % str(self.startbid))
        self.sayAddBid()

    def sayAddBid(self):
        self.sendMessage(self.addBidMessage)


class PollBoy(BotPersonality):
    """Perform an informal poll in the channel"""
    isRunning = False
    votePrefix = "vote"
    voteNotRecognized = "To vote, say 'vote [number]'. For example, 'vote 2'."
    voteCommandHelp = "Say 'vote [number] to vote"
    voteNotANumber = "I'm sorry, I couldn't understand your vote."
    voteOutOfRange = "Please vote on a number between 1 and %s"
    youAreNotOps = "Only ops can control this bot"
    startPollMessage = "We want to know: %s"
    resultsStart = "Results:"
    resultsLine = "%s    %s"

    def __init__(self, connection, interval, variance, cmdurl):
        BotPersonality.__init__(self, connection, interval, variance, cmdurl)
        self.description    = ""
        self.isRunning      = False
        self.current_winner = ""
        self.options        = []
        self.votes          = {}

    def doWork(self):
        pass

    def pollActive(self):
        if self.isRunning == True:
            return True
        return False

    def setPollActive(self, isRunning):
        self.isRunning = isRunning

    def receiveMessage(self, user, message):
        choice = 0
        if not self.pollActive():
            return

        if not message.lower().startswith(self.votePrefix + " "):
            return

        splitted = message.split(" ")
        if (len(splitted) <= 1):
            self.sendPrivateMessage(user, self.voteNotRecognized)
            return

        try:
            choice = int(splitted[1])-1
        except:
            self.sendPrivateMessage(user, self.voteNotANumber)
            return

        if choice < 0 or choice > len(self.options)-1:
            self.sendPrivateMessage(user, self.voteOutOfRange % str(len(self.options)))
            return

        self.votes[user] = choice

    def receivePrivateMessage(self, user, message):
        # If user is op ANYWHERE, allow it
        if not self.isOp(user):
            self.sendPrivateMessage(user, self.youAreNotOps)
            return

        return self.adminCommand(user, self.parseArgs(message))

    def adminCommand(self, user, argv):
        if not argv or len(argv) < 1:
            self.sendHelp(user)

        elif argv[0] == "help":
            self.sendHelp(user)

        elif argv[0] == "new":
            self.addNew(user, argv)

        elif argv[0] == "finish":
            self.endPoll()

        elif argv[0] == "reject":
            self.rejectPoll(user, argv)

        else:
            self.sendPrivateMessage(user,
                    "Unrecognized command '" + argv[0] + '"')
            self.sendHelp(user)

    def sendHelp(self, user):
        self.sendPrivateMessage(user,
                "Commands:"
              + "\nnew [poll name] [option 1] [option 2] [...]"
              + "\nreject [nick]"
              + "\nfinish")

    def startPoll(self):
        self.sendMessage(self.startPollMessage % self.description)
        for i in range(0, len(self.options)):
            self.sendMessage(str(int(i+1)) + ": " + self.options[i])
        self.sendMessage(self.voteCommandHelp)
        self.setPollActive(True)

    def endPoll(self):
        totals = {}
        results = []
        for key in self.options:
            totals[key] = {}
            totals[key]['count'] = 0
            totals[key]['name'] = key

        for option in self.votes.values():
            totals[self.options[option]]['count'] = totals[self.options[option]]['count'] + 1

        results = sorted(totals, key=lambda tot: tot['count'])

        self.sendMessage(self.resultsStart)
        for tot in results:
            self.sendMessage(self.resultsLine % (str(tot['count']), tot['name']))
        self.setPollActive(False)

    def addNew(self, user, argv):
        if len(argv) < 4:
            self.sendPrivateMessage(user,
                        "Usage: new [description] [option 1] [option 2] [...]")
            return

        del self.options[:]
        for i in range(2, len(argv)):
            self.options.append(argv[i])

        self.votes.clear()
        self.startPoll()

    def rejectPoll(self, user, argv):
        if len(argv) != 2:
            self.sendMessage("Usage: reject [username]")
            return

        if argv[1] in self.votes:
            del self.votes[argv[1]]
        else:
            self.sendMessage("User " + argv[1] + " hasn't voted")

class Bottob(BotPersonality):
    """Mirror messages between all configured bottob bots"""
    activeBottobs = set()

    def __init__(self, connection, interval, variance, cmdurl):
        BotPersonality.__init__(self, connection, interval,
                                variance, cmdurl)

    def doWork(self):
        pass

    def pauseBot(self):
        BotPersonality.pauseBot(self)
        self.activeBottobs.discard(self)

    def resumeBot(self):
        BotPersonality.resumeBot(self)
        self.activeBottobs.add(self)

    def receiveMessage(self, user, message):
        print "Received message from " + user + ": " + message
        # Ignore messages from ourselves.
        if user == self.connection.getNick():
            return

        # Send a message to all other active bots
        for bot in self.activeBottobs:
            if bot.connection.getName() == self.connection.getName():
                continue
            bot.sendMessage(user + ": " + message)
