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
		if logType not in self.getValidLogTypes():
			raise(ValueError('Not a valid logType'))
		cursor = self.db.cursor()
		cursor.execute(sql, (logType, rfid, userID, message))
		cursor.close()
		if commit:
			self.db.commit()

	def getLogs(self):
		'''
		'''
		sql = 	'''
			SELECT * FROM logs
			'''
		cursor = self.db.cursor()
		data = cursor.fetchmany(cursor.execute(sql))
		cursor.close()

		return data		

	def getValidTags(self):
		'''
		'''
		sql = 	'''
			SELECT tag FROM tags
			'''

		cursor = self.db.cursor()
		data = cursor.fetchmany(cursor.execute(sql))
		data = [tag['tag'] for tag in data]
		cursor.close()
		self.db.commit()
		return data

	def getValidStatuses(self):
		'''
		'''
		return self.getEnumValues('users', 'status')

	def getValidLogTypes(self):
		'''
		'''
		return self.getEnumValues('logs', 'logType')	

	def getEnumValues(self, table, field):
		'''
		'''
		sql = 	'''
			SHOW COLUMNS FROM {:s} WHERE Field = %s
			'''.format(table)

		cursor = self.db.cursor()
		cursor.execute(sql, field)
		data = [datum[1:-1] for datum in cursor.fetchone()['Type'][5:-1].split(',')]
		cursor.close()
		self.db.commit()
		return data
		

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
		sql1 = 	'''
			SELECT tags.* FROM tags
				JOIN userTags ON tags.tagID = userTags.tagID
				JOIN users ON userTags.userID = users.userID
			WHERE users.email = %s
			'''
		sql3 = 	'''
			SELECT * from rfids WHERE userID = %s
			'''
		sql2 = 	'''SELECT * FROM users '''
		cursor = self.db.cursor()
		if key == 'id':
			sql2 += '''JOIN rfids ON users.userID = rfids.userID '''
			key = 'rfids.' + key
		elif key == 'email' or key == 'userID':
			pass
		else:
			#@TODO: not a valid key, raise an exception?
			return None
		sql2 += '''WHERE ''' + key + ''' = %s'''
		cursor.execute(sql2, value)
		user = cursor.fetchone()
		if user != None:
			numTags = cursor.execute(sql1,user['email'])
			data = cursor.fetchmany(numTags)
			tags = [tag['tag'] for tag in data]
			user['tags'] = tags
			rfids = cursor.fetchmany(cursor.execute(sql3, user['userID']))
			rfidList = [x['id'] for x in rfids]
			user['rfids'] = rfidList
		cursor.close()
		self.db.commit()
		return user

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

	def getAllUsers(self):
		'''
'		Get all users in the database.

		Returns:
		  List of dicts containing user information
		'''
		sql1 = 	'''
			SELECT tags.* FROM tags
				JOIN userTags ON tags.tagID = userTags.tagID
				JOIN users ON userTags.userID = users.userID
			WHERE users.email = %s
			'''
		sql3 = 	'''
			SELECT * from rfids WHERE userID = %s
			'''
		cursor = self.db.cursor()
		userList =  cursor.fetchmany(cursor.execute(
			'''SELECT * FROM users'''))
		for user in userList:
			if user != None:
				numTags = cursor.execute(sql1,user['email'])
				data = cursor.fetchmany(numTags)
				tags = [tag['tag'] for tag in data]
				user['tags'] = tags
				rfids = cursor.fetchmany(cursor.execute(sql3, user['userID']))
				rfidList = [x['id'] for x in rfids]
				user['rfids'] = rfidList
		cursor.close()
		self.db.commit()
		return userList
	
	def updateUser(self, userID, email=None, firstName=None, lastName=None, tags=None, status=None, password=None):
		'''
		Update an existing user

		Args:
		  userID (string): the userID of the user to be edited
		  email (string, optional): updated e-mail address
		  firstName (string, optional): updated first name
		  lastName (string, optional): updated last name
		  tags (list of strings, optional): updated list of tags
		  password (string, optional): updated password
		'''
		sql = '''UPDATE users SET '''
		strings = []
		if email != None and email != '':
			strings.append('''email='%s' '''%email)
		if firstName != None and firstName != '':
			strings.append('''firstName='%s' '''%firstName)
		if lastName != None and lastName != '':
			strings.append('''lastName='%s' '''%lastName)
		if status != None and status != '':
			strings.append('''status='%s' '''%status)
		if password != None and password != '':
			strings.append('''passwordHash='%s' '''%self.saltAndHash(password))
		sql += ','.join(strings)
		sql += '''WHERE userID = %s'''
			
		cursor = self.db.cursor()
		if email or firstName or lastName or password or status:
#			print sql
			cursor.execute(sql, userID)
		
		if tags != None:
			cursor.execute('''DELETE FROM userTags WHERE userID = %s''', userID)
			for tag in tags:
				cursor.execute('''INSERT INTO userTags (userID, tagID)
						  VALUES(
						  (SELECT userID FROM users WHERE userID = %s),
						  (SELECT tagID FROM tags WHERE tag = %s))''', 
						  (userID, tag))
	
		cursor.close()
		self.db.commit()

	def addUser(self, email, firstName=None, lastName=None, password=None, tags=None):
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
		sql = 	'''
			INSERT INTO users
				(email, firstName, lastName, passwordHash)
			VALUES
				(%s, %s, %s, %s)
			'''
		sql2 = 	'''
			INSERT INTO userTags (userID, tagID)
			VALUES (%s,(SELECT tagID FROM tags WHERE tag = %s))
			'''

		if password == '' or password == None:
			password = None
		else:
			password = self.saltAndHash(password)
		cursor = self.db.cursor()
		cursor.execute(sql, (email, firstName, lastName, password))
		user = self.getUserByEmail(email)
		if tags != None:
			for tag in tags:
				cursor.execute(sql2, (user['userID'], tag))
		
		cursor.close()
		self.db.commit()
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

	def unenroll(self, userID, keyUID):
		'''
		Remove NFC key from user

		Args:
		  userID (string): unique ID of the user
		  keyUID (string): UID of the card
		'''
		sql = 	'''
			DELETE FROM rfids WHERE id = %s AND userID = %s
			'''
		cursor = self.db.cursor()
		cursor.execute(sql,(keyUID, userID))
		cursor.close()
		self.db.commit()

backend = MySQLBackend(
	host="localhost" ,db="MakeICTMemberKeys",
	user="MakeICTDBUser", passwd="2879fd3b0793d7972cbf7647bc1e62a4")
