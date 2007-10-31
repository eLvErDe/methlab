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

CreateRootTableQuery = '''
CREATE TABLE IF NOT EXISTS roots
(
  dir TEXT NOT NULL PRIMARY KEY
)'''
AddRootQuery = '''INSERT OR IGNORE INTO roots VALUES (?)'''
GetRootStartsWithQuery = '''SELECT dir FROM roots WHERE SUBSTR(dir, 1, ?) = ?'''
GetRootsQuery = '''SELECT dir FROM roots'''
DeleteRootQuery = '''DELETE FROM roots WHERE dir = ?'''

CreateDirTableQuery = '''
CREATE TABLE IF NOT EXISTS dirs
(
  dir TEXT NOT NULL PRIMARY KEY,
  mtime INTEGER,
  parent_id INTEGER
)'''

AddDirQuery = '''INSERT INTO dirs (dir, parent_id) VALUES (?, ?)'''
GetDirIdQuery = '''SELECT OID FROM dirs WHERE dir = ?'''
GetDirIdAndMtimeQuery = '''SELECT OID, mtime FROM dirs WHERE dir = ?'''
GetSubdirsByDirIdQuery = '''SELECT OID, dir FROM dirs WHERE parent_id = ?'''
GetDirsWithoutParentQuery = '''SELECT OID, dir FROM dirs WHERE parent_id IS NULL'''
GetDirsQuery = '''SELECT OID, dir FROM dirs'''
GetDirCountQuery = '''SELECT COUNT(*) FROM dirs'''
UpdateDirMtimeQuery = '''UPDATE dirs SET mtime = ? WHERE OID = ?'''
DeleteDirQuery = '''DELETE FROM dirs WHERE OID = ?'''
PurgeDirsQuery = '''DELETE FROM dirs'''

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
QueryTracksQuery = '''SELECT dirs.dir || filename AS path, dirs.dir AS dir, album, artist, comment, genre, title, track, year FROM tracks INNER JOIN dirs ON tracks.dir_id == dirs.OID WHERE %s'''
GetTrackCountQuery = '''SELECT COUNT(*) FROM tracks'''
PurgeTracksQuery = '''DELETE FROM tracks'''

DropSearchViewQuery = '''DROP VIEW IF EXISTS search'''
CreateSearchViewQuery = '''CREATE TEMPORARY VIEW search AS SELECT dirs.dir || filename AS path, dirs.dir AS dir, album, artist, comment, genre, title, track, year, %s AS field FROM tracks INNER JOIN dirs ON tracks.dir_id == dirs.OID'''
SearchTracksQuery = '''SELECT path, album, artist, comment, genre, title, track, year FROM search WHERE (%s)'''

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

PathToDirMigrationScript = '''
ALTER TABLE roots RENAME TO roots_old;
CREATE TABLE roots (dir TEXT NOT NULL PRIMARY KEY);
INSERT INTO roots (OID, dir) SELECT OID, path FROM roots_old;
DROP TABLE roots_old;
ALTER TABLE dirs RENAME TO dirs_old;
CREATE TABLE dirs (dir TEXT NOT NULL PRIMARY KEY, parent_id INTEGER);
INSERT INTO dirs (OID, dir, parent_id) SELECT OID, path, parent_id FROM dirs_old;
DROP TABLE dirs_old;
'''

CheckDirMtimeMigration = '''SELECT mtime FROM dirs'''
DirMtimeMigrationScript = '''
ALTER TABLE dirs RENAME TO dirs_old;
CREATE TABLE dirs (dir TEXT NOT NULL PRIMARY KEY, mtime INTEGER, parent_id INTEGER);
INSERT INTO dirs (OID, dir, parent_id) SELECT OID, dir, parent_id FROM dirs_old;
DROP TABLE dirs_old;
'''
