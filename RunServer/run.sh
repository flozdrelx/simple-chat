#!/usr/bin/env sh
cd "$(dirname "$0")/../Scripts/server" || exit 1
python server.py
status=$?
if [ "$status" -ne 0 ]; then
    printf 'Press Enter to close...'
    read _
fi