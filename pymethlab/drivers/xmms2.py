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

DRIVERS = ['Xmms2Driver']

from gettext import gettext as _
import urllib

class Xmms2Driver:
  name = 'xmms2'
  name_tr = _('XMMS2 (using xmmsclient)')
  def __init__(self):
    import xmmsclient
    self.xmms = xmmsclient.XMMSSync()
    self.xmms.connect()

  def play_files(self, files):
    self.xmms.playlist_clear()
    files = ['file://' + file for file in files]
    for file in files:
      self.xmms.playlist_add_url(file)
    if self.xmms.playback_status() > 0:
      self.xmms.playback_tickle()
    self.xmms.playback_start()

  def enqueue_files(self, files):
    files = ['file://' + file for file in files]
    for file in files:
      self.xmms.playlist_add_url(file)
