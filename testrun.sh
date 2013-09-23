#!/bin/sh
set -e
[ -e ./environment ] && . ./environment
exec python PyIRCBridge.py
