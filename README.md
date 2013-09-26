cba-bot
=======

IRC bot for IGG happenings.


Configuration
=============

Configuration is normally done through Heroku environment variables, but
for local testing you can simply modify your local environment.

To avoid polluting your setup, place all environment variables into a file
called "environment", and then run "testrun.sh".  To create such a file,
run a command such as:

    cat >>environment <<EOF
    export INITTIME=0
    export IRCSERVERS='{"TTV": {"username": "",
                                "password": "",
                                "realname": "Example Bot",
                                "channels": ["#example", "#example2"],
                                "nick": "examplebot",
                                "host": "irc.example.com",
                                "port": 6667,
    				"personality": "roboto",
    				"url": "http://example.com/words.json"}}'
    EOF

Bot types
=========

Multiple bot types are available.  Each bot has its own unique set of
parameters that must be specified in a given IRCSERVER definition.


Donbot
------

The donbot monitors donations.  It will poll a URL at a given rate (with a
given variance), look for new primary keys, and relay those donations to
all configured channels.  When it starts up, it will limit its initial
broadcast to at most a few donations, none of which may be older than a
certain timeframe.

If more than one donation comes in between polls, then donbot will sort all
new donations and then emit them in lieu of connecting the server.  That
is, if two new donations are retrieved during a URL poll, then one message
will be emitted to IRC, and then donbot will sleep.  When it wakes up
again, instead of polling the server for new donations, it will skip this
step and simply post the second message to IRC.

Variables:

* **personality**: Must be set to "donbot"
* **url**: The JSON URL to fetch donations from
* **interval**: The minimum number of seconds to wait between messages.
* **variance**: In order to keep things interesting, a random number of
seconds to add to the interval period
* **reportlast**: When donbot starts up, it will only report this many
old donations.
* **ignoreolderthan**: When donbot starts up, it will unconditionally
ignore messages older than this many seconds.


Debugging
---------

To debug the bot, add an environment variable "DEBUG" and set it to "True".

To get more information on cba-bot, run:

    pydoc ./irc-botmanager.py
