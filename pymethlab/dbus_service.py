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

import dbus.service
import gtk

class MethLabApplicationDBusProxy(dbus.service.Object):
  def __init__(self, bus):
    dbus.service.Object.__init__(self, bus, '/org/thegraveyard/MethLab/Application')

  @dbus.service.method('org.thegraveyard.MethLab.Application',
                       in_signature='', out_signature='')
  def quit(self):
    gtk.main_quit()

class MethLabMainWindowDBusProxy(dbus.service.Object):
  def __init__(self, bus, window):
    self.window = window
    dbus.service.Object.__init__(self, bus, '/org/thegraveyard/MethLab/MainWindow')

  @dbus.service.method('org.thegraveyard.MethLab.MainWindow',
                       in_signature='', out_signature='')
  def show(self):
    self.window.show_window()

  @dbus.service.method('org.thegraveyard.MethLab.MainWindow',
                       in_signature='', out_signature='')
  def hide(self):
    self.window.hide_window()

  @dbus.service.method('org.thegraveyard.MethLab.MainWindow',
                       in_signature='', out_signature='')
  def toggle(self):
    if self.window.window.get_property('visible'):
      self.window.hide_window()
    else:
      self.window.show_window()

class MethLabDBusService:
  def __init__(self, window):
    session_bus = dbus.SessionBus()
    self.name = dbus.service.BusName('org.thegraveyard.MethLab', bus = session_bus)
    self.app_proxy = MethLabApplicationDBusProxy(session_bus)
    self.main_window_proxy = MethLabMainWindowDBusProxy(session_bus, window)
