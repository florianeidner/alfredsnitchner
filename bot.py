#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import time
from datetime import datetime
from pytz import timezone
import json
import threading
import requests
from random import randint
import logging

import telepot
from telepot.loop import MessageLoop

from wit import Wit

from tinydb import TinyDB, Query


#Setup
logging.getLogger().setLevel(logging.DEBUG)

alfred = telepot.Bot(os.environ['ALFRED_API_TOKEN'])
nlp = Wit(access_token=os.environ['WIT_API_TOKEN'])
weatherToken = os.environ['WEATHER_API_TOKEN']
runDir = os.environ['RUN_DIR'] #This one sets the directory where bot.py is located, so we can use relative paths
allowedChats= os.environ['ALLOWED_CHATS'].split(",")
if not allowedChats: #If no delimiter "," was found
	allowedChats = os.environ['ALLOWED_CHATS']

quotes=json.load(open(runDir+"media/quotes.json","r"))

db = TinyDB('db.json')
queue = {}

startTime = time.time()

#Utilities
def getUptime():
	seconds = (time.time() - startTime)
	m, s =divmod(seconds, 60)
	h, m = divmod(m, 60)
	uptime = str("%d:%02d:%02d" %(h,m,s))
	return uptime

def getTimestamp():
#	tz='Europe/Berlin'
#	year = datetime.now(timezone(tz)).strftime('%Y')
#	month = datetime.now(timezone(tz)).strftime('%m')
#	day = datetime.now(timezone(tz)).strftime('%d')
#	timestamp={'year':year,'month':month,'day':day}
	timestamp=time.time()
	return timestamp

def tail(file, lines=20, _buffer=4098):
    #Tail a file and get X lines from the end
    #place holder for the lines found
    f=open(file,'r')
    lines_found = []

    # block counter will be multiplied by buffer
    # to get the block size from the end
    block_counter = -1

    # loop until we find X lines
    while len(lines_found) < lines:
        try:
            f.seek(block_counter * _buffer, os.SEEK_END)
        except IOError:  # either file is too small, or too many lines requested
            f.seek(0)
            lines_found = f.readlines()
            break

        lines_found = f.readlines()

        # we found enough lines, get out
        if len(lines_found) > lines:
            break

        # decrement the block counter to get the
        # next X bytes
        block_counter -= 1

    return lines_found[-lines:]

def getChuckNorrisFact():
	r=requests.get("https://api.chucknorris.io/jokes/random")
	fact = r.json()['value']
	return fact

awaitingConfirmation = False

degree_sign= u'\N{DEGREE SIGN}'

weatherEmojis = {
	'thunderstorm' : u'\U0001F4A8',		# Code: 200's, 900, 901, 902, 905
	'drizzle' : u'\U0001F4A7',			# Code: 300's
	'rain' : u'\U00002614',				# Code: 500's
	'snowflake' : u'\U00002744',		# Code: 600's snowflake
	'snowman' : u'\U000026C4',			# Code: 600's snowman, 903, 906
	'atmosphere' : u'\U0001F301',		# Code: 700's foogy
	'clearSky' : u'\U00002600',			# Code: 800 clear sky
	'fewClouds' : u'\U000026C5',		# Code: 801 sun behind clouds
	'clouds' : u'\U00002601',			# Code: 802-803-804 clouds general
	'hot' : u'\U0001F525',  			# Code: 904
	'defaultEmoji' : u'\U0001F300'		# default emojis
	}

#Forward all messages to Bot
messageForward=False

def forceNextMessages(duration):
	print "turn ON message forwarding"
	global messageForward
	messageForward = True
	threading.Timer(duration,unforceNextMessages).start()

def unforceNextMessages():
	print "turn OFF message forwarding"
	global messageForward
	messageForward = False

#Actions that shall be taken after an intent was detected.
def actionIntro(chatId,msgSender,attributes):
	print "I will tell you something about me"
	alfred.sendMessage(chatId,"Hej, ich bin Alfred")

