#! /usr/bin/python

"""
xmmsalike.py is an alternative to pyxmms, the interface module to the
XMMS media player. It should work with XMMS as well as its successors,
the Beep Media Player and Audacious, while being somewhat limited in
functionality compared to pyxmms. It uses the ctypes library that is
available as an extra Python package.

It was originally created by Ben Wolfson as published at
http://waste.typepad.com/waste/2006/03/ctypes_rules.html

This version is being developed by Risto A. Paju
(http://iki.fi/teknohog/), and distributed with permission from B. W.

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or (at
your option) any later version.

This program is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307,
USA.

Changelog
=========

20061102:
First release

20061103:
init()

20061103b:
config file access basics, config_get()

"""

import os
from ctypes import *

import ConfigParser
config = ConfigParser.SafeConfigParser()

library = None
libraries = ("beep", "audacious", "xmms")

class LibraryNotFound(IOError): pass
class InvalidLibrary(ValueError): pass

def swaplibrary(libname, searchpath=("/usr/lib","/usr/local/lib")):
    global library, config
    if libname not in libraries:
        raise InvalidLibrary
    soname = "lib%s.so" % libname
    for path in searchpath:
        j = os.path.join(path, soname)
        if os.path.exists(j):
            library = cdll.LoadLibrary(j)

            config.read(os.path.expanduser("~/." + libname + "/config"))

            return
    raise LibraryNotFound

# by teknohog
# note to self: you can initialize this library without the running
# player, but then you need to provide libname. But if you need to
# detect which one is running, you obviously need it running, and the
# is_running state takes a while after you start the application.
def init(libname=""):
    global library_name
    if libname in libraries:
        swaplibrary(libname)
    else:
        for lib in libraries:
            try:
                swaplibrary(lib)
                if is_running():
                    libname = lib
                    break
            except:
                pass
    library_name = libname
    # the actual string may not be very useful for comms etc., but at
    # least it tells something about success...
    return libname

# changed by teknohog to reflect pyxmms behaviour
def playlist(files, enq, s=0):
    num = len(files)
    arrclass = c_char_p * num
    filearr = arrclass()
    for i, f in enumerate(files):
        filearr[i] = c_char_p(f)
    library.xmms_remote_playlist(s, filearr, num, enq)

playlist_add = lambda files, s=0: playlist(files, 1, s)
playlist_set = lambda files, s=0: playlist(files, 0, s)

def get_volume(s=0):
    vl = pointer(c_int())
    vr = pointer(c_int())
    library.xmms_remote_get_volume(s, vl, vr)
    return vl.contents.value, vr.contents.value

def set_volume(vl, vr, s=0):
    library.xmms_remote_set_volume(s, vl, vr)

def get_info(s=0):
    rate = pointer(c_int())
    freq = pointer(c_int())
    nch = pointer(c_int())
    library.xmms_remote_get_info(s, rate, freq, nch)
    return rate.contents.value, freq.contents.value, nch.contents.value

def funcstring(name):
    return lambda s, sess=0: getattr(library, name)(c_char_p(s), sess)
set_skin = funcstring("xmms_remote_set_skin")
playlist_add_url_string = funcstring("xmms_remote_playlist_add_url_string")
del funcstring

#def get_eq(s=0):
#    preamp = pointer(c_float())
#    bands = pointer(pointer(c_float()))
# hmm...  Don't really know what to do with this one.    
    

def playlist_ins_url_string(s, pos, sess=0):
    return library.xmms_remote_playlist_ins_url_string(sess, c_char_p(s), pos)

def func0(name):
    return lambda s=0: getattr(library, name)(s)
def string_func0(name):
    def func(s=0):
        r = getattr(library, name)(s)
        return c_char_p(r).value
    return func
def func1int(name):
    return lambda i, s=0: getattr(library, name)(s,int(i))
def string_func1int(name):
    def func(i, s=0):
        r = getattr(library, name)(s,int(i))
        return c_char_p(r).value
    return func

for n in "play pause stop is_playing is_paused get_output_time playlist_clear \
get_playlist_pos get_playlist_length get_main_volume get_balance Sget_skin \
is_main_win is_pl_win is_eq_win show_prefs_box eject playlist_prev playlist_next \
is_running toggle_repeat toggle_shuffle is_repeat is_shuffle get_eq_preamp \
quit play_pause get_playqueue_length toggle_advance is_advance".split():
    if n[0] == 'S':
        n = n[1:]
        f = 'string_func0'
    else:
        f = 'func0'
    exec "%s = %s('xmms_remote_%s')" % (n,f,n)

for n in "playlist_delete set_playlist_pos jump_to_time set_main_volume set_balance \
Sget_playlist_file Sget_playlist_title get_playlist_time main_win_toggle pl_win_toggle \
eq_win_toggle toggle_aot get_eq_band playqueue_add playqueue_remove".split():
    if n[0] == 'S':
        n = n[1:]
        f = 'string_func1int'
    else:
        f = 'func1int'
    exec "%s = %s('xmms_remote_%s')" % (n,f,n)

del func0, string_func0, func1int, string_func1int

# for example config_get("CDDA", "device") returns '/dev/cdrom' or equivalent.
def config_get(section, option):
    return config.get(section, option)
