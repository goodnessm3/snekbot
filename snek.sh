#!/usr/bin/env bash
python3.6 snek2.py | tee >(grep --line-buffered "plantplant" | netcat -lkU /tmp/commsoc)