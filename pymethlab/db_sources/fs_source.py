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

DB_SOURCES = ['FilesystemSource']

import os, stat
from tagwrap import get_tag

class FilesystemSource:
  name = 'Filesystem'
  def __init__(self, db, yield_func = None):
    self.db = db
    self.yield_func = yield_func

  def update(self):
    dirs = self.db.get_roots()
    for dir in dirs:
      self.update_dir(None, dir[0])
      if self.yield_func:
        self.yield_func()

  def update_dir(self, parent, dir):
    print 'Checking %s' % dir
    dir_id = self.db.get_dir_id(parent, dir)

    found_subdirs = []
    found_files = []

    files = os.listdir(dir)
    for file in files:
      if file[:1] == '.':
        continue
      if self.yield_func:
        self.yield_func()
      path = dir + file
      statdata = os.stat(path)
      if stat.S_ISDIR(statdata.st_mode):
        if not os.access(path, os.R_OK | os.X_OK):
          continue
        found_subdirs.append(os.path.join(path, ''))
        self.update_dir(dir_id, os.path.join(path, ''))
      elif stat.S_ISREG(statdata.st_mode):
        if not os.access(path, os.R_OK):
          continue
        found_files.append(file)
        if self.db.get_track_mtime(dir_id, file) != statdata.st_mtime:
          tag = get_tag(path)
          if tag:
            self.db.add_track(dir_id, file, long(statdata.st_mtime), tag)
          else:
            print "Skipping '%s'..." % path

    db_subdirs = self.db.get_subdirs_by_dir_id(dir_id)
    for subdir in db_subdirs:
      if not subdir[1] in found_subdirs:
        print "Purging dir '%s'..." % subdir[1]
        self.db.delete_dir_by_dir_id(subdir[0])

    db_filenames = self.db.get_filenames_by_dir_id(dir_id)
    for filename in db_filenames:
      if not filename[0] in found_files:
        print "Purging track '%s'..." % (dir + filename[0])
        self.db.delete_track(dir_id, filename[0])