#! /usr/bin/env python

from distutils.core import setup
import os, sys

def locale_enum(ext):
  ret_val = []
  for lang in os.listdir('locale'):
    path = os.path.join('locale', lang, 'methlab' + ext)
    if not os.path.exists(path):
      continue
    ret_val.append((lang, path))
  return ret_val

def compile_po_files():
  for lang, po_file in locale_enum('.po'):
    mo_file = os.path.splitext(po_file)[0] + '.mo'
    print 'Compiling %s to %s' % (po_file, mo_file)
    os.system('msgfmt "%s" -o "%s"' % (po_file, mo_file))

def mo_files():
  ret_val = []
  for lang, mo_file in locale_enum('.mo'):
    dir = os.path.join(sys.prefix, 'share', 'locale', lang, 'LC_MESSAGES')
    ret_val.append((dir, [mo_file]))
  return ret_val

if __name__ == '__main__':
  compile_po_files()

  setup(name = 'methlab',
        version = '0.0.0',
        description = 'MethLab Music Library',
        author = 'Ingmar K. Steen',
        author_email = 'iksteen@gmail.com',
        url = 'http://thegraveyard.org/',
        license = 'GPL',
        scripts = ['methlab', 'methlab-db'],
        packages = ['pymethlab'],
        package_data = {'pymethlab': ['*.glade']},
        data_files = mo_files(),
  )
