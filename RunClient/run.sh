#!/usr/bin/env sh
cd "$(dirname "$0")/../Scripts/client" || exit 1
python client.py
status=$?
if [ "$status" -ne 0 ]; then
    printf 'Press Enter to close...'
    read _
fi