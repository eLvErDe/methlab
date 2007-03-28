#! /usr/bin/env python

from distutils.core import setup

setup(name = 'methlab',
      version = '0.0.0',
      description = 'MethLab Music Library',
      author = 'Ingmar K. Steen',
      author_email = 'iksteen@gmail.com',
      url = 'http://thegraveyard.org/',
      license = 'GPL',
      scripts = ['methlab', 'methlab-db'],
      packages = ['pymethlab'],
#      package_dir = {'pymethlab': 'pymethlab'},
      package_data = {'pymethlab': ['*.glade']},
)
      