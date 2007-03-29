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

class DummyDriver:
  name = "Dummy driver (doesn't do anything)"
  def __init__(self):
    pass

  def play(self, files):
    pass

  def enqueue(self, files):
    pass

class PyXmmsDriver:
  name = 'XMMS driver (using PyXMMS)'
  def __init__(self):
    import xmms.control
    self.xmms = xmms.control

  def play(self, files):
    self.xmms.playlist_clear()
    self.xmms.enqueue_and_play_launch_if_session_not_started(files)

  def enqueue(self, files):
    self.xmms.playlist_add(files)

class XmmsAlikeDriver:
  name = 'XMMS driver (using xmmsalike)'
  flavor = 'xmms'
  def __init__(self):
    import xmmsalike
    xmmsalike.init(self.flavor)
    self.xmms = xmmsalike

  def play(self, files):
    self.xmms.playlist_set(files)
    self.xmms.play()

  def enqueue(self, files):
    self.xmms.playlist_add(files)

class AudaciousDriver(XmmsAlikeDriver):
  name = 'Audacious driver (using xmmsalike)'
  flavor = 'audacious'

class BeepDriver(XmmsAlikeDriver):
  name = 'Beep driver (using xmmsalike)'
  flavor = 'beep'

DRIVERS = (DummyDriver, PyXmmsDriver, XmmsAlikeDriver, AudaciousDriver, BeepDriver)
