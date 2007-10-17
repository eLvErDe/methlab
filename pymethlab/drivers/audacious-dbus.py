#  methlab - A music library application
#  Copyright (C) 2007 Ingmar K. Steen (iksteen@gmail.com)
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

DRIVERS = ['AudaciousDBusDriver']

try:
  from dbus import Bus, DBusException
except ImportError:
  DRIVERS = []

from gettext import gettext as _
import urllib

def get_audacious():
  bus = Bus(Bus.TYPE_SESSION)

  try:
    return bus.get_object('org.atheme.audacious', '/org/atheme/audacious')
  except DBusException:
    return None

class AudaciousDBusDriver:
  name = 'audacious-dbus'
  name_tr = _('Audacious (using DBus)')
  def __init__(self):
    self.audacious = get_audacious()

  def play_files(self, files):
    self.audacious.Clear()
    files = ['file://' + file for file in files]
    for file in files:
      self.audacious.AddUrl(file)
    self.audacious.Play()

  def enqueue_files(self, files):
    files = ['file://' + file for file in files]
    for file in files:
      self.audacious.AddUrl(file)
