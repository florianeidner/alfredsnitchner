#!/usr/bin/python
# -*- coding: utf-8 -*-
import os
import time
from datetime import datetime
from pytz import timezone
import json
import threading
import requests

import telepot
from telepot.loop import MessageLoop

from wit import Wit

from tinydb import TinyDB, Query


#Setup
alfred = telepot.Bot(os.environ['ALFRED_API_TOKEN'])
nlp = Wit(access_token=os.environ['WIT_API_TOKEN'])
weatherToken = os.environ['WEATHER_API_TOKEN']
runDir = os.environ['RUN_DIR'] #This one sets the directory where bot.py is located, so we can use relative paths

db = TinyDB('db.json')
queue = {}

#Utilities
def getTimestamp():
#	tz='Europe/Berlin'
#	year = datetime.now(timezone(tz)).strftime('%Y')
#	month = datetime.now(timezone(tz)).strftime('%m')
#	day = datetime.now(timezone(tz)).strftime('%d')
#	timestamp={'year':year,'month':month,'day':day}
	timestamp=time.time()
	return timestamp

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
	category = "No"
	alfred.sendMessage(chatId,answer)
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
	alfred.sendMessage(chatId,"Also, Ihr habt folgendes ausgegeben:")
	expenses = dbGetExpenses(period)
	message=""
	for expense in expenses:
		message=message+str(expense['date'])+" - *"+str(expense['amount'])+"EUR*  "+expense['account']+" - _"+expense['category']+"_\n"

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
	if attributes['entities'].has_key('location'):
		location = attributes['entities']['location'][0]['value']
	else:
		location="München"

	r = requests.get('https://dataservice.accuweather.com/locations/v1/cities/autocomplete',params={'apikey':weatherToken,'q':location,'language':'de-de'})
	if r.json() = None:
		location ="München"
		r = requests.get('https://dataservice.accuweather.com/locations/v1/cities/autocomplete',params={'apikey':weatherToken,'q':location,'language':'de-de'})

	city = r.json()[0]['LocalizedName']
	country = r.json()[0]['Country']['LocalizedName']
	locationKey = r.json()[0]['Key']

	message= "Hier kommt das Wetter für "+city+", "+country+":"
	alfred.sendMessage(chatId,message)

	url="http://dataservice.accuweather.com/forecasts/v1/daily/1day/"+locationKey
	r = requests.get(url,params={'apikey':weatherToken,'language':'de-de','details':'false','metric':'true'})
	headline = r.json()['Headline']['Text']
	weatherLink = r.json()['Headline']['Link']
	weatherCategory = r.json()['Headline']['Category']
	tempMin = r.json()['DailyForecasts'][0]['Temperature']['Minimum']['Value']
	tempMax = r.json()['DailyForecasts'][0]['Temperature']['Maximum']['Value']
	weatherIcon = r.json()['DailyForecasts'][0]['Day']['Icon']
	weatherPhrase = r.json()['DailyForecasts'][0]['Day']['IconPhrase']

	#Sending weather stickers instead of emojis
	#filename=runDir+"weather_icons/"+str(weatherIcon)+"-s.png"
	#iconFile=open(filename,'r')
	#alfred.sendPhoto(chatId,filename)
	emoji = weatherEmojis[weatherCategory]

	message = emoji+emoji+emoji+emoji+emoji+emoji+emoji+emoji+emoji+emoji+"\n*"+headline+"*\n"+weatherPhrase+" bei tagsueber zwischen "+str(tempMin)+degree_sign+"C bis "+str(tempMax)+degree_sign+"C\nMehr Infos unter: "+weatherLink
	alfred.sendMessage(chatId,message,parse_mode="Markdown")

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


#Handle incoming messages.

def handleMessage(msg):
	print msg
	chatId = msg['chat']['id']
	msgContent = msg['text']
	msgSender = msg['from']['first_name']

	print "Message received"
	print "messageForward: " + str(messageForward)
	if "alfred" in msgContent or "Alfred" in msgContent or(messageForward == True):
		print "Yeah, i was mentioned"
		resp = nlp.message(msgContent)
		if resp['entities'].has_key('intent'):
			intent = resp['entities']['intent'][0]['value']
			print resp
			print "Intent:" + intent
			intentActions[intent](chatId,msgSender,resp)
		else:
			print "No intent found"
			alfred.sendMessage(chatId,"Mmmh. Erklaer mir nochmal was ich machen soll")
			if messageForward == False:
				forceNextMessages(10)

MessageLoop(alfred,handleMessage).run_as_thread()

print "Listening..."
print getTimestamp()
while 1:
	time.sleep(10)