def actionAddExpense(chatId,msgSender,attributes):
	print "I will add an Expense"
	amount = attributes['entities']['amount_of_money'][0]['value']
	if attributes['entities'].has_key('contact'):
		person = attributes['entities']['contact'][0]['value']

		if "mein" in person or "ich" in person or "Mein" in person or "Ich" in person:
			person = msgSender
		if "toni" in person or "Toni" in person:
			person = "Antonia"
		if "flo" in person or "Flo" in person:
			person = "Florian"
	else:
		print"who made the expense?"
		person = msgSender

	answer = "Ok, soll ich " +str(amount)+ "EUR zu "+person+"'s Ausgaben hinzufuegen?"
	alfred.sendMessage(chatId,answer)

	if attributes['entities'].has_key('spending_type'):
		category = attributes['entities']['spending_type']['value']

	else:
		category = "/"


	args = {'person':person,'amount':amount,'category':category}
	addCommand(dbAddExpense,args)

	global awaitingConfirmation
	awaitingConfirmation = True

	forceNextMessages(20)

def actionConfirm(chatId,msgSender,attributes):
	print "Action confirmed"
	global awaitingConfirmation
	if (awaitingConfirmation == True):
		execCommand()
		alfred.sendMessage(chatId,"Ok, wird gemacht.")
		awaitingConfirmation = False
	else:
		print "Nothing to do here"

def actionDiscard(chatId,msgSender,attributes):
	print "Action discarded"
	alfred.sendMessage(chatId, "Na gut, dann eben nicht!")

def actionGreeting(chatId,msgSender,attributes):
	print "Saying hello"
	hello = "Hallo, " + msgSender
	alfred.sendMessage(chatId,hello)
	if ((randint(1,50))<20):
		cmdQuote(chatId)

	forceNextMessages(20)

def actionGetBalance(chatId,msgSender,attributes):
	print "Lets see who owns money"
	balance=dbGetBalance(msgSender)
	message="Ihr habt seit der letzten Abrechnung insgesamt "+str(balance['Total'])+"EUR ausgegeben\n"
	if (balance['Outstanding'] < 0):
		message = message + msgSender+", du bekommst noch " +str((-1)*(balance['Outstanding']))+"EUR."

	elif (balance['Outstanding'] >0):
		message = message + msgSender+", du musst noch " +str(balance['Outstanding'])+"EUR ueberweisen."

	elif (balance['Outstanding'] ==0):
		message = message + "Ihr seid quit!"

	alfred.sendMessage(chatId,message)

def actionSetCut(chatId,msgSender,attributes):
	print "Lets call it a draw"
	alfred.sendMessage(chatId,"Ihr seid quit?")
	addCommand(dbSetCut,{'sender':msgSender})
	global awaitingConfirmation
	awaitingConfirmation = True
	forceNextMessages(20)

def actionGetExpenses(chatId,msgSender,attributes):
	print "Lets see what was spent."
	period = 100000
	expenses = dbGetExpenses(period)
	message="Also, Ihr habt folgendes ausgegeben:"
	for expense in expenses:
		message=message+str(expense['date'])+" - *"+str(expense['amount'])+"EUR*  "+expense['account']+" - _"+expense['category']+"_\n"

	if (message == "Also, Ihr habt folgendes ausgegeben:"):
		message = "Ihr habt seid der letzten Abrechnung nichts ausgegeben."
	alfred.sendMessage(chatId,message,parse_mode='Markdown')

def actionMakePayment(chatId,msgSender,attributes):
	balance= dbGetBalance(msgSender)
	paymentAddress = {'Florian':'paypal.me/florianeidner/','Antonia':'paypal.me/dieterle/'}

	if (balance['Outstanding'] > 0):
		message="Du musst " + str(balance['Outstanding'])+"EUR ueberweisen.\n"
		if msgSender=="Florian":
			link = paymentAddress['Antonia']
		else:
			link = paymentAddress['Florian']

		message = message+"Hier ist der Link: "+link+str(balance['Outstanding'])
	else:
		message="Du hast nichts zu bezahlen."

	alfred.sendMessage(chatId,message)

