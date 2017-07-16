# -- coding: utf-8 --

import sys
import select
import time

from PySide import QtCore

import plugins, utils, events

class Plugin(plugins.ThreadedPlugin):
	def _dataOnSTDIN(self):
		# https://stackoverflow.com/questions/3762881/how-do-i-check-if-stdin-has-some-data
		return select.select([sys.stdin,],[],[],0.0)[0]

	def _prompt(self):
		sys.stdout.write('> ')
		sys.stdout.flush()
		
	def run(self):
		self.keepRunning = True
		self.systemEvent.emit(events.Ready(self))
		self._prompt()
		while self.keepRunning:
			if self._dataOnSTDIN():
				cmd = input()
				if cmd == 'exit':
					self.systemEvent.emit(events.Exit(self))
				else:
					print('Unknown command: %s' % cmd)
					
				self._prompt()
			else:
				time.sleep(1)

	def handleSystemEvent(self, event):
		super().handleSystemEvent(event)
		
		if isinstance(event, events.Exit):
			self.keepRunning = False
