#!/usr/bin/python/
# -*- coding: utf-8 -*-
'''
MakeICT/Bluebird Arthouse Electronic Door Entry

rpi.py: Hardware control

Authors:
	Dominic Canare <dom@greenlightgo.org>
	Rye Kennedy <ryekennedy@gmail.com>
'''

import lib.MFRC522 as NFC
import wiringpi2
import time

class InterfaceControl(object):
	def __init__(self):
		Pi_rev = wiringpi2.piBoardRev()	#@TODO: use this?
		self.GPIOS = {
			'latch': 7,
			'unlock_LED': 11,
			'power_LED': 13,
			'buzzer': 12, 
			'doorStatus1': 15,
			'doorStatus2': 16,
		}
		
		self.nfc = NFC.MFRC522()
		
		#set up I/O pins
		wiringpi2.wiringPiSetupPhys()
		wiringpi2.pinMode(self.GPIOS['unlock_LED'], 1)
		wiringpi2.pinMode(self.GPIOS['power_LED'], 1)
		wiringpi2.pinMode(self.GPIOS['latch'], 1)
		wiringpi2.pinMode(self.GPIOS['doorStatus1'], 0)
		wiringpi2.pinMode(self.GPIOS['doorStatus2'], 0)
		
		#Set up Hardware PWM - Only works on GPIO 18 (Phys 12)
		wiringpi2.pwmSetMode(0)				# set PWM to markspace mode
		wiringpi2.pinMode(self.GPIOS['buzzer'], 2)      # set pin to PWM mode
		wiringpi2.pwmSetClock(750)   			# set HW PWM clock division (frequency)
		wiringpi2.pwmWrite(self.GPIOS['buzzer'], 0)
		
		#Set input pull-ups
		wiringpi2.pullUpDnControl(self.GPIOS['doorStatus1'], 2)
		wiringpi2.pullUpDnControl(self.GPIOS['doorStatus2'], 2)

	def nfcGetUID(self):
		loops = 0
		while loops < 20:
			# Scan for cards    
			(status,TagType) = self.nfc.MFRC522_Request(self.nfc.PICC_REQIDL)
			# If a card is found
			if status == self.nfc.MI_OK:
				# Get the UID of the card
				(status,uid) = self.nfc.MFRC522_Anticoll()
			# If we have the UID, continue
			if status == self.nfc.MI_OK:
				# Print UID
				return format(uid[0],'02x')+format(uid[1], '02x')+format(uid[2], '02x')+format(uid[3],'02x')
			loops += 1
			time.sleep(0.5)
		return None
	
	def output(self, componentID, status):
		'''
		Write to a GPIO pin set as an output

		Args:
		  componentID (int): pin number of output pin
		  status (bool): True to turn on, False to turn off
		'''
		wiringpi2.digitalWrite(self.GPIOS[componentID], status)

	def input(self, componentID):
		'''
		Read a GPIO pin set as an input
		
		Args:
		  componentID (int): pin number of input pin

		Returns:
		  True if pin is high
		  False if pin is low
		'''
		return wiringpi2.digitalRead(self.GPIOS[componentID])

	def setPowerStatus(self, powerIsOn):
		'''
		Set power LED state

		Args:
		  powerIsOn (bool): True to turn on LED, False to turn off
		'''
		self.output('power_LED', powerIsOn)

	def setBuzzerOn(self, buzzerOn):
		'''
		Set buzzer state

		Args:
		  buzzerOn (bool): True to turn on buzzer, False to turn off
		'''

		if buzzerOn:
			wiringpi2.pwmWrite(self.GPIOS['buzzer'], 30)    # 30% duty cycle
			pass
		else:
			wiringpi2.pwmWrite(self.GPIOS['buzzer'], 0)
			pass

	def unlockDoor(self, timeout=2):
		'''
		Unlock door, activate unlock_LED and buzzer, and relock door after timeout

		Args:
		  timeout (int): length of time to keep the door unlocked (default 2)
		'''
		self.output('latch', True)
		self.output('unlock_LED', True)
		self.setBuzzerOn(True)
		time.sleep(timeout)
		self.output('latch', False)
		self.output('unlock_LED', False)
		self.setBuzzerOn(False)

	def checkDoors(self):
		'''
		Check the open/closed status of both doors. 

		Returns:
		  A list of Boolean values representing each door state: True if open, False if closed
		'''

		#invert values if using pull-down resistors on switch inputs
		return [self.input('doorStatus1'), self.input('doorStatus2')]


	def showBadCardRead(self, blinkCount=3, blinkPeriod=0.25):
		'''
		Blink power_LED to indicate invalid card read

		Args:
		  blinkCount (int): number of time to blink (default 3)
		  blinkPeriod (float): on/off duration in seconds (default 0.25)
		'''
		for i in range(blinkCount):
			self.output('power_LED', True)
			self.setBuzzerOn(True)
			time.sleep(blinkPeriod)
			self.output('power_LED', False)
			self.setBuzzerOn(False)
			time.sleep(blinkPeriod)

	def cleanup(self):
		'''
		Reset status of GPIO pins before terminating
		'''
		#Clean up GPIO pins
		wiringpi2.digitalWrite(self.GPIOS['unlock_LED'], 0)
		wiringpi2.digitalWrite(self.GPIOS['power_LED'], 0)
		wiringpi2.digitalWrite(self.GPIOS['latch'], 0)
		wiringpi2.pwmWrite(self.GPIOS['buzzer'], 0)
		
		wiringpi2.pinMode(self.GPIOS['unlock_LED'], 0)
		wiringpi2.pinMode(self.GPIOS['power_LED'], 0)
		wiringpi2.pinMode(self.GPIOS['latch'], 0)
		wiringpi2.pinMode(self.GPIOS['buzzer'], 0) 

		wiringpi2.pullUpDnControl(self.GPIOS['doorStatus1'], 0)
		wiringpi2.pullUpDnControl(self.GPIOS['doorStatus2'], 0)
	
interfaceControl = InterfaceControl()
