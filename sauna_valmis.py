#!/usr/bin/env python
# -*- coding: utf-8 -*-

#pip install python-telegram-bot --upgrade
#sudo modprobe w1-gpio
#sudo modprobe w1-therm


from telegram.ext import Updater, CommandHandler, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import logging
import time
import _thread
import RPi.GPIO as GPIO
import os
from functools import wraps



# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

LIST_OF_ADMINS = [753621566, 740806666] #Add your telegram id to gain access to bot

#Temperature sensor setup
os.system('sudo modprobe w1-gpio')
os.system('sudo modprobe w1-therm')

temp_sensor ='/sys/bus/w1/devices/22-0000005717c4/w1_slave'

#Led setup
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(18, GPIO.OUT)
GPIO.output(18,GPIO.LOW)

def restricted(func):
    @wraps(func)
    def wrapped(bot, update, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in LIST_OF_ADMINS:
            print("Unauthorized access denied for {}.".format(user_id))
            update.message.reply_text('\U000026D4')
            return
        return func(bot, update, *args, **kwargs)
    return wrapped

@restricted
def start(bot, update):
    
    update.message.reply_text('Hei! kirjoita /set <Lämpötila(\u2103)> <Aika(min)> asettaaksesi lämmityksen ja sen jälkeisen saunan päällä olo ajan.')
    print("Start message")
    #update.message.reply_text('Please choose:', reply_markup=reply_markup)

def alarm(bot, job):

    bot.send_message(job.context, text='Sauna sammutettu!')
    GPIO.output(18,GPIO.LOW)
    print("Turned timer and sauna off")
    
@restricted
def set_timer(bot, update, args, job_queue, chat_data):

    chat_id = update.message.chat_id
    if 'job'  in chat_data or 'temp'  in chat_data :
        update.message.reply_text('Lämmitys tai ajastin on jo asetettu!\n/unset poistaaksesi ne.')
        return
    try:
        global due
        due = int(args[0])
        timer = int (args[1])
        if due < 0 or timer < 0:
            update.message.reply_text('En ole jääkaappi tai aikakone! \U0001F916')
            print("Heating set value out of range")
            return

        update.message.reply_text('Lämmitys aloitettu onnistuneesti! %s\u2103' % (due))
       
        GPIO.output(18,GPIO.HIGH) 

        jobTemp =job_queue.run_repeating(startTemperature,interval=1,first=0,context={"chat_data":chat_data, "chat_id":chat_id,"job_queue":job_queue,"timer":timer},name='temperature')     
        chat_data['temp'] = jobTemp    

        print("Heating set")

    except (IndexError, ValueError):
        update.message.reply_text('Käyttö:\n/set <Lampötila(\u2103)> <Lämmityksen jälkeinen aika (min)>')

        print("Heating set help")

@restricted
def unset(bot, update, chat_data):
    
    if 'job'  in chat_data or 'temp'  in chat_data :
        if 'job' in chat_data:
            job = chat_data['job']
            job.schedule_removal()
            del chat_data['job']
        if 'temp' in chat_data:
            temp = chat_data['temp']
            temp.schedule_removal()
            del chat_data['temp']

        update.message.reply_text('Sauna ja ajastin sammutettu onnistuneesti!')

        GPIO.output(18,GPIO.LOW)

        print("Unset")

        return    
     
    update.message.reply_text('Ei aktiivista lämmitystä tai ajastinta!')
    print("Unset help")

def temp_raw():
    f = open(temp_sensor, 'r')
    lines = f.readlines()
    f.close()
    return lines

def read_temp(temperature):
    while True:
        lines = temp_raw()
        while lines[0].strip()[-3:] != 'YES':
            time.sleep(0.2)
            lines = temp_raw()
        temp_output = lines[1].find('t=')
        if temp_output != -1:
            temp_string = lines[1].strip()[temp_output+2:]
            temp_c = float(temp_string) / 1000.0
            global lampotila
            lampotila = temp_c
            print(lampotila)
                    
def startTemperature(bot,job):
    
    if lampotila >= due:
        print("Temperature reached timer started")
        chat_data = job.context["chat_data"]#chat_data('temp')
        #print(chat_data)
        timer = job.context["timer"]*60
        #print(timer)
        job.schedule_removal()
        del chat_data['temp']

        bot.send_message(job.context["chat_id"],text='Sauna valmis! Lampotila: %.2f\u2103 \U0001F44C Sauna sammuu %d minuutin kuluttua,\n/unset sammuttaaksesi saunan.' % (lampotila,timer/60)) 
        job = job.context["job_queue"].run_once(alarm, timer, context=job.context["chat_id"])
        chat_data['job'] = job

def error(bot, update, error):
    #Log Errors caused by Updates.
    logger.warning('Update "%s" caused error "%s"', update, error)
    
@restricted
def temperature(bot, update):

    emoji = "\U0001F321"

    if lampotila > 60:
        emoji = "\U0001F975"

    if lampotila < 60:
        emoji = "\U0001F976"

    update.message.reply_text('\U0001F321 %.2f\u2103 %s' % (lampotila, emoji))
    print("Temperature message")

@restricted
def help(bot, update):
    update.message.reply_text('Komennot:\n/start\n/set\n/unset\n/temp\n/help')
    print("Help message")



def main():

    updater = Updater("Token") #Bot token here

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help))
    dp.add_handler(CommandHandler("set", set_timer,
                                  pass_args=True,
                                  pass_job_queue=True,
                                  pass_chat_data=True))
    dp.add_handler(CommandHandler("temp", temperature))
    dp.add_handler(CommandHandler("unset", unset, pass_chat_data=True))
    
    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    updater.start_polling()
    
    # Start new thread for reading temperature
    try:
        _thread.start_new_thread(read_temp,("thread",))
    except:
        print("Error")
   
    

if __name__ == '__main__':
    main()
