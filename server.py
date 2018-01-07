#!/usr/bin/env python

import time
print("sleeping before start")
time.sleep(30)
import socket
import sys
import glob
import os


os.system('modprobe w1-gpio')
os.system('modprobe w1-therm')

base_dir = '/sys/bus/w1/devices/'
device_folder = glob.glob(base_dir + '28*')[0]
device_file = device_folder + '/w1_slave'
HOST = '192.168.0.21'   # Symbolic name meaning all available interfaces
PORT = 1884 # Arbitrary non-privileged port
def read_temp_raw():
    f = open(device_file, 'r')
    lines = f.readlines()
    f.close()
    return lines
	
def read_temp_c():
    lines = read_temp_raw()
    while lines[0].strip()[-3:] != 'YES':
        time.sleep(0.2)
        lines = read_temp_raw()
    equals_pos = lines[1].find('t=')
    if equals_pos != -1:
        temp_string = lines[1][equals_pos+2:]
        temp_c = int(temp_string) / 1000.0 # TEMP_STRING IS THE SENSOR OUTPUT, MAKE SURE IT'S AN INTEGER TO DO THE MATH
        temp_c = str(round(temp_c, 1)) # ROUND THE RESULT TO 1 PLACE AFTER THE DECIMAL, THEN CONVERT IT TO A STRING
        return temp_c 
# Datagram (udp) socket
def main():
	try :
		s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		print('Socket created')
	except socket.error as msg :
		print('Failed to create socket. Error Code : ' + str(msg[0]) + ' Message ' + msg[1])

	# Bind socketto local host and port
	try:
		s.bind((HOST, PORT))
	except socket.error as msg:
		print('Bind failed. Error Code : ' + str(msg[0]) + ' Message ' + msg[1])

	print('Socket bind complete')
	 
	#now keep talking with the client
	try:
		while 1:
			# receive data from client (data, addr)
			d = s.recvfrom(1024)
			data = d[0]
			addr = d[1]

			if not data:
				continue
			data = read_temp_c()
			reply = data

			s.sendto(reply , addr)
			print('Message[' + addr[0] + ':' + str(addr[1]) + '] - ' + data.strip())
	except KeyboardInterrupt:
		print('shutting down socket')
		s.close()
        sys.exit()
	print("closing socket")
	s.close()
if __name__ == '__main__':
    try:
        while True:
            main()
            print('restart program')
    except KeyboardInterrupt:
        s.close()
        sys.exit()
