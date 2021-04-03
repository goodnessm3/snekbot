#!/usr/bin/env/bash
# note only works on snek's specific server with the specific python3.6 installation
echo "Updating and restarting"
git pull
python3.6 snek2.py