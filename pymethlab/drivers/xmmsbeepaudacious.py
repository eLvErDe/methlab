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

DRIVERS = ['XmmsAlikeDriver', 'AudaciousDriver', 'BeepDriver']

from gettext import gettext as _

class XmmsAlikeDriver:
  name = 'xmmsalike'
  name_tr = _('XMMS (using xmmsalike)')
  flavor = 'xmms'
  def __init__(self, methlab):
    import xmmsalike
    xmmsalike.init(self.flavor)
    self.xmms = xmmsalike

  def play_files(self, files):
    self.xmms.playlist_set(files)
    self.xmms.play()

  def enqueue_files(self, files):
    self.xmms.playlist_add(files)

class AudaciousDriver(XmmsAlikeDriver):
  name = 'audaciousalike'
  name_tr = _('Audacious (using xmmsalike)')
  flavor = 'audacious'

class BeepDriver(XmmsAlikeDriver):
  name = 'beepalike'
  name_tr = _('Beep Media Player (using xmmsalike)')
  flavor = 'beep'
