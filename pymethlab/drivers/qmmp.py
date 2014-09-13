DRIVERS = ['QMMPDriver']

from gettext import gettext as _
from subprocess import call

class QMMPDriver:
	name = 'QMMP'
	name_tr = _('QMMP (using cli)')

	def __init__(self, methlab):
		pass

	def play_files(self, files):
		args = ["qmmp"]
		args.extend(files)
		call(args)

	def enqueue_files(self, files):
		args = ["qmmp", "-e"]
		args.extend(files)
		call(args)

