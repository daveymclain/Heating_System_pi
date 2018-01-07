#!/usr/bin/env python

import time
time.sleep(30)
import socket
import os
import glob
import sqlite3 as lite
import datetime
from RPLCD import CharLCD
import RPi.GPIO as GPIO
import threading
import ConfigParser
# Import smtplib for the actual sending function
import smtplib
import string
import sys
import logging
import socket
socket.setdefaulttimeout(20)

def sendEmail(option):
    logging.warning("trying to send email")

    TO = "braveheart_52@hotmail.com"
    FROM = "daveymclain@gmail.com"
    password = 'Bobbobbob14'
    if not option:
        SUBJECT = "The heating system is down!"
        text = ("Heating System Down!\ndo something you sexy man\nThe heating is currently: "+ str(on_off))
    else:
        SUBJECT = "The heating system back up!"
        text = ("Heating System up!\nYou have codied the shit out of it\nThe heating is currently: "+ str(on_off))
    BODY = string.join((
    "From: %s" % FROM,
    "To: %s" % TO,
    "Subject: %s" % SUBJECT ,
    "",
    text
    ), "\r\n")
    try:
        h = smtplib.SMTP()
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(FROM, password)
        server.sendmail(FROM, [TO], BODY)
        logging.warning("email sent. Server: " + str(option))
    except smtplib.SMTPException:
        logging.warning("cant send email")
    except socket.timeout:
        logging.warning("email socket timeout")
    finally:
        server.quit()



class Files:
    # sbj = 'Heating Down'
    # msg = "The heating server is down. Please check it!!"
    #
    # server.sendmail("daveymalcin@gmail.com", "braveheart_52@hotmail.com", msg)
    # server.quit()
    def __init__(self, file_extention):
        self.folder = '/var/www/davidgoss.duckdns.org/public_html/text/'
        self.file = self.folder + file_extention

    def read(self):
        f = open(self.file)
        t = f.read()
        f.close()
        return t

    def write(self, contents):
        f = open(self.file, 'rb+')
        f.write(str(contents))
        f.close()


class TempRead:

    def __init__(self, source):
        os.system('modprobe w1-gpio')
        os.system('modprobe w1-therm')
        self.base_dir = '/sys/bus/w1/devices/'
        self.device_folder = glob.glob(self.base_dir + source)[0]
        self.device_file = self.device_folder + '/w1_slave'

    def read_raw(self):
        f = open(self.device_file, 'r')
        lines = f.readlines()
        f.close()
        return lines

    def read_temp(self):
        lines = self.read_raw()
        while lines[0].strip()[-3:] != 'YES':
            time.sleep(0.2)
            lines = self.read_raw()
        equals_pos = lines[1].find('t=')
        if equals_pos != -1:
            temp_string = lines[1][equals_pos + 2:]
            temp_c = int(temp_string) / 1000.0
            temp_c = str(round(temp_c, 1))
            return temp_c

config = ConfigParser.ConfigParser()
config.read('/home/pi/server/heating.conf')
conf_count = 0
on_off = 'off'
servo_pos = 10
ava_temp = 19.0
cycle_room = 0
db_count = 0
on_off_count = 0
# lcd setup
screen = CharLCD(cols=16, rows=2, pin_rs=37, pin_e=35, pins_data=[33, 31, 29, 23])
# servo GPIO setup
GPIO.setup(15, GPIO.OUT)
p = GPIO.PWM(15, 50)
p.start(10)
# relay GPIO setup
GPIO.setup(13, GPIO.OUT)
# files
des_temp_file = Files('temp.txt')
ava_temp_file = Files('ava_temp.txt')
on_off_file = Files('on_off.txt')
hallway_temp_file = Files('hallway_temp.txt')
livingroom_temp_file = Files('living_temp.txt')
# read local temp set up
livingroom_temp = TempRead('28-031681e70dff')
hallway_temp = TempRead('28-0316823cdeff')
# test server is running
server_test = 0
emailSend = False
stop = True
run_event = threading.Event()
#get data from conf file
offset = config.getfloat('heating', 'low_offset')
dif_value = config.getfloat('heating', 'dif_value')
sensitivity = config.getfloat('heating', 'sensitivity')
dif_amount = config.getfloat('heating','dif_amount')
# logger**********
logging.basicConfig(format='{%(asctime)s} %(message)s', datefmt='%d/%m/%Y %H:%M:%S',filename='/home/pi/server/client.log',level=logging.DEBUG)
logging.warning('--------Startng Heating System---------')
logging.warning('Settings:')
logging.warning('Offset: '+ str(offset))
logging.warning('dif value: '+ str(dif_value))
logging.warning('Sensitivty: '+ str(sensitivity))
server_test = 0


# for turning on/off thermostat
def servo_move():

    global servo_pos
    global on_off
    GPIO.output(13, GPIO.HIGH)
    time.sleep(.5)
    if on_off == "run":
        logging.warning("turning on heating")
        while servo_pos >= 5:
            p.ChangeDutyCycle(servo_pos)
            time.sleep(0.05)
            servo_pos -= 0.05
    else:
        logging.warning("turning off heating")
        while servo_pos <= 10:
            p.ChangeDutyCycle(servo_pos)
            time.sleep(0.05)
            servo_pos += 0.05
    logging.warning("turning off relay")
    time.sleep(.5)
    GPIO.output(13, GPIO.LOW)

def write_db():
    con = lite.connect('/var/www/gossheating/public_html/database/templog.db')
    now = datetime.datetime.now()
    now = now.replace(second=0, microsecond=0)
    ur = con.cursor()
    if on_off == 'run':
        int_on_off = 1
    else:
        int_on_off = 0
    ur.execute("INSERT INTO temps VALUES (?, ?, ?, ?, ?);",
               (now, float(ava_temp), float(hallway_temp.read_temp()),
                int_on_off, float(livingroom_temp.read_temp())))
    con.commit()
    con.close()
    logging.warning("*********wrote ava temp to data base temps*********")


