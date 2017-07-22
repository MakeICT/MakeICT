# -- coding: utf-8 --

import os, logging
import re
from importlib.machinery import SourceFileLoader

from PySide import QtCore

import plugins
from .. import utils, events, backend

import json

loadedPlugins = []

def getPluginByName(name):
	for plugin in loadedPlugins:
		if plugin.getName() == name:
			return plugin

class AbstractPlugin(QtCore.QObject):
	systemEvent = QtCore.Signal(object)

	def __init__(self):
		super().__init__()
		self.db = backend.Backend(self.getName())
		self.enabled = False
		self.options = []
		self.defineOptions()
		self.loadOptions()

	def loadOptions(self):
		for option in self.options:
			option.value = self.db.getPluginOption(self.getName(), option.name)

	def getName(self):
		# strip top-level module name
		name = type(self).__module__
		return re.sub('^[^\\.]*\\.', '', name)

	def getOptions(self):
		return self.options

	def getOption(self, name):
		for options in self.options:
			if options.name == name:
				return options

	def setOption(self, name, value):
		self.db.setPluginOption(self.getName(), name, value)

	def defineOptions(self):
		pass

	def handleSystemEvent(self, event):
		pass

	def isEnabled(self):
		return self.enabled

	def setEnabled(self, status):
		self.enabled = status

	def __str__(self):
		return '<%s>' % self.getName()

class ThreadedPlugin(AbstractPlugin):
	def __init__(self):
		super().__init__()
		self.thread = utils.SimpleThread(self.run)

	def handleSystemEvent(self, event):
		if isinstance(event, events.Ready):
			if event.originator == QtCore.QCoreApplication.instance():
				self.thread.start()


def loadAllFromPath(base='plugins'):
	global loadedPlugins

	# make a list of directories to check
	pluginDirs = []
	for p in os.listdir(base):
		if p[:2] != '__' and os.path.isdir(os.path.join(base, p)):
			pluginDirs.append(p)

	# Try to load plugins
	# Some plugins depend on others, so we may have to try multiple times
	leftover = len(pluginDirs) + 1 # add 1 to make sure it's ran at least once
	while len(pluginDirs) > 0 and len(pluginDirs) != leftover:
		leftover = len(pluginDirs)
		modules = {}
		for p in list(pluginDirs):
			logging.debug('Loading plugin module: %s...' % p)
			path = os.path.join(base, p)

			# load the module
			try:
				print('Loading %s' % p)
				mod = SourceFileLoader('plugins.%s' % p, os.path.join(path, "__init__.py")).load_module()
				modules[p] = mod

				# add to the module list
				plugins.__dict__[p] = mod
				pluginDirs.remove(p)
			except Exception as exc:
				print('Failed to load plugin module %s' % path)
				print(exc)
				raise exc
		
		for name, mod in modules.items():
			logging.debug('Initializing plugin: %s...' % name)

			# load the plugin
			try:
				plugin = mod.Plugin()
				loadedPlugins.append(plugin)
				logging.debug('Initialized %s' % plugin.getName())
				print('Initialized %s' % plugin.getName())
			except Exception as exc:
				print('Failed to create plugin %s' % name)
				print(exc)
				raise exc

	if len(pluginDirs) > 0:
		logging.error('Failed to load plugin modules: %s' % pluginDirs)
	
	return loadedPlugins