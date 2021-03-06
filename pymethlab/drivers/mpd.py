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

DRIVERS = ['MpdDriver']

from gettext import gettext as _

class MpdDriver:
  name = 'mpd'
  name_tr = _('Music Player Daemon')
  def __init__(self, methlab):
    import mpdclient3
    self.mpdclient = mpdclient3

  def play_files(self, files):
    mpd = self.mpdclient.connect()
    mpd.do.clear()
    for file in files:
      mpd.do.add(file)
    mpd.do.play(0)

  def enqueue_files(self, files):
    mpd = self.mpdclient.connect()
    for file in files:
      mpd.do.add(file)
