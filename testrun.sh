#!/bin/sh
set -e
[ -e ./environment ] && . ./environment
exec python cba-bot.py
