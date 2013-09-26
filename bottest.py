#!/usr/bin/env python

from cbabots import DonBot
import time
import os

class TestFramework():
    bots = []
    def __init__(self):
        bot = DonBot(self, "cloudboatarmada",
                    "http://localhost/~user/file.json", 1, 1)
        self.bots.append(bot)

    def pause(self):
        for bot in self.bots:
            bot.pauseBot()

    def resume(self):
        for bot in self.bots:
            bot.resumeBot()

    def sendMessage(self, bot, channel, message):
        print "Message from " + bot.name \
                + " to channel " + channel + ": " \
                + message

if __name__ == '__main__':
    print "Loading test framework..."
    tests = TestFramework()

    print "Resuming tests..."
    tests.resume()

    print "Waiting on the test framework..."
    time.sleep(15)

    print "Done.  Quitting!"
    os._exit(0)
