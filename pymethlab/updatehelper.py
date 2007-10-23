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

__all__ = ['UpdateHelper']

import threading

class UpdateHelper:
  def __init__(self, db, scanner_class):
    self.db = db
    self.scanner_class = scanner_class
    self.scanner = None
    
    self.lock = threading.Lock()
    self.stop_flag = threading.Event()
    self.stopped_flag = threading.Event()
    self.stopped_flag.set()
  
  def set_scanner_class(self, scanner_class):
    self.lock.acquire()
    if self.scanner:
      self.lock.release()
      self.stop()
      self.lock.acquire()
    self.scanner_class = scanner_class
    self.lock.release()
  
  def stop(self):
    self.stop_flag.set()
    self.stopped_flag.wait()
  
  def update(self, callback):
    def run_scanner():
      self.scanner.update()
      self.lock.acquire()
      self.scanner = None
      self.lock.release()
      self.stopped_flag.set()
      callback()
    if not self.stopped_flag.isSet():
      return False
    self.lock.acquire()
    self.stopped_flag.clear()
    self.stop_flag.clear()
    self.scanner = self.scanner_class(self.db, lambda: not self.stop_flag.isSet())
    threading.Thread(target = run_scanner).start()
    self.lock.release()
    return True
