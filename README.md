cba-bot
=======

IRC bot for IGG happenings.


Configuration
=============

Configuration is normally done through Heroku environment variables, but
for local testing you can simply modify your local environment.

The bot uses a single environment variable "BOTS", which contains the URL
of a configuration file in JSON format.  It will poll this file once every
60 seconds, and if any single bot's configuration changes, that bot will be
restarted.

You can also specify an environment variable "BOTS_REFRESH" to affect
how frequently the bots JSON file is fetched from the server.

In this way, new bots can be added while the system is running live.

    cat >>test.json <<EOF
    {
                "microtron": {
                        "host": "irc.example.com",
                        "port": 6667,
                        "username": "",
                        "password": "",
                        "realname": "Example Bot",
                        "channels": ["#example", "#example2"],
                        "nick": "examplebot",
                        "personality": "microtron",
                        "interval": 60,
                        "variance": 0,
                        "message": "hello, I say"
                }
    }
    EOF

Bot types
=========

Multiple bot types are available.  Each bot has its own unique set of
parameters that must be specified in a given BOTS definition.

All bots accept the following variables:

* **host**: Hostname of the IRC server to connect to
* **port**: Port number of the IRC server (defaults to 6667)
* **username**: Username (if specified) to use with the IRC server
* **password**: Password (if specified) to use with the IRC server
* **realname**: The "real name" of the bot (optional)
* **channels**: An array of channels for the bot to enter
* **nick**: Nickname of the bot, as seen by users
* **personality**: The name of the bot to invoke
* **interval**: The minimum number of seconds to wait between messages.
* **variance**: In order to keep things interesting, a random number of
seconds (between 0 and *variance*) to add to the interval on each loop.


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
* **reportlast**: When donbot starts up, it will only report this many
old donations.
* **ignoreolderthan**: When donbot starts up, it will unconditionally
ignore messages older than this many seconds.

Microtron
---------

Microtron is small, and simply acts like a microphone.  It will blithely
repeat a given message at a regular interval.  It's not very interesting,
but it's small.

* **personality**: Must be set to "microtron"
* **message**: The message you want microtron to say

Gavelmaster
-----------

Gavelmaster has no special requirements.  It is currently localized to US
numeral systems, and expects the '.' character to be used to denote cents.
Additionally, it does not support sub-unit currencies (e.g. cents), and does
not support any currency symbol other than '$'.

Channel ops are able to control gavelmaster.  Control of the bot is done by
sending it direct messages.  If a user is op in any of the chatrooms, then
they will be able to control the bot.

To get a list of available commands, send the bot "help".  E.g. "/msg
gavelmaster help".

Note that arguments may be quoted.  That is, to supply a multi-word
description to a new auction, send:

    /msg gavelmaster new $10 "this is a multiword auction"

* **personality**: Must be set to "gavelmaster"

Pollboy
-----------

Pollboy has no special requirements.  It will monitor a channel for messages
from ops, and conduct polls.  For help on pollboy, send a private message with
the string "help".

Note that arguments may be quoted.  That is, to supply a multi-word
description to a poll option, send:

    /msg pollboy new "What are you doing?" "Watching IGG" "Playing games"

* **personality**: Must be set to "pollboy"

Debugging
---------

It is probably desirable to debug bots on your own IRC server.  Crashes and
the like will mean frequent reconnects, and this can trigger a server's
limits.  It can be handy to restart the server if necessary.

To debug the bot, add an environment variable "DEBUG" and set it to "True".

To get more information on cba-bot, run:

    pydoc ./irc-botmanager.py
