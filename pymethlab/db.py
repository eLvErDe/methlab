#! /usr/bin/env python

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

__all__ = ['DBThread']

import os
import threading
import Queue

try:
  import sqlite3 as sqlite
except ImportError:
  try:
    from pysqlite2 import dbapi2 as sqlite
  except ImportError:
    print "Couldn't find pysqlite 2 or 3. Bailing out."
    raise

from querytranslator import *
from dbqueries import *

class DBMessage:
  def __init__(self, query, args, event = None, script = False):
    self.query = query
    self.args = args
    self.event = event
    self.script = script
    self.result = None

class DBThread(threading.Thread):
  def __init__(self, path = None, scanner_class = None):
    threading.Thread.__init__(self)
    self.queue = Queue.Queue()
    self.lock = threading.Lock()
    if path is None:
      path = os.path.expanduser(os.path.join('~', '.methlab', 'methlab.db'))
    dir = os.path.split(path)[0]
    if not os.path.exists(dir):
      os.makedirs(dir)
    self.path = path

    self.scanner_class = scanner_class
  
  def start(self):
    threading.Thread.start(self)
    self.execute(CreateRootTableQuery)
    self.execute(CreateDirTableQuery)
    self.execute(CreateTrackTableQuery)
    self.execute(CreateSearchTableQuery)
    self.migrate_path_to_dir()
    self.set_sort_order('album', 'track', 'title')
    self.set_search_fields('artist', 'album', 'title')

  def run(self):
    conn = sqlite.connect(self.path)
    conn.isolation_level = None
    conn.text_factory = str
    conn.row_factory = sqlite.Row
    cursor = conn.cursor()
    while 1:
      msg = self.queue.get()
      if not msg:
        break
      if msg.script:
        cursor.executescript(msg.query, msg.args)
      else:
        cursor.execute(msg.query, msg.args)
      msg.result = cursor.fetchall()
      if msg.event:
        msg.event.set()
    conn.close()

  def stop(self):
    self.queue.put(None)
  
  def execute(self, query, args = []):
    msg = DBMessage(query, args, threading.Event())
    self.queue.put(msg)
    msg.event.wait()
    return msg.result

  def executescript(self, query, args = []):
    msg = DBMessage(query, args, threading.Event(), True)
    self.queue.put(msg)
    msg.event.wait()
    return msg.result

  def migrate_path_to_dir(self):
    try:
      self.get_roots()
    except sqlite.OperationalError:
      print 'Note: Migrating database (rename path to dir in roots and dirs).'
      self.executescript(PathToDirMigrationScript)

  def get_scanner_class(self):
    self.lock.acquire()
    scanner_class = self.scanner_class
    self.lock.release()
    return scanner_class

  def set_scanner_class(self, scanner_class):
    self.lock.acquire()
    self.scanner_class = scanner_class
    self.lock.release()

  def purge(self):
    self.execute(PurgeDirsQuery)
    self.execute(PurgeTracksQuery)

  def update(self, yield_func):
    scanner = self.get_scanner_class()(self, yield_func)
    scanner.update()

  def add_root(self, dir):
    dir = os.path.join(os.path.abspath(dir), '')
    symbols = (len(dir), dir)
    result = self.execute(GetRootStartsWithQuery, symbols)
    for row in result:
      if row[0] != dir:
        self.delete_root(row[0])
    symbols = (dir, )
    self.execute(AddRootQuery, symbols)

  def get_roots(self):
    return self.execute(GetRootsQuery)

  def delete_root(self, dir):
    symbols = (dir, )
    row = self.execute(GetDirIdQuery, symbols).fetchone()
    if row is not None:
      self.delete_dir_by_dir_id(row[0])
    self.execute(DeleteRootQuery, symbols)

  def get_dir_id(self, parent, dir):
    symbols = (dir, )
    row = self.execute(GetDirIdQuery, symbols)[:1]
    if not row:
      symbols = (dir, parent)
      self.execute(AddDirQuery, symbols)
      return self.get_dir_id(parent, dir)
    else:
      return row[0][0]

  def get_subdirs_by_dir_id(self, dir_id):
    symbols = (dir_id, )
    return self.execute(GetSubdirsByDirIdQuery, symbols)

  def get_dirs(self):
    return self.execute(GetDirsQuery)

  def delete_dir_by_dir_id(self, dir_id):
    symbols = (dir_id, )
    result = self.execute(GetSubdirsByDirIdQuery, symbols)
    for row in result:
      print "Purging '%s' because of recursion..." % row[1]
      self.delete_dir_by_dir_id(row[0])
    self.execute(DeleteTracksByDirIdQuery, symbols)
    self.execute(DeleteDirQuery, symbols)

  def get_track_mtime(self, dir_id, filename):
    symbols = (dir_id, filename)
    row = self.execute(GetTrackMtimeQuery, symbols)[:1]
    if not row:
      return 0
    else:
      return row[0]

  def add_track(self, dir_id, filename, mtime, tag):
    symbols = (dir_id, filename, mtime, tag.album, tag.artist, tag.comment, tag.genre, tag.title, tag.track, tag.year)
    self.execute(AddTrackQuery, symbols)

  def get_filenames_by_dir_id(self, dir_id):
    symbols = (dir_id, )
    return self.execute(GetFilenamesByDirIdQuery, symbols)

  def delete_track(self, dir_id, filename):
    symbols = (dir_id, filename)
    self.execute(DeleteTrackQuery, symbols)

  def set_search_fields(self, *fields):
    self.execute(DropSearchViewQuery)
    if fields:
      symbol = ' || " " || '.join(fields)
      symbol = symbol.replace('path', 'dirs.dir || filename')
      self.execute(CreateSearchViewQuery % symbol)

  def set_sort_order(self, *fields):
    self.lock.acquire()
    self.sort_order = []
    for field in fields:
        self.sort_order.append(field)
    self.lock.release()

  def get_sort_order(self):
    self.lock.acquire()
    if self.sort_order:
      result = ' ORDER BY ' + ', '.join(self.sort_order)
    else:
      result = ''
    self.lock.release()
    return result

  def query_tracks(self, query):
    query, symbols = translate_query(query)
    query = QueryTracksQuery % query + self.get_sort_order()
    return self.execute(query, symbols)

  def search_tracks(self, query):
    # Chop op the query:
    # a b | c d --> (a AND b) OR (c AND d)

    clauses = []
    symbols = []

    queries = [q.strip() for q in query.split('|') if q.strip()]
    queries = [[p.strip() for p in q.split() if p.strip()] for q in queries]
    for query in queries:
      clauses.append(' AND '.join(['field LIKE ?'] * len(query)))
      symbols += ['%%%s%%' % part for part in query]

    query = SearchTracksQuery % ') OR ('.join(clauses)
    query += self.get_sort_order()
    return self.execute(query, symbols)

  def get_distinct_track_info(self, *fields):
    symbol = ', '.join(fields)
    return self.execute(GetDistinctTrackInfoQuery % symbol)

  def get_artists(self):
    return self.get_distinct_track_info('artist')

  def get_albums(self):
    return self.get_distinct_track_info('album')

  def get_artists_albums(self):
    return self.get_distinct_track_info('artist', 'album')

  def add_search(self, name, query, fields):
    symbols = (name, query, fields)
    self.execute(AddSearchQuery, symbols)

  def get_searches(self):
    return self.execute(GetSearchesQuery)

  def delete_search(self, name):
    symbols = (name, )
    self.execute(DeleteSearchQuery, symbols)

if __name__ == '__main__':
  db = DBThread()
  db.start()
  print 'pong'
  db.stop()
  print 'done!'
