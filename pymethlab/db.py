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

__all__ = ['DB']

import os
try:
  import sqlite3 as sqlite
except ImportError:
  try:
    from pysqlite2 import dbapi2 as sqlite
  except ImportError:
    print "Couldn't find pysqlite 2 or 3. Bailing out."
    raise

from querytranslator import *

CreateRootTableQuery = '''
CREATE TABLE IF NOT EXISTS roots
(
  path TEXT NOT NULL PRIMARY KEY
)'''
AddRootQuery = '''INSERT OR IGNORE INTO roots VALUES (?)'''
GetRootStartsWithQuery = '''SELECT path FROM roots WHERE SUBSTR(path, 1, ?) = ?'''
GetRootsQuery = '''SELECT path FROM roots'''
DeleteRootQuery = '''DELETE FROM roots WHERE path = ?'''

CreateDirTableQuery = '''
CREATE TABLE IF NOT EXISTS dirs
(
  path TEXT NOT NULL PRIMARY KEY,
  parent_id INTEGER
)'''
AddDirQuery = '''INSERT INTO dirs VALUES (?, ?)'''
GetDirIdQuery = '''SELECT OID FROM dirs WHERE path = ?'''
GetSubdirsByDirIdQuery = '''SELECT OID, path FROM dirs WHERE parent_id = ?'''
DeleteDirQuery = '''DELETE FROM dirs WHERE OID = ?'''

CreateTrackTableQuery = '''
CREATE TABLE IF NOT EXISTS tracks
(
  dir_id INTEGER,
  filename TEXT NOT NULL,
  mtime INTEGER,
  album TEXT,
  artist TEXT,
  comment TEXT,
  genre TEXT,
  title TEXT,
  track INTEGER,
  year INTEGER,
  PRIMARY KEY (dir_id, filename)
)'''
GetTrackMtimeQuery = '''SELECT mtime FROM tracks WHERE dir_id = ? AND filename = ?'''
AddTrackQuery = '''INSERT OR REPLACE INTO tracks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'''
GetFilenamesByDirIdQuery = '''SELECT filename FROM tracks WHERE dir_id = ?'''
DeleteTrackQuery = '''DELETE FROM tracks WHERE dir_id = ? AND filename = ?'''
DeleteTracksByDirIdQuery = '''DELETE FROM tracks WHERE dir_id = ?'''
GetDistinctTrackInfoQuery = '''SELECT DISTINCT %s FROM tracks'''
QueryTracksQuery = '''SELECT dirs.path || filename AS path, album, artist, comment, genre, title, track, year FROM tracks INNER JOIN dirs ON tracks.dir_id == dirs.OID WHERE %s ORDER BY artist, year, album, track, title'''

DropSearchViewQuery = '''DROP VIEW IF EXISTS search'''
CreateSearchViewQuery = '''CREATE TEMPORARY VIEW search AS SELECT dirs.path || filename AS path, album, artist, comment, genre, title, track, year, %s AS field FROM tracks INNER JOIN dirs ON tracks.dir_id == dirs.OID'''

CreateSearchTableQuery = '''
CREATE TABLE IF NOT EXISTS searches
(
  name TEXT NOT NULL PRIMARY KEY,
  query TEXT,
  fields TEXT
)'''
AddSearchQuery = '''INSERT OR REPLACE INTO searches VALUES (?, ?, ?)'''
GetSearchesQuery = '''SELECT * FROM searches'''
DeleteSearchQuery = '''DELETE FROM searches WHERE name = ?'''

