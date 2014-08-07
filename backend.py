#!/usr/bin/pytho
# -*- coding: utf-8 -*-
'''
MakeICT/Bluebird Arthouse Electronic Door Entry

backend.py - contains code for accessing/modifying the database

Authors:
	Dominic Canare <dom@greenlightgo.org>
	Rye Kennedy <ryekennedy@gmail.com>
	Christian Kindel <iceman81292@gmail.com>
'''
#@TODO: Make proper use of transactions
#	Note: transaction is started when the cursor is created, ended by db.commit|rollback
#@TODO: Add debug logging

import MySQLdb, MySQLdb.cursors
from passlib.hash import sha512_crypt

class MySQLBackend(object):
	def __init__(self, host, db, user, passwd):
		'''
		Initiate a connection to the database using constructor arguments,
		and store these credentials for subsequent reconnects

		Args:
		  host (string): hostname of database computer
		  db (string): name of MySQL computer
		  user (string): MySQL username
		  passwd (string): MySQL password
		'''
		self.dbInfo = {'host':host, 'db':db, 'user':user, 'passwd':passwd}
		self.db = MySQLdb.connect(
			host=host, db=db,
			user=user, passwd=passwd,
			cursorclass=MySQLdb.cursors.DictCursor
		)

	def reconnectDB(self):
		'''
		Re-connect to database using stored credentials
		'''
		self.db.close()
		self.db = MySQLdb.connect(
			host=self.dbInfo['host'], db=self.dbInfo['db'],
			user=self.dbInfo['user'], passwd=self.dbInfo['passwd'],
			cursorclass=MySQLdb.cursors.DictCursor
		)
	
	#@TEST added this to make sure data is up-to-date. Not sure if it's the best way
	#only useful if long running scripts like door-lock.py
	def ensureConnection(self):
		if self.db.stat() == "MySQL server has gone away":
			self.reconnectDB()
		self.db.commit()				

	#@TODO: Unit tests
	def log(self, logType, rfid=None, userID=None, message=None, commit=True):
		'''
		Write a log to MySQL database
		
		Args:
		  logtype (string): 'assign', 'activate', 'de-activate', 'unlock', 'deny', 'message', 'error'
		  rfid (string, optional): id number of rfid card, Default=None
		  userID (string, optional): the user's ID number, Default=None
		  message (string, optional): additional information, Default=None
		  commit (bool, optional): if True commit the transaction, Default=True
		'''
		sql = '''
			INSERT INTO logs
				(timestamp, logType, rfid, userID, message)
			VALUES
				(UNIX_TIMESTAMP(), %s, %s, %s, %s)'''

		cursor = self.db.cursor()
		cursor.execute(sql, (logType, rfid, userID, message))
		cursor.close()
		if commit:
			self.db.commit()

	#@TODO: implement this. duh.
	def saltAndHash(self, data):
		'''
		Salt and hash a plaintext password using SHA512 algorithm

		Args:
		  data (string): a plaintext password
		Returns:
		  A string containing the salted hash of the password
		'''
		return sha512_crypt.encrypt(data)
	
	def getUser(self, key, value):
		'''
		Retrieve information about a user whose attribute %key is %value
		
		Args:
		  key (string): 'email' or 'userID' or 'id'
		  value (string): the user's e-mail address, userID, or NFC key UID
		Returns:
		  Dict of user data if the user exists
		  None if the user does not exist
		'''
		self.ensureConnection()	
		sql = 	'''SELECT * FROM users '''
		cursor = self.db.cursor()
		if key == 'id':
			sql += '''JOIN rfids ON users.userID = rfids.userID '''
			key = 'rfids.' + key
		elif key == 'email' or key == 'userID':
			pass
		else:
			#@TODO: not a valid key, raise an exception?
			return None
		sql += '''WHERE ''' + key + ''' = %s'''
		cursor.execute(sql, value)
		data = cursor.fetchone()
		cursor.close()
		self.db.commit()
		return data

	def getUserByEmail(self, email):
		'''
		Retrieve information for user with a given e-mail
		
		Args:
		  email (string): the e-mail address of the user
		Returns:
		  Dict of user data if the user exists
		  None if the user does not exist
		'''
		return self.getUser('email', email)

	def getUserByUserID(self, userID):
		'''
		Retrieve information for user with a given userID
		
		Args:
		  userID (string): the userID of the user
		Returns:
		  Dict of user data if the user exists
		  None if the user does not exist
		'''
		return self.getUser('userID', userID)

	def getUserByKeyID(self, key):
		'''
		Look up user given a card id number
		
		Args:
		  key (string): the UID of an NFC key
		Returns:
		  Dict of user data if the user exists
		  None if card is not registered to a user
		'''
		return self.getUser('id', key)
	
	def addUser(self, email, firstName=None, lastName=None, password=None):
		'''
		Add a user to the database

		Args:
		  email (string): user's e-mail address
		  firstname (string, optional): user's first name, default=None
		  lastName (string, optional): user's last name, default=None
		  password (string, optional): user's password, default=None
		Returns:
		  A string containing the newly created user's ID number
		'''
		sql = '''
			INSERT INTO users
				(email, firstName, lastName, passwordHash)
			VALUES
				(%s, %s, %s, %s)'''

		if password == '' or password == None:
			password = None
		else:
			password = self.saltAndHash(password)
		cursor = self.db.cursor()
		cursor.execute(sql, (email, firstName, lastName, password))
		cursor.close()

		self.db.commit()
		user = self.getUserByEmail(email)
		if user != None:
			return user['userID']
	
	#@TODO: should be able to delete user without deleting logs	
	def rmUser(self, userID):
		'''
		Delete a user with a given userID.

		Args:
		  userID (string): Unique ID of user to delete
		'''
		sql = 	'''
			DELETE FROM logs
				WHERE userID=%s;
			DELETE FROM rfids
				WHERE userID=%s;
			DELETE FROM userTags
				WHERE userID=%s;
			DELETE FROM users
				WHERE userID=%s;
			'''
		cursor = self.db.cursor()
		cursor.execute(sql, (userID, userID, userID, userID))
		cursor.close()

		self.db.commit()
	
	#@TODO: Unit tests
	def enroll(self, key, userID, autoSteal=False):
		'''
		Link an rfid card serial number to a user

		Args:
		  key (string): the rfid serial number
		  userID (string): the user's ID number
		  autoSteal (bool, optional): if True assign the key even if it is already assigned
		'''
		sql = '''
			INSERT INTO rfids
				(id, userID)
			VALUES (%(key)s, %(userID)s)'''
		if autoSteal:
			sql = sql + ' ON DUPLICATE KEY UPDATE userID=%(userID)s'
		
		cursor = self.db.cursor()
		cursor.execute(sql, {'key': key, 'userID': userID })
		self.log('assign', key, userID, commit=False)

		sql = 'UPDATE users SET status=\'active\' WHERE userID=%(userID)s';
		cursor.execute(sql, { 'userID': userID })
		self.log('activate', userID=userID, commit=False)
		cursor.close()
		
		self.db.commit()

backend = MySQLBackend(
	host="localhost" ,db="MakeICTMemberKeys",
	user="MakeICTDBUser", passwd="2879fd3b0793d7972cbf7647bc1e62a4")
