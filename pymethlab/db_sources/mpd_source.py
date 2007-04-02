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

DB_SOURCES = ['MpdSource']

import os, stat, mpdclient3
from gettext import gettext as _

class MpdTagAbsorber:
  def __init__(self, info):
    self.album = info.get('album', '')
    self.title = info.get('title', '')
    self.track = int(info.get('track', '0').split('/')[0])
    self.artist = info.get('artist', '')
    self.genre = info.get('genre', '')
    self.year = int(info.get('date', '0'))
    self.comment = info.get('comment', '')
                                     
class MpdSource:
  name = 'mpd'
  name_tr = _('Music Player Daemon')
  def __init__(self, db, yield_func = None):
    self.db = db
    self.yield_func = yield_func

  def update(self):
    self.yield_func()
    mpd = mpdclient3.connect()
    mpd_tracks = mpd.do.listallinfo()

    found = {}
    for mpd_track in mpd_tracks:
      self.yield_func()
      if mpd_track['type'] == 'file':
        dir, filename = os.path.split(mpd_track['file'])
        dir = os.path.join(dir, '')
        dir_id = self.db.get_dir_id(None, dir)
        if not dir in found:
          found[dir] = [filename]
        else:
          found[dir].append(filename)
        if self.db.get_track_mtime(dir_id, filename) == 0:
          tag = MpdTagAbsorber(mpd_track)
          self.db.add_track(dir_id, filename, 1, tag)

    db_subdirs = self.db.get_subdirs_by_dir_id(dir_id)
    for subdir in db_subdirs:
      if not subdir[1] in found.keys():
        self.db.delete_dir_by_dir_id(subdir[0])

    for dir, filenames in found.items():
      dir_id = self.db.get_dir_id(None, dir)
      db_filenames = self.db.get_filenames_by_dir_id(dir_id)
      for filename in db_filenames:
        if not filename[0] in filenames:
          self.db.delete_track(dir_id, filename[0])