class DB:
  def __init__(self, path = None):
    if path is None:
      path = os.path.expanduser('~/.methlab/methlab.db')
    dir = os.path.split(path)[0]
    if not os.path.exists(dir):
      os.makedirs(dir)
    self.path = path

    self.scanner = None

    self.conn = conn = sqlite.connect(path)
    conn.isolation_level = None
    conn.text_factory = str
    conn.row_factory = sqlite.Row
    cursor = conn.cursor()
    cursor.execute(CreateRootTableQuery)
    cursor.execute(CreateDirTableQuery)
    cursor.execute(CreateTrackTableQuery)
    cursor.execute(CreateSearchTableQuery)
    self.set_search_fields('artist', 'album', 'title')

  def __del__(self):
    self.conn.close()

  def update(self, yield_func):
    from scanner import Scanner
    scanner = Scanner(self, yield_func)
    scanner.update()

  def add_root(self, path):
    path = os.path.abspath(path) + '/'
    cursor = self.conn.cursor()
    symbols = (len(path), path)
    result = cursor.execute(GetRootStartsWithQuery, symbols)
    for row in result:
      if row[0] != path:
        self.delete_root(row[0])
    symbols = (path, )
    cursor.execute(AddRootQuery, symbols)

  def get_roots(self):
    cursor = self.conn.cursor()
    return cursor.execute(GetRootsQuery)

  def delete_root(self, path):
    cursor = self.conn.cursor()
    symbols = (path, )
    row = cursor.execute(GetDirIdQuery, symbols).fetchone()
    if row is not None:
      self.delete_dir_by_dir_id(row[0])
    cursor.execute(DeleteRootQuery, symbols)

  def get_dir_id(self, parent, path):
    cursor = self.conn.cursor()
    symbols = (path, )
    row = cursor.execute(GetDirIdQuery, symbols).fetchone()
    if row is None:
      symbols = (path, parent)
      cursor.execute(AddDirQuery, symbols)
      return self.get_dir_id(parent, path)
    else:
      return row[0]

  def get_subdirs_by_dir_id(self, dir_id):
    cursor = self.conn.cursor()
    symbols = (dir_id, )
    return cursor.execute(GetSubdirsByDirIdQuery, symbols)

  def delete_dir_by_dir_id(self, dir_id):
    cursor = self.conn.cursor()
    symbols = (dir_id, )
    result = cursor.execute(GetSubdirsByDirIdQuery, symbols)
    for row in result:
      print "Purging '%s' because of recursion..." % row[1]
      self.delete_dir_by_dir_id(row[0])
    cursor.execute(DeleteTracksByDirIdQuery, symbols)
    cursor.execute(DeleteDirQuery, symbols)

  def get_track_mtime(self, dir_id, filename):
    cursor = self.conn.cursor()
    symbols = (dir_id, filename)
    row = cursor.execute(GetTrackMtimeQuery, symbols).fetchone()
    if row is None:
      return 0
    else:
      return row[0]

  def add_track(self, dir_id, filename, mtime, tag):
    cursor = self.conn.cursor()
    symbols = (dir_id, filename, mtime, tag.album, tag.artist, tag.comment, tag.genre, tag.title, tag.track, tag.year)
    symbols_ = []
    for symbol in symbols:
      if callable(symbol):
        symbols_.append(symbol())
      else:
        symbols_.append(symbol)
    cursor.execute(AddTrackQuery, symbols_)

  def get_filenames_by_dir_id(self, dir_id):
    cursor = self.conn.cursor()
    symbols = (dir_id, )
    cursor = cursor.execute(GetFilenamesByDirIdQuery, symbols)
    return cursor

  def delete_track(self, dir_id, filename):
    cursor = self.conn.cursor()
    symbols = (dir_id, filename)
    cursor.execute(DeleteTrackQuery, symbols)

  def set_search_fields(self, *fields):
    cursor = self.conn.cursor()
    cursor.execute(DropSearchViewQuery)
    if fields:
      symbol = ' || " " ||'.join(fields)
      cursor.execute(CreateSearchViewQuery % symbol)

  def find_tracks(self, **kwargs):
    cursor = self.conn.cursor()
    query = 'SELECT * FROM search WHERE'
    symbols = []
    where = ''
    for key, value in kwargs.items():
      if where:
        where += ' AND'
      where += ' ' + key + ' LIKE ?'
      symbols.append(value)
    return cursor.execute(query + ' ' + where, symbols)

  def query_tracks(self, query):
    cursor = self.conn.cursor()
    query, symbols = translate_query(query)
    query = QueryTracksQuery % query
    return cursor.execute(query, symbols)

  def search(self, *args):
    cursor = self.conn.cursor()
    query = "SELECT * FROM search WHERE"
    for i in range(len(args)):
      if i > 0:
        query += ' AND'
      query += ' field LIKE ?'
    query += ' ORDER BY artist, album, track, title'
    symbols = tuple(['%%%s%%' % arg for arg in args])
    return cursor.execute(query, symbols)

  def get_distinct_track_info(self, *fields):
    cursor = self.conn.cursor()
    symbol = ', '.join(fields)
    return cursor.execute(GetDistinctTrackInfoQuery % symbol)

  def get_artists(self):
    return self.get_distinct_track_info('artist')

  def get_albums(self):
    return self.get_distinct_track_info('album')

  def get_artists_albums(self):
    return self.get_distinct_track_info('artist', 'album')

  def add_search(self, name, query, fields):
    cursor = self.conn.cursor()
    symbols = (name, query, fields)
    cursor.execute(AddSearchQuery, symbols)

  def get_searches(self):
    cursor = self.conn.cursor()
    return cursor.execute(GetSearchesQuery)

  def delete_search(self, name):
    cursor = self.conn.cursor()
    symbols = (name, )
    cursor.execute(DeleteSearchQuery, symbols)
