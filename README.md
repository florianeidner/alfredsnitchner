# alfredsnitchner
The ultimate butler.

## Setup

To get it up and running you need to set a few environmental variables. If this script is run via supervisor the config file can look like this:
```
[program: alfredsnitchner]
environment =
	ALFRED_API_TOKEN="XXXXXXXXXXXXXXXX",                      #Telegram bot token
	WIT_API_TOKEN="XXXXXXXXXXXXXX",                           #NLP wit.ai token
	WEATHER_API_TOKEN="XXXXXXXXXXXXXXXXXXX",                  #ACCU Weather api token
	RUN_DIR="/home/florianeidner/projects/alfredsnitchner/",  #Path to running dir to use relative paths
	ALLOWED_CHATS="CHATID1,CHATID2"                           #include "ALL" to open to all chatIDs
	
command = /home/florianeidner/projects/alfredsnitchner/bot.py

autostart=true
autorestart=unexpected

stderr_logfile=/var/log/alfredsnitchner.err.log
stdout_logfile=/var/log/alfredsnitchner.out.log
```

## Functions

### Introduction
