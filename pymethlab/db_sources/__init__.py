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

__all__ = ['DB_SOURCES']

def init():
  db_sources = []
  import os, glob
  dirname = os.path.split(__file__)[0]
  for path in glob.glob(os.path.join(dirname, '*.py')):
    filename = os.path.split(path)[1]
    name = os.path.splitext(filename)[0]
    if name == '__init__':
      continue
    mod = __import__(name, globals(), locals(), ['DB_SOURCES'], -1)
    if hasattr(mod, 'DB_SOURCES'):
      for db_source in mod.DB_SOURCES:
        db_sources.append(getattr(mod, db_source))
  return db_sources

DB_SOURCES = init()
for db_source in DB_SOURCES:
  print `db_source.__name__`
  locals()[db_source.__name__] = db_source
del db_source
