#!/usr/bin/env python

from cbabots import DonBot, MicroTron
import time
import os

class TestFramework():
    bots = []
    def __init__(self):
        bot = DonBot(self, 5, 2, "http://localhost/~user/file.json", 5, 144380)
        self.bots.append(bot)
        bot = MicroTron(self, 5, 2, "You're listening to KABE")
        self.bots.append(bot)

    def pause(self):
        for bot in self.bots:
            bot.pauseBot()

    def resume(self):
        for bot in self.bots:
            bot.resumeBot()

    def sendMessage(self, bot, message):
        print ">>> Message from " + bot.name + ": " + message

if __name__ == '__main__':
    print "Loading test framework..."
    tests = TestFramework()

    print "Resuming tests..."
    tests.resume()

    print "Waiting on the test framework..."
    time.sleep(15)

    print "Done.  Quitting!"
    os._exit(0)