# get temp from another raspberry pi
def get_temp_ava(run_event):
    global ava_temp
    global server_test
    global on_off
    global server_test
    global emailSend
    udp_ip = config.get('socket', 'ip')
    port = config.getint('socket', 'port')
    message = "temp please"
    logging.warning("UDP target IP: %s", udp_ip)
    logging.warning("UDP target port: %s", port)
    logging.warning("message going to send: %s", message)
    global stop
    while run_event.is_set():
        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client.settimeout(20)
        while run_event.is_set():
            try:
                client.sendto(message.encode('utf_8'), (udp_ip, port))
                logging.warning("sending message: %s", message)
                data, addr = client.recvfrom(1024)
                logging.warning("received echo: %s %s", data,addr)
                ava_temp = data
                time.sleep(10)
                server_test = 0
                if not emailSend:
                    emailSend = True
                    sendEmail(emailSend)
            except socket.timeout:
                server_test += 1
                logging.warning("Server timeout. server_test: " + str(server_test))
                if server_test == 10:
                    logging.warning("Can not talk to Ava room pi. Send email.")
                    emailSend = False
                    sendEmail(emailSend)
                    server_test = 0
                break
            except socket.error as msg:
                logging.warning("socket error")
                time.sleep(5)
                break

def lcd_display():
    global cycle_room
    if cycle_room == 0:
        screen.cursor_pos = (0, 0)
        screen.write_string("Ava room: " + str(ava_temp) + unichr(223) + "c")
        cycle_room += 1
        time.sleep(1)
        ava_temp_file.write(ava_temp)
    if cycle_room == 1:
        screen.cursor_pos = (0, 0)
        screen.write_string("Hallway:  " + hallway_temp.read_temp() + unichr(223) + "c")
        cycle_room += 1
        time.sleep(1)
        hallway_temp_file.write(hallway_temp.read_temp())
    if cycle_room == 2:
        screen.cursor_pos = (0, 0)
        screen.write_string("Living:   " + livingroom_temp.read_temp() + unichr(223) + "c")
        cycle_room = 0
        time.sleep(1)
        livingroom_temp_file.write(livingroom_temp.read_temp())
    screen.cursor_pos = (1, 0)
    screen.write_string("Heating: " + on_off + "  ")


def logic(des_temp,hall):
    global on_off
    global on_off_count
    global db_count
    global conf_count
    global offset
    global dif_value
    global sensitivity
    global dif_amount
    conf_count += 1
    if conf_count == 10:
        conf_count = 0
        try:
            offset = config.getfloat('heating', 'low_offset')
            dif_value = config.getfloat('heating', 'dif_value')
            sensitivity = config.getfloat('heating', 'sensitivity')
            dif_amount = config.getfloat('heating','dif_amount')
            logging.warning("read conf file and put in new values")
        except:
            logging.warning("Problem reading conf values")
    dif = float(ava_temp) - float(hall)
    dif_val = 0
    if dif > dif_amount and float(ava_temp) > float(hall):
        dif_val = dif_value
        logging.warning("temp dif too high. revised des temp: " + str(float(des_temp) + dif_val))
    # write to lcd
    lcd_display()
    # write to data base
    if db_count == 0:
        write_db()
    db_count += 1
    if db_count == 75:
        db_count = 0
    # see if heating needs to come on
    if float(ava_temp) <= float(des_temp) - offset + dif_val:
        on_off_count += 1
        logging.warning("turn on count= " + str(on_off_count))
    # if float(ava_temp) >= float(des_temp) + dif_val:
    elif float(ava_temp) >= float(des_temp) + dif_val:
        on_off_count -= 1
        logging.warning("turn off count= " + str(on_off_count))
    else:
        logging.warning("not low enough to turn off. Not high enough to turn on")
    # turn heating on if needed
    if on_off_count == sensitivity and on_off == "off":
        on_off = "run"
        on_off_count = 0
        servo_move()
        on_off_file.write(on_off)
    elif on_off_count == sensitivity:
        logging.warning("-----already on-----")
        logging.warning("desired temp:- " + str(des_temp))
        on_off_count = 0
    # turn heating off if not needed
    if on_off_count == -sensitivity and on_off == "run":
        on_off = "off"
        on_off_count = 0
        servo_move()
        on_off_file.write(on_off)
    elif on_off_count == -sensitivity:
        logging.warning("-----already off-----")
        logging.warning("desired temp:- " + str(des_temp))
        on_off_count = 0
    time.sleep(.5)

def logic_loop(run_event):
    servo_move()
    on_off_file.write(on_off)
    while run_event.is_set():
        logic(des_temp_file.read(),hallway_temp_file.read())

def main():
    global run_event
    global on_off
    run_event.set()
    t1 = threading.Thread(target=get_temp_ava, args = (run_event,))
    t2 = threading.Thread(target=logic_loop, args = (run_event,))
    t1.start()
    time.sleep(.5)
    t2.start()
    try:
        while 1:
            time.sleep(.1)
    except KeyboardInterrupt:
        logging.warning('user interumpt. Cleaning up program')
        logging.warning('--------Stopping! Heating System---------')
        logging.warning("attempting to close threads")
        run_event.clear()
        t1.join()
        t2.join()
        logging.warning("threads successfully closed")
        on_off = "off"
        logging.warning("Turning off heating")
        servo_move()
        screen.clear()
        logging.warning("Cleaning gpio pins")
        GPIO.cleanup()
        sys.exit(0)

if __name__ == '__main__':
    main()
