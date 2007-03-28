#  methlab - A music library application
#  Copyright (C) 2007 Ingmar K. Steen (iksteen@gmail.com)
#
LICENSE = '''
  This program is free software; you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation; either version 2 of the License, or
  (at your option) any later version.

  This program is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU General Public License for more details.

  You should have received a copy of the GNU General Public License
  along with this program; if not, write to the Free Software
  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
'''

import os
import gobject
import gtk
import gtk.glade
import sqlite3
from ConfigParser import ConfigParser
from db import DB
from querytranslator import QueryTranslatorException
from drivers import DRIVERS, DummyDriver

# Case insensitive string compare
def case_insensitive_cmp(model, a, b):
  return cmp(model.get_value(a, 0).upper(), model.get_value(b, 0).upper())

# Quote and escape a string to be used in a query
def query_escape(s):
  return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

# The main window
class MethLabWindow:
  def __init__(self):
    # Set the default configuration and load the configuration file
    self.config = ConfigParser()
    self.config.add_section('options')
    self.config.set('options', 'driver', DummyDriver.name)
    self.config.set('options', 'update_on_startup', 'True')
    self.config.read(os.path.expanduser('~/.methlab/config'))

    # Create our database back-end
    self.db = DB()

    # If this value is not 0, searches will not occur
    self.inhibit_search = 1

    # Some timeout tags we may wish to cancel
    self.search_timeout_tag = None
    self.flash_timeout_tag = None

    # Load the gui from the XML file
    self.gladefile = os.path.join(os.path.split(__file__)[0], 'methlab.glade')
    wtree = gtk.glade.XML(self.gladefile)

    # Map the widgets from the wtree to the class
    for w in wtree.get_widget_prefix(''):
      setattr(self, w.name, w)

    # Create the audio-player back-end
    self.set_driver(self.config.get('options', 'driver'))

    # Build the menus
    self.build_menus()

    # Set up the search options
    self.set_active_search_fields()

    # Create a cell renderer we re-use
    cell_renderer = gtk.CellRendererText()

    # Set up the artists / albums model
    self.artists_albums_model = gtk.TreeStore(str)
    self.artists_albums_model.set_sort_func(0, case_insensitive_cmp)
    self.artists_albums_model.set_sort_column_id(0, gtk.SORT_ASCENDING)
    self.artist_iters = {}
    self.album_iters = {}
    self.update_artists_albums_model()

    # Set up the artists / albums tree view
    col = gtk.TreeViewColumn("Artist / Album", cell_renderer, text = 0)
    self.tvArtistsAlbums.append_column(col)
    self.tvArtistsAlbums.set_model(self.artists_albums_model)
    self.tvArtistsAlbums.expand_all()
    self.tvArtistsAlbums.get_selection().connect('changed', self.on_artists_albums_selection_changed)
    self.tvArtistsAlbums.get_selection().set_mode(gtk.SELECTION_MULTIPLE)

    # Set up the saved searches model
    self.searches_model = gtk.ListStore(str, str, str)
    self.searches_model.set_sort_func(0, case_insensitive_cmp)
    self.searches_model.set_sort_column_id(0, gtk.SORT_ASCENDING)
    self.search_iters = {}
    self.update_searches_model()

    # Set up the saved searches tree view
    self.tvSearches.append_column(gtk.TreeViewColumn("Saved search", cell_renderer, text = 0))
    self.tvSearches.set_model(self.searches_model)
    self.tvSearches.get_selection().connect('changed', self.on_searches_selection_changed)
    self.tvSearches.connect('button-press-event', self.on_searches_button_press_event)

    # Set up the search history model
    self.history_model = gtk.ListStore(str)
    self.cbeSearch.set_model(self.history_model)

    # Set up the search results model
    self.results_model = gtk.ListStore(str, str, str, int, str, int, str, str)
    # 0: Path
    self.results_model.set_sort_func(0, case_insensitive_cmp)
    # 1: Artist
    self.results_model.set_sort_func(1, case_insensitive_cmp)
    # 2: Album
    self.results_model.set_sort_func(2, case_insensitive_cmp)
    # 3: Track#
    # 4: Title
    self.results_model.set_sort_func(4, case_insensitive_cmp)
    # 5: Year
    # 6: Genre
    self.results_model.set_sort_func(6, case_insensitive_cmp)
    # 7: Comment
    self.results_model.set_sort_func(7, case_insensitive_cmp)

    # Set up the results tree view
    self.tvResults.append_column(gtk.TreeViewColumn('Artist', cell_renderer, text = 1))
    self.tvResults.append_column(gtk.TreeViewColumn('Album', cell_renderer, text = 2))
    self.tvResults.append_column(gtk.TreeViewColumn('#', cell_renderer, text = 3))
    self.tvResults.append_column(gtk.TreeViewColumn('Title', cell_renderer, text = 4))
    for col in self.tvResults.get_columns():
      col.set_sizing(gtk.TREE_VIEW_COLUMN_AUTOSIZE)
      col.set_reorderable(True)
    self.tvResults.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
    self.tvResults.set_model(self.results_model)

    # Fix and hook up the expanders
    self.sidebar_expanders = wtree.get_widget_prefix('exp')
    for w in self.sidebar_expanders:
      w.connect('notify::expanded', self.on_expander_expanded)
    self.expSearchOptions.set_expanded(True)

    # Hook up the search options
    self.cbSearchPath.connect('toggled', self.on_search_field_toggled)
    self.cbSearchArtist.connect('toggled', self.on_search_field_toggled)
    self.cbSearchAlbum.connect('toggled', self.on_search_field_toggled)
    self.cbSearchTitle.connect('toggled', self.on_search_field_toggled)
    self.cbSearchTrack.connect('toggled', self.on_search_field_toggled)
    self.cbSearchYear.connect('toggled', self.on_search_field_toggled)
    self.cbSearchGenre.connect('toggled', self.on_search_field_toggled)
    self.cbSearchComment.connect('toggled', self.on_search_field_toggled)

    # Hook up the search bar
    self.entSearch.connect('focus-in-event', self.on_search_focus_in_event)
    self.entSearch.connect('activate', self.on_search)
    self.entSearch.connect('changed', self.on_search_changed)

    # Hook up the buttons
    self.btnClearSearch.connect('clicked', self.on_clear_search)
    self.btnPlayResults.connect('clicked', self.on_play_results)
    self.btnEnqueueResults.connect('clicked', self.on_enqueue_results)
    self.btnSaveSearch.connect('clicked', self.on_save_search)

    # Set up accelerators
    accel_group = gtk.AccelGroup()
    self.window.add_accel_group(accel_group)
    self.entSearch.add_accelerator('grab-focus', accel_group, ord('f'), gtk.gdk.CONTROL_MASK, 0)
    self.btnClearSearch.add_accelerator('clicked', accel_group, ord('e'), gtk.gdk.CONTROL_MASK, 0)
    self.expSearches.add_accelerator('activate', accel_group, ord('s'), gtk.gdk.CONTROL_MASK, 0)
    self.expArtistsAlbums.add_accelerator('activate', accel_group, ord('b'), gtk.gdk.CONTROL_MASK, 0)
    self.cbSearchPath.add_accelerator('activate', accel_group, ord('1'), gtk.gdk.MOD1_MASK, 0)
    self.cbSearchArtist.add_accelerator('activate', accel_group, ord('2'), gtk.gdk.MOD1_MASK, 0)
    self.cbSearchAlbum.add_accelerator('activate', accel_group, ord('3'), gtk.gdk.MOD1_MASK, 0)
    self.cbSearchTitle.add_accelerator('activate', accel_group, ord('4'), gtk.gdk.MOD1_MASK, 0)
    self.cbSearchTrack.add_accelerator('activate', accel_group, ord('5'), gtk.gdk.MOD1_MASK, 0)
    self.cbSearchYear.add_accelerator('activate', accel_group, ord('6'), gtk.gdk.MOD1_MASK, 0)
    self.cbSearchGenre.add_accelerator('activate', accel_group, ord('7'), gtk.gdk.MOD1_MASK, 0)
    self.cbSearchComment.add_accelerator('activate', accel_group, ord('8'), gtk.gdk.MOD1_MASK, 0)

    # Connect destroy signal and show the window
    self.window.connect('destroy', gtk.main_quit)
    self.window.resize(640, 380)
    self.window.show()

    # Finished initializing
    self.inhibit_search = 0

    # Set focus to the search bar
    self.entSearch.grab_focus()

    # Start updating the library
    if self.config.getboolean('options', 'update_on_startup'):
      self.update_db()

  def build_menus(self):
    # Create the File menu
    self.filemenu = gtk.Menu()
    filemenu_item = gtk.MenuItem("_File")
    filemenu_item.set_submenu(self.filemenu)
    self.menubar.append(filemenu_item)

    # File -> Update library
    self.filemenu_update = gtk.ImageMenuItem('_Update library')
    self.filemenu_update.set_image(gtk.image_new_from_stock(gtk.STOCK_REFRESH, gtk.ICON_SIZE_MENU))
    self.filemenu_update.connect('activate', self.on_file_update)
    self.filemenu.append(self.filemenu_update)

    # Separator
    self.filemenu.append(gtk.SeparatorMenuItem())

    # File -> Exit
    self.filemenu_exit = gtk.ImageMenuItem(gtk.STOCK_QUIT)
    self.filemenu_exit.connect('activate', gtk.main_quit)
    self.filemenu.append(self.filemenu_exit)

    # Create the Settings menu
    self.settingsmenu = gtk.Menu()
    settingsmenu_item = gtk.MenuItem('_Settings')
    settingsmenu_item.set_submenu(self.settingsmenu)
    self.menubar.append(settingsmenu_item)

    # Settings -> Update on startup
    self.settingsmenu_update_on_startup = gtk.CheckMenuItem('_Update library on startup')
    self.settingsmenu_update_on_startup.set_active(self.config.getboolean('options', 'update_on_startup'))
    self.settingsmenu_update_on_startup.connect('toggled', self.on_settings_update_on_startup_toggled)
    self.settingsmenu.append(self.settingsmenu_update_on_startup)

    # Settings -> Directories
    self.settingsmenu_directories = gtk.ImageMenuItem('_Directories')
    self.settingsmenu_directories.set_image(gtk.image_new_from_stock(gtk.STOCK_DIRECTORY, gtk.ICON_SIZE_MENU))
    self.settingsmenu_directories.connect('activate', self.on_settings_directories)
    self.settingsmenu.append(self.settingsmenu_directories)

    # Settings -> Audio player
    self.drivermenu = gtk.Menu()
    drivermenu_item = gtk.MenuItem('_Audio player')
    drivermenu_item.set_submenu(self.drivermenu)
    self.settingsmenu.append(drivermenu_item)

    # Settings -> Driver -> <...>
    group = None
    for driver in DRIVERS:
      item = gtk.RadioMenuItem(group, driver.name)
      if group is None:
        group = item
      if self.ap_driver.__class__ == driver:
        item.set_active(True)
      item.connect('toggled', self.on_settings_driver_toggled, driver.name)
      self.drivermenu.append(item)

    # Create the Help menu
    self.helpmenu = gtk.Menu()
    helpmenu_item = gtk.MenuItem('_Help')
    helpmenu_item.set_submenu(self.helpmenu)
    self.menubar.append(helpmenu_item)

    # Help -> About
    self.helpmenu_about = gtk.ImageMenuItem(gtk.STOCK_ABOUT)
    self.helpmenu_about.connect('activate', self.on_about)
    self.helpmenu.append(self.helpmenu_about)

    # Show everything
    self.menubar.show_all()

  # Set which backend driver to use
  def set_driver(self, drivername):
    driver = DummyDriver
    for d in DRIVERS:
      if d.name == drivername:
        driver = d
        break
    try:
      self.ap_driver = driver()
    except Exception, e:
      msg = 'An error has occured while activating the selected driver.\n\nThe error is: %s\n\nFalling back to the dummy driver.' % str(e.message)
      dialog = gtk.MessageDialog(self.window, 
        flags = gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
        type = gtk.MESSAGE_ERROR, 
        buttons = (gtk.BUTTONS_OK),
        message_format = msg
      )
      dialog.run()
      dialog.destroy()
      self.ap_driver = DummyDriver()

  def set_config(self, section, option, value):
    if type(value) != str:
      value = `value`
    if not self.config.has_section(section):
      self.config.add_section(option)
    self.config.set(section, option, value)
    if not os.path.exists(os.path.expanduser('~/.methlab')):
      os.path.makedirs(os.path.expanduser('~/.methlab'))
    self.config.write(open(os.path.expanduser('~/.methlab/config'), 'w'))

  # Get a list of fields that are enabled
  def get_active_search_fields(self):
    fields = []
    if self.cbSearchPath.get_active():
      fields.append('path')
    if self.cbSearchArtist.get_active():
      fields.append('artist')
    if self.cbSearchAlbum.get_active():
      fields.append('album')
    if self.cbSearchTitle.get_active():
      fields.append('title')
    if self.cbSearchTrack.get_active():
      fields.append('track')
    if self.cbSearchYear.get_active():
      fields.append('year')
    if self.cbSearchGenre.get_active():
      fields.append('genre')
    if self.cbSearchComment.get_active():
      fields.append('comment')
    return fields

  # Set active fields (fields is a list or tuple)
  def set_active_search_fields(self, fields = ('artist', 'album', 'title')):
    self.inhibit_search += 1
    self.cbSearchPath.set_active('path' in fields)
    self.cbSearchArtist.set_active('artist' in fields)
    self.cbSearchAlbum.set_active('album' in fields)
    self.cbSearchTitle.set_active('title' in fields)
    self.cbSearchTrack.set_active('track' in fields)
    self.cbSearchYear.set_active('year' in fields)
    self.cbSearchGenre.set_active('genre' in fields)
    self.cbSearchComment.set_active('comment' in fields)
    self.inhibit_search -= 1
    self.search()

  def update_search_fields(self):
    fields = self.get_active_search_fields()
    self.db.set_search_fields(*fields)

  def update_artists_albums_model(self):
    artists = [row["artist"] for row in self.db.get_artists()]
    for artist in artists:
      if not self.artist_iters.has_key(artist):
        iter = self.artists_albums_model.append(None)
        self.artists_albums_model.set(iter, 0, artist)
        self.artist_iters[artist] = iter
    for artist, iter in self.artist_iters.items():
      if not artist in artists:
        self.artists_albums_model.remove(iter)
        del self.artist_iters[artist]
        for (artist_, album_) in self.artist_albums.keys():
          if artist_ == artist:
            self.artist_albums.remove((artist_, album_))

    artists_albums = [(row['artist'], row['album']) for row in self.db.get_artists_albums()]
    for artist, album in artists_albums:
      if not self.album_iters.has_key((artist, album)):
        artist_iter = self.artist_iters[artist]
        iter = self.artists_albums_model.append(artist_iter)
        self.artists_albums_model.set(iter, 0, album)
        self.album_iters[(artist, album)] = iter
    for (artist, album), iter in self.album_iters.items():
      if not (artist, album) in artists_albums:
        self.artists_albums_model.remove(iter)
        del self.album_iters[(artist, album)]

  def update_searches_model(self):
    search_names = []
    searches = self.db.get_searches()
    for row in searches:
      name = row['name']
      query = row['query']
      fields = row['fields']
      search_names.append(name)
      iter = self.search_iters.get(name, None)
      if iter is None:
        iter = self.searches_model.append(None)
        self.searches_model.set(iter, 0, name, 1, query, 2, fields)
        self.search_iters[name] = iter
      else:
        self.searches_model.set(iter, 1, query, 2, fields)
    for search_name, iter in self.search_iters.items():
      if not search_name in search_names:
        self.searches_model.remove(iter)
        del self.search_iters[search_name]

  def cancel_search_timeout(self):
    if self.search_timeout_tag is not None:
      gobject.source_remove(self.search_timeout_tag)
      self.search_timeout_tag = None

  def search(self, add_to_history = False):
    self.cancel_search_timeout()
    if self.inhibit_search:
      return

    self.unflash_search_entry()

    self.results_model.clear()
    query = self.entSearch.get_text()
    if not query:
      return
    try:
      if query[0] == '@':
        results = self.db.query_tracks(query[1:])
      else:
        args = query.split()
        results = self.db.search(*args)
    except sqlite3.OperationalError:
      self.flash_search_entry()
      return
    except QueryTranslatorException:
      self.flash_search_entry()
      return

    if add_to_history:
      self.add_to_history(query)

    for result in results:
      iter = self.results_model.append()
      self.results_model.set(iter,
        0, result['path'],
        1, result['artist'],
        2, result['album'],
        3, result['track'],
        4, result['title'],
        5, result['year'],
        6, result['genre'],
        7, result['comment']
      )

  def cancel_flash_search_entry(self):
    if self.flash_timeout_tag is not None:
      gobject.source_remove(self.flash_timeout_tag)
      self.flash_timeout_tag = None

  def flash_search_entry(self):
    self.cancel_flash_search_entry()
    self.entSearch.modify_base(gtk.STATE_NORMAL, gtk.gdk.color_parse('#ff0000'))
    self.flash_timeout_tag = gobject.timeout_add(300, self.unflash_search_entry)

  def unflash_search_entry(self):
    self.cancel_flash_search_entry()
    self.entSearch.modify_base(gtk.STATE_NORMAL, None)
    return False

  def get_selected_result_paths(self):
    files = []
    sel = self.tvResults.get_selection()
    model, paths = sel.get_selected_rows()
    if not paths:
      iter = model.get_iter_first()
      while iter:
        files.append(model.get_value(iter, 0))
        iter = model.iter_next(iter)
    else:
      for path in paths:
        iter = model.get_iter(path)
        if iter:
          files.append(model.get_value(iter, 0))
    return files

  def update_db(self):
    def yield_func():
      gtk.main_iteration(False)

    dialog = gtk.Dialog \
    (
      "Please wait...",
      self.window,
      gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT
    )
    dialog.set_has_separator(False)
    dialog.vbox.pack_start(gtk.Label('Please wait while MethLab updates the library...'))
    dialog.connect('delete_event', lambda w, e: True)
    dialog.show_all()
    self.db.update(yield_func)
    dialog.destroy()

  def add_to_history(self, query):
    iter = self.history_model.get_iter_first()
    while iter:
      if self.history_model.get_value(iter, 0) == query:
        self.history_model.move_after(iter, None)
        break
      iter = self.history_model.iter_next(iter)
    else:
      iter = self.history_model.prepend()
      self.history_model.set_value(iter, 0, query)

    node = self.history_model.iter_nth_child(None, 49)
    next = None
    if node:
      next = self.history_model.iter_next(node)
    while next:
      self.history_model.remove(next)
      next = self.history_model.iter_next(node)

  def on_expander_expanded(self, expander, param_spec):
    if expander.get_expanded():
      for e in self.sidebar_expanders:
        if e != expander:
          if e.get_expanded():
            e.set_expanded(False)
        self.vboxExpanders.set_child_packing(e, e == expander, True, 0, gtk.PACK_START)
        if expander == self.expArtistsAlbums:
          self.tvArtistsAlbums.realize()
          self.tvArtistsAlbums.grab_focus()
        elif expander == self.expSearches:
          self.tvSearches.realize()
          self.tvSearches.grab_focus()
    else:
      for e in self.sidebar_expanders:
        if e.get_expanded():
          break
      else:
        e.set_expanded(True)

  def on_artists_albums_selection_changed(self, selection):
    model, paths = selection.get_selected_rows()
    if not paths:
      return

    queries = []
    for path in paths:
      iter = model.get_iter(path)
      parent = model.iter_parent(iter)
      if parent is None:
        artist = query_escape(model.get_value(iter, 0))
        queries.append('(artist = %s)' % artist)
      else:
        artist = query_escape(model.get_value(parent, 0))
        album = query_escape(model.get_value(iter, 0))
        queries.append('(artist = %s AND album = %s)' % (artist, album))

    self.entSearch.set_text('@' + ' OR '.join(queries))
    self.search()

  def on_search_focus_in_event(self, widget, event):
    self.expSearchOptions.set_expanded(True)

  def on_search(self, entry):
    self.search(True)

  def on_search_changed(self, editable):
    self.cancel_search_timeout()
    if self.inhibit_search:
      return

    text = editable.get_text()

    if not text:
      self.search()
      return

    if text[0] == '@' or len(text) <= 3:
      return

    self.search_timeout_tag = gobject.timeout_add(500, self.on_search_timeout)

  def on_search_timeout(self):
    self.search_timeout_tag = None
    self.search(True)
    return False

  def on_play_results(self, button):
    files = self.get_selected_result_paths()
    if files:
      self.ap_driver.play(files)

  def on_enqueue_results(self, button):
    files = self.get_selected_result_paths()
    if files:
      self.ap_driver.enqueue(files)

  def on_search_field_toggled(self, button):
    self.update_search_fields()
    text = self.entSearch.get_text()
    if text and text[0] != '@':
      self.search()

  def on_save_search(self, button):
    query = self.entSearch.get_text()
    if not query:
      return
    fields = self.get_active_search_fields()

    sel = self.tvSearches.get_selection()
    model, iter = sel.get_selected()
    if iter:
      name = model.get_value(iter, 0)
    else:
      if query[:1] == '@':
        name = query
      else:
        name = "'" + query + "' in " + ', '.join(fields)

    dialog = gtk.Dialog \
    (
      "Save search",
      self.window,
      gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
      (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
       gtk.STOCK_OK,     gtk.RESPONSE_ACCEPT)
    )
    dialog.vbox.pack_start(gtk.Label("Name of the search"))
    entry = gtk.Entry()
    entry.set_text(name)
    entry.connect('activate', lambda w: dialog.response(gtk.RESPONSE_ACCEPT))
    dialog.vbox.pack_start(entry)
    dialog.show_all()
    response = dialog.run()
    if response == gtk.RESPONSE_ACCEPT:
      name = entry.get_text()
      if name:
        self.db.add_search(name, query, ' '.join(fields))
        self.update_searches_model()
        self.tvSearches.get_selection().select_iter(self.search_iters[name])
        self.expSearches.set_expanded(True)
    dialog.destroy()

  def on_searches_selection_changed(self, selection):
    model, iter = selection.get_selected()
    if iter is None:
      return
    self.inhibit_search += 1
    query, fields = model.get(iter, 1, 2)
    fields = fields.split()
    self.set_active_search_fields(fields)
    self.entSearch.set_text(query)
    self.inhibit_search -= 1
    self.search()

  def on_searches_button_press_event(self, treeview, event):
    if event.button == 3:
      data = treeview.get_path_at_pos(int(event.x), int(event.y))
      if data is not None:
        path, col, r_x, r_y = data
        iter = treeview.get_model().get_iter(path)
        name = treeview.get_model().get_value(iter, 0)
        treeview.get_selection().select_iter(iter)
        menu = gtk.Menu()
        item = gtk.MenuItem('Remove')
        item.connect('activate', self.on_searches_popup_remove, name)
        menu.append(item)
        menu.show_all()
        menu.popup(None, None, None, event.button, event.time)
      else:
        treeview.get_selection().unselect_all()
      return True

  def on_searches_popup_remove(self, menuitem, name):
    self.db.delete_search(name)
    self.tvSearches.get_model().remove(self.search_iters[name])
    del self.search_iters[name]

  def on_clear_search(self, button):
    self.entSearch.set_text('')
    self.entSearch.grab_focus()

  def on_file_update(self, menuitem):
    self.update_db()

  def on_settings_directories(self, menuitem):
    def on_add_directory(button, model):
      dialog = gtk.FileChooserDialog \
        (
          'Add directory',
          self.window,
          gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
          (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
           gtk.STOCK_OK,     gtk.RESPONSE_ACCEPT)
        )
      if dialog.run() == gtk.RESPONSE_ACCEPT:
        dir = dialog.get_current_folder()
        iter = model.append(None)
        model.set_value(iter, 0, dir)
      dialog.destroy()

    def on_remove_directory(button, treeview):
      model, iter = treeview.get_selection().get_selected()
      if iter is not None:
        model.remove(iter)

    changed = False

    model = gtk.ListStore(str)
    roots = [os.path.abspath(root[0]) for root in self.db.get_roots()]
    for root in roots:
      iter = model.append(None)
      model.set_value(iter, 0, root)

    gladefile = os.path.join(os.path.split(__file__)[0], 'dirdialog.glade')
    wtree = gtk.glade.XML(gladefile)
    dialog = wtree.get_widget('dialog')
    treeview = wtree.get_widget('tvDirs')
    treeview.append_column(gtk.TreeViewColumn('Directory', gtk.CellRendererText(), text = 0))
    treeview.set_model(model)
    wtree.get_widget('btnAdd').connect('clicked', on_add_directory, model)
    wtree.get_widget('btnRemove').connect('clicked', on_remove_directory, treeview)
    wtree.get_widget('btnOk').connect('clicked', lambda w: dialog.response(gtk.RESPONSE_ACCEPT))
    wtree.get_widget('btnCancel').connect('clicked', lambda w: dialog.response(gtk.RESPONSE_REJECT))
    dialog.resize(300, 300)
    if dialog.run() == gtk.RESPONSE_ACCEPT:
      dirs = [row[0] for row in model]
      for root in roots:
        if not root in dirs:
          print 'Purging', root
          self.db.delete_root(root + '/')
          changed = True
      for dir in dirs:
        if not dir in roots:
          print 'Adding', dir
          self.db.add_root(dir)
          changed = True

    dialog.destroy()

    if changed:
      self.update_db()

  def on_settings_driver_toggled(self, menuitem, driver):
    if menuitem.get_active():
      self.set_driver(driver)
      self.set_config('options', 'driver', driver)

  def on_settings_update_on_startup_toggled(self, menuitem):
    self.set_config('options', 'update_on_startup', menuitem.get_active())

  def on_about(self, menuitem):
    dialog = gtk.AboutDialog()
    dialog.set_name('MethLab')
    dialog.set_version('0.0.0')
    dialog.set_copyright('MethLab is (C) 2007 Ingmar Steen.\nThe bundled xmmsalike library is (C) 2006 Ben Wolfson and Risto A. Paju')
    dialog.set_license(LICENSE)
    dialog.set_website('http://thegraveyard.org/')
    dialog.set_authors(['Ingmar Steen <iksteen@gmail.com> (Main developer)'])
    dialog.run()
    dialog.destroy()