def actionGetWeather(chatId,msgSender,attributes):
	print "Talk to weather bot"
	location_not_found=False

	if attributes['entities'].has_key('location'):
		location = attributes['entities']['location'][0]['value']
	else:
		location="München"

	r = requests.get('https://dataservice.accuweather.com/locations/v1/cities/autocomplete',params={'apikey':weatherToken,'q':location,'language':'de-de'})
	if r.json()[0].has_key('Code') and r.json()['Code']=="ServiceUnavailable":
		alfred.sendMessage(chatId,"Der Wetterservice ist momentan nicht verfügbar.")

	elif bool(r.json())==False:
		alfred.sendMessage(chatId,"Für den Ort find ich keine Wetterdaten")
		weather = (-1)
	else:
		city = r.json()[0]['LocalizedName']
		country = r.json()[0]['Country']['LocalizedName']
		locationKey = r.json()[0]['Key']
		message= "Hier kommt das Wetter fuer "+city+", "+country+":"
		alfred.sendMessage(chatId,message)
		url="http://dataservice.accuweather.com/forecasts/v1/daily/1day/"+locationKey
		r = requests.get(url,params={'apikey':weatherToken,'language':'de-de','details':'false','metric':'true'})
		headline = r.json()['Headline']['Text']
		weatherLink = r.json()['Headline']['Link']
		weatherCategory = r.json()['Headline']['Category']
		tempMin = r.json()['DailyForecasts'][0]['Temperature']['Minimum']['Value']
		tempMax = r.json()['DailyForecasts'][0]['Temperature']['Maximum']['Value']
		#weatherIcon = r.json()['DailyForecasts'][0]['Day']['Icon']
		weatherPhrase = r.json()['DailyForecasts'][0]['Day']['IconPhrase']
		#Sending weather stickers instead of emojis
		#filename=runDir+"weather_icons/"+str(weatherIcon)+"-s.png"
		#iconFile=open(filename,'r')
		#alfred.sendPhoto(chatId,filename)
		if weatherEmojis.has_key(weatherCategory):
			emoji = weatherEmojis[weatherCategory]
		else:
			emoji = u'\U0001F300'
		message = emoji+emoji+emoji+emoji+emoji+emoji+emoji+emoji+emoji+emoji+"\n*"+headline+"*\n"+weatherPhrase+" bei tagsueber zwischen "+str(tempMin)+degree_sign+"C bis "+str(tempMax)+degree_sign+"C\nMehr Infos unter: "+weatherLink
		alfred.sendMessage(chatId,message,parse_mode="Markdown")


def actionNotLearned(chatId,intent):
	emoji = u'\U0001F622'
	message = intent+" - Da hat mir noch niemand gesagt was ich machen soll."+u'\U0001F622'
	alfred.sendMessage(chatId,message)

intentActions = {
	"introduction": actionIntro,
	"addExpense": actionAddExpense,
	"confirm": actionConfirm,
	"discard": actionDiscard,
	"hello": actionGreeting,
	"balance" : actionGetBalance,
	"cut" : actionSetCut,
	"expenses":actionGetExpenses,
	"pay":actionMakePayment,
	"weather":actionGetWeather}

def cmdPrintError(chatId):
	errorLog= "/var/log/alfredsnitchner.err.log"
	log=tail(errorLog,20)
	message="*Ok, hier sind die letzten Logs:*\n"
	for line in log:
		message = message+line

	alfred.sendMessage(chatId,message,parse_mode="Markdown")

def cmdShowHelp(chatId):
	message = "Folgende Befehle kannst du mir geben:\n"
	for cmd in commands:
		message+=("  /"+cmd+"\n")
	alfred.sendMessage(chatId,message)

def cmdRestart(chatId):
	alfred.sendMessage(chatId,"Ciao,bis gleich!")
	os.system("supervisorctl restart alfredsnitchner")

def cmdReset(chatId):
	args={}
	addCommand(dbPurgeAll,args)
	alfred.sendMessage(chatId,"Soll ich die Datenbank bereinigen?")

	global awaitingConfirmation
	awaitingConfirmation = True

	forceNextMessages(20)

def cmdQuote(chatId):
	length = len(json.loads(quotes))
	quote=quotes[str((randint(1, length)))]
	quote=quote+" _B. Springsteen_"
	alfred.sendMessage(chatId,quote,parse_mode="Markdown")
	alfred.sendMessage(chatId,"Just saying.")

def cmdStatus(chatId):

	message = "Dieser Chat hat folgende ID: "+str(chatId)+"\nErlaubte Chats:\n"
	for allowedChat in allowedChats:
		message=message+"   "+allowedChat+"\n"

	message = message+"\nIch bin jetzt seit "+str(getUptime())+ " online!"
	alfred.sendMessage(chatId,message)


commands = {
	"errors" : cmdPrintError,
	"help" : cmdShowHelp,
	"restart" : cmdRestart,
	"reset": cmdReset,
	"quote": cmdQuote,
	"status":cmdStatus}


