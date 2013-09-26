#!/bin/sh
set -e
[ -e ./environment ] && . ./environment
exec python irc-botmanager.py
