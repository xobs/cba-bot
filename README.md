cba-bot
=======

IRC bot for IGG happenings.


Configuration
-------------

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
                                "channels": ["#example"],
                                "nick": "examplebot",
                                "host": "irc.example.com",
                                "port": 6667,
    				"personality": "roboto",
    				"url": "http://example.com/words.json"}}'
    export MSGPERIOD="15"
    export POLLRATE="10"
    EOF

Debugging
---------

To debug the bot, add an environment variable "DEBUG" and set it to "True".

To get more information on cba-bot, run:

    pydoc ./cba-bot.py
