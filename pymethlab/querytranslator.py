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

__all__ = ['QueryTranslatorException', 'translate_query']

import string

class QueryTranslatorException(Exception):
  pass

class QueryTranslator:
  SYMBOLS = ('(', ')', '=', '!=')
  KEYWORDS = ('AND', 'OR')

  def __init__(self):
    self.query = None
    self.sql_query = None
    self.sql_symbols = None

  def is_safe(self, token):
    for c in token:
      if not c in string.ascii_letters:
        return False
    return True

  def parse(self, query):
    self.query = query
    self.sql_query = ''
    self.sql_symbols = []

    level = 0
    state = 0
    while self.query:
      token = self.get_token()
      if token is None:
        continue

      if state == 0:
        if token == '(':
          level += 1
          self.sql_query += '('
        elif token == 'NOT':
          self.sql_query += 'NOT '
        elif token in self.SYMBOLS:
          raise QueryTranslatorException('Unexpected symbol %s' % token)
        elif token in self.KEYWORDS:
          raise QueryTranslatorException('Unexpected keyword %s' % token)
        else:
          if not self.is_safe(token):
            raise QueryTranslatorException('Unsafe field %s' % token)
          self.sql_query += token
          state = 1

      elif state == 1:
        if token == '=':
          self.sql_query += ' LIKE ?'
        elif token == '!=':
          self.sql_query += ' NOT LIKE ?'
        elif token in self.SYMBOLS:
          raise QueryTranslatorException('Unexpected symbol %s' % token)
        elif token in self.KEYWORDS:
          raise QueryTranslatorException('Unexpected keyword %s' % token)
        else:
          raise QueryTranslatorException('Unexpected string %s' % token)
        state = 2

      elif state == 2:
        if token in self.SYMBOLS:
          raise QueryTranslatorException('Unexpected symbol %s' % token)
        elif token in self.KEYWORDS:
          raise QueryTranslatorException('Unexpected keyword %s' % token)
        self.sql_symbols.append(token)
        state = 3

      elif state == 3:
        if token in ('AND', 'OR'):
          self.sql_query += ' ' + token + ' '
          state = 0
        elif token == ')':
          level -= 1
          state = 3
          self.sql_query += ')'
        elif token in self.SYMBOLS:
          raise QueryTranslatorException('Unexpected symbol %s' % token)
        elif token in self.KEYWORDS:
          raise QueryTranslatorException('Unexpected keyword %s' % token)
        else:
          raise QueryTranslatorException('Unexpected string %s' % token)

    if level > 0:
      raise QueryTranslatorException('Unbalanced (')
    elif level < 0:
      raise QueryTranslatorException('Unbalanced )')

  def get_token(self):
    if not self.query:
      return None

    c = self.query[0]

    if c == ' ':
      self.query = self.query[1:]
      return None

    for symbol in self.SYMBOLS:
      if self.query[:len(symbol)] == symbol:
        self.query = self.query[len(symbol):]
        return symbol

    if c in ('"', "'"):
      return self.get_string_token()
    else:
      return self.get_word_token()

  def get_string_token(self):
    quote = self.query[0]

    self.query = self.query[1:]
    if not self.query:
      raise QueryTranslatorException('Unterminated string near end of query')

    token = ''
    escape = False
    while not (self.query[0] == quote and not escape):
      c = self.query[0]
      if escape:
        token += c
        escape = False
      elif c == '\\':
        escape = True
      else:
        token += c
      self.query = self.query[1:]
      if not self.query:
        raise QueryTranslatorException('Unterminated string near end of query')
    self.query = self.query[1:]
    return token

  def get_word_token(self):
    token = ''
    while self.query and not self.query[0] in self.SYMBOLS + (' ', ):
      token += self.query[0]
      self.query = self.query[1:]
    return token

def translate_query(query):
  t = QueryTranslator()
  t.parse(query)
  return t.sql_query, tuple(t.sql_symbols)