#Queue commands
def addCommand(function, args):
	global queue
	queue={'function':function,
		'arguments':args}
	print "Added command to queue"

def execCommand():
	if (queue != {}):
		queue['function'](**queue['arguments'])
		print "Executed command"
		clearQueue();
	else:
		print "No command executed, queue was empty"

def clearQueue():
	global queue
	queue={}
	print "Queue cleared"


#Database
def dbAddExpense(person,amount,category):
	db.insert({'type':'expense','date':getTimestamp(),'account':person,'amount':amount,'category':category})

def dbSetCut(sender):
	db.insert({'type':'cut','date':getTimestamp()})

def dbGetExpenses(period):
	print "Listing the expenses in that period"
	events = Query()
	expenses = db.search((events.type=='expense') & (events.date > (getTimestamp()-period)))
	i=0
	expensesOptimized =[]
	for expense in expenses:
		expensesOptimized.append({'date':datetime.fromtimestamp(expense['date']).strftime('%d.%m.'),'account':expense['account'],'amount':expense['amount'],'category':expense['category']})
		i += 1
		print i
	print expensesOptimized
	return expensesOptimized

def dbGetBalance(sender):
	print "Calculating balance"
	events = Query()
	dateLastCut=0
	expenses= {'Antonia':0,'Florian':0,'Total':0,'Outstanding':0}
	for cut in db.search(events.type=='cut'):
		if (cut['date'] > dateLastCut):
			dateLastCut=cut['date']

	for expense in db.search((events.type=='expense') & (events.date > dateLastCut)):
		expenses[expense['account']] += expense['amount']
		expenses['Total']+=expense['amount']

	expenses['Outstanding'] = ((expenses['Total']/2)-expenses[sender])
	return expenses

def dbPurgeAll():
	db.purge()

#Handle incoming messages.

def handleMessage(msg):
	
	logging.info('Message received')
	logging.debug('Message:'+str(msg))
	try:
		chatId = msg['chat']['id']
		msgContent = msg['text']
		msgSender = msg['from']['first_name']
	except:
		logging.warning('Couldnt extract Chat ID, Content or Sender from message.')

	if ((str(chatId) in allowedChats) or ("ALL" in allowedChats)):
		logging.info('Message from allowed Chat. Starting the handling...')
		if "/" in msgContent:
			logging.info('Message is a command. Extracting command...')
			cmd = msgContent[msgContent.find("/")+1:].split()[0]
			if commands.has_key(cmd): # and (msgSender=='Florian'):
				message = "JAWOHL!"+u'\U0001F4A9'
				alfred.sendMessage(chatId,message)
				commands[cmd](chatId)
			else:
				alfred.sendMessage(chatId,"Den Befehl kenn ich nicht.")

		else:
			logging.info('Lets see if I was mentioned... - Message forwarding is:' + str(messageForward))

			if "alfred" in msgContent or "Alfred" in msgContent or(messageForward == True):
				logging.info('Ok i heard my name or forwarding is turned on. I will try to parse the message...')
				resp = nlp.message(msgContent)
				if resp['entities'].has_key('intent'):
					intent = resp['entities']['intent'][0]['value']
					logging.info('The NLP detected an intent.')
					logging.debug(str(resp))
					
					if intentActions.has_key(intent):
						logging.info('Intent: '+ str(intent)+" - I know what to do.")
						intentActions[intent](chatId,msgSender,resp)
					else:
						logging.info('Intent: '+ str(intent)+" - You didnt tell me what to do yet.")
						actionNotLearned(chatId,intent)
				else:
					logging.info('No idea what that means, lets reply with a random quote...')

					chuckFact=getChuckNorrisFact()

					message = "Mmmh. Keine Ahnung was du willst, aber wusstest du:\n_" + chuckFact+"_"
					alfred.sendMessage(chatId,message,parse_mode="Markdown")
					if messageForward == False:
						forceNextMessages(10)
	else:
		logging.info('This chatId is not allowed.')
		
		logmsg= 'This ID: '+ chatId +'\nAllowed: '
		for allowedChat in allowedChats:
			logmsg = logmsg+str(allowedChat)+", "
		logging.debug(logmsg)

		message = "In diesem Chat darf ich nicht antworten. Der Chat hat die ID "+str(chatId)
		alfred.sendMessage(chatId,message)

MessageLoop(alfred,handleMessage).run_as_thread()

while 1:
	time.sleep(10)
