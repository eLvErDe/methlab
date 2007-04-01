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

__all__ = ['get_tag']

EXT_OPEN = ['.ogg', '.flac', '.mpc', '.mpp', '.mp+', '.wv']
EXT_PROP = ['.ape', '.wma', '.vqf']
EXT_MPEG = ['.mp3', '.m4a', '.mp4', '.m4p', '.aac']
EXT_WHITELIST = EXT_OPEN + EXT_PROP + EXT_MPEG

import os

class DummyTag:
  artist = ''
  album = ''
  comment = 'unsupported or no tag'
  genre = ''
  title = ''
  track = 0
  year = 0

class OldTagPyTagAbsorber:
  def __init__(self, tag):
    self.album = tag.album()
    self.artist = tag.artist()
    self.comment = tag.comment()
    self.genre = tag.genre()
    self.title = tag.title()
    self.track = tag.track()
    self.year = tag.year()

class MutagenTagAbsorber:
  def __init__(self, tag):
    self.album = self.get_value(tag, '', 'TALB', 'album')
    self.artist = self.get_value(tag, '', 'TPE1', 'artist')
    self.comment = self.get_value(tag, '', 'COMM', 'comment')
    self.genre = self.get_value(tag, '', 'TCON', 'genre')
    self.title = self.get_value(tag, '', 'TIT2', 'title')
    self.track = int(self.get_value(tag, '0', 'TRCK', 'tracknumber').split('/')[0])
    self.year = int(self.get_value(tag, '0', 'TYER', 'year'))

  def get_value(self, tag, default, *keys):
    for key in keys:
      if tag.has_key(key):
        return tag[key][0]
    return default

def get_tag_dummy(path):
  if os.path.splitext(path)[1].lower() in EXT_WHITELIST:
    print "Returning dummy tag for '%s'..." % path
    return DummyTag()
  return None

def get_tag_new_tagpy(path):
  f = tagpy.FileRef(path)
  if not f.isNull():
    return f.tag()
  return get_tag_dummy(path)

def get_tag_old_tagpy(path):
  f = tagpy.FileRef(path)
  if f.isValid():
    return OldTagPyTagAbsorber(f.tag())
  return get_tag_dummy(path)

def get_tag_mutagen(path):
  tag = mutagen.File(path)
  if tag:
    return MutagenTagAbsorber(tag)
  return get_tag_dummy(path)

try:
  import tagpy
  if type(tagpy.Tag.track) is property:
    print 'Using new (>= 0.91) TagPy as tag library'
    get_tag = get_tag_new_tagpy
  else:
    print 'Using old (< 0.91) TagPy as tag library'
    get_tag = get_tag_old_tagpy
except ImportError:
  try:
    import mutagen
    print 'Using mutagen as tag library'
    get_tag = get_tag_mutagen
  except ImportError:
    print 'WARNING: Using dummy tagger since no tag library was found'
    get_tag = get_tag_dummy
