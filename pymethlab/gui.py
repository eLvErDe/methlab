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
import pango
from ConfigParser import ConfigParser
from db import DB
from querytranslator import QueryTranslatorException
from drivers import DRIVERS, DummyDriver
from db_sources import DB_SOURCES, FilesystemSource
from db import sqlite
from gettext import gettext as _
try:
  from dbus_service import MethLabDBusService
except ImportError:
  MethLabDBusService = None

# Case insensitive string compare
def case_insensitive_cmp(model, a, b):
  return cmp(model.get_value(a, 0).upper(), model.get_value(b, 0).upper())

# Quote and escape a string to be used in a query
def query_escape(s):
  return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

# The main window
class MethLabWindow:
  CONFIG_PATH = os.path.join('~', '.methlab', 'config')
  # Generic options
  DEFAULT_DB_SOURCE = 'fs'
  DEFAULT_DRIVER = DummyDriver.name
  DEFAULT_UPDATE_ON_STARTUP = True
  DEFAULT_SEARCH_ON_ARTIST_AND_ALBUM = True
  DEFAULT_SEARCH_FIELDS = 'artist album title'
  DEFAULT_SORT_ORDER = 'album track title path artist year genre comment'
  # User interface options
  DEFAULT_COLUMN_ORDER = 'path artist album track title year genre comment'
  DEFAULT_VISIBLE_COLUMNS = 'artist album track title'
  DEFAULT_ARTISTS_COLLAPSIBLE = False
  DEFAULT_SHOW_STATUS_ICON = True
  DEFAULT_START_HIDDEN = False
  DEFAULT_CLOSE_TO_TRAY = True
  DEFAULT_DOUBLE_CLICK_ACTION = 'play'
  DEFAULT_GEOMETRY = (640, 380, None, None)

  DEFAULT_CONFIG = {
    'options': {
      'db_source': DEFAULT_DB_SOURCE,
      'driver': DEFAULT_DRIVER,
      'update_on_startup': `DEFAULT_UPDATE_ON_STARTUP`,
      'search_on_artist_and_album': `DEFAULT_SEARCH_ON_ARTIST_AND_ALBUM`,
      'search_fields': DEFAULT_SEARCH_FIELDS,
      'sort_order': DEFAULT_SORT_ORDER,
    },
    'interface': {
      'column_order': DEFAULT_COLUMN_ORDER,
      'visible_columns': DEFAULT_VISIBLE_COLUMNS,
      'artists_collapsible': `DEFAULT_ARTISTS_COLLAPSIBLE`,
      'show_status_icon': `DEFAULT_SHOW_STATUS_ICON`,
      'start_hidden': `DEFAULT_START_HIDDEN`,
      'close_to_tray': `DEFAULT_CLOSE_TO_TRAY`,
      'double_click_action': DEFAULT_DOUBLE_CLICK_ACTION,
    }
  }

  def __init__(self, start_hidden = False):
    # Set up the window icon list
    self.icons = {}
    basedir = os.path.split(__file__)[0]
    imagedir = os.path.join(basedir, 'images')
    for width in 16, 24, 32, 48, 64:
      icon_name = 'logo_%ix%i.png' % (width, width)
      icon = gtk.gdk.pixbuf_new_from_file(os.path.join(imagedir, icon_name))
      self.icons[width] = icon
    gtk.window_set_default_icon_list(*self.icons.values())

    # Load the gui from the XML file
    self.gladefile = os.path.join(os.path.split(__file__)[0], 'methlab.glade')
    wtree = gtk.glade.XML(self.gladefile)

    # Map the widgets from the wtree to the class
    for w in wtree.get_widget_prefix(''):
      setattr(self, w.name, w)

    # Set the default configuration options
    self.config = ConfigParser()
    for section, options in self.DEFAULT_CONFIG.items():
      self.config.add_section(section)
      for key, value in options.items():
        self.config.set(section, key, value)
    # Merge configuration file with default options
    self.config.read(os.path.expanduser(self.CONFIG_PATH))

    # Pick a database source
    need_purge = False
    db_source = self.config.get('options', 'db_source')
    for db_source_class in DB_SOURCES:
      if db_source_class.name == db_source:
        break
    else:
      self.error_dialog(_('The database source you have previously selected is not or no longer available.\n\nFalling back to the filesystem database source.'))
      db_source_class = FilesystemSource
      self.set_config('options', 'db_source', 'fs')
      need_purge = True

    # Create our database back-end
    self.db = DB(scanner_class = db_source_class)

    # If this value is not 0, searches will not occur
    self.inhibit_search = 1

    # Some timeout tags we may wish to cancel
    self.search_timeout_tag = None
    self.flash_timeout_tag = None

    # A tuple describing all the result columns (name, field, model_col)
    self.result_columns = \
    {
      'path': (0, _('Path'), _('Path')),
      'artist': (1, _('Artist'), _('Artist')),
      'album': (2, _('Album'), _('Album')),
      'track': (3, _('#'), _('Track number')),
      'title': (4, _('Title'), _('Track title')),
      'year': (5, _('Year'), _('Year')),
      'genre': (6, _('Genre'), _('Genre')),
      'comment': (7, _('Comment'), _('Comment'))
    }

    # Create the audio-player back-end
    self.set_driver(self.config.get('options', 'driver'))

    # Build the menus
    self.build_menus()

    # Create a cell renderer we re-use
    cell_renderer = gtk.CellRendererText()

    # Get the sort order and do some sanity checks
    sort_order = self.config.get('options', 'sort_order').split(' ')
    a = sort_order[:]
    a.sort()
    b = self.result_columns.keys()
    b.sort()
    if a != b:
      sort_order = self.DEFAULT_SORT_ORDER.split(' ')

    # Get the active search fields and do some sanity checks
    search_fields = self.config.get('options', 'search_fields').split(' ')
    search_fields = [field for field in search_fields if field in sort_order]

    # Set up the search options model
    self.search_options_model = gtk.ListStore(str, bool, str)
    for field in sort_order:
      iter = self.search_options_model.append()
      self.search_options_model.set_value(iter, 0, field)
      self.search_options_model.set_value(iter, 1, field in search_fields)
      self.search_options_model.set_value(iter, 2, self.result_columns[field][2])
    # The reason we connect 'row-deleted' is because 'rows-reordered' does
    # not get emitted when a user re-orders the columns. The order of signals
    # that get emitted is: row-inserted, row-changed, row-deleted.
    self.search_options_model.connect('row-deleted', self.on_search_options_row_deleted)

    # Set up the search options tree view
    self.tvSortOrder.get_selection().set_mode(gtk.SELECTION_NONE)
    cell_renderer_toggle = gtk.CellRendererToggle()
    cell_renderer_toggle.connect('toggled', self.on_search_field_toggled)
    self.tvSortOrder.append_column(gtk.TreeViewColumn('', cell_renderer_toggle, active = 1))
    self.tvSortOrder.append_column(gtk.TreeViewColumn('', cell_renderer, text = 2))
    self.tvSortOrder.set_model(self.search_options_model)
    self.update_sort_order(False)
    self.update_search_fields(False)
    # Haxory and trixory to tweak the base color of the tree view. However,
    # this makes the checkbox look like they're disabled.
#    self.tvSortOrder.realize()
#    normal_bg = self.tvSortOrder.get_style().bg[gtk.STATE_NORMAL]
#    self.tvSortOrder.modify_base(gtk.STATE_NORMAL, normal_bg)

    # Set up the artists / albums model
    self.artists_albums_model = gtk.TreeStore(str)
    self.artists_albums_model.set_sort_func(0, case_insensitive_cmp)
    self.artists_albums_model.set_sort_column_id(0, gtk.SORT_ASCENDING)
    self.artist_iters = {}
    self.album_iters = {}
    self.update_artists_albums_model()

    # Set up the artists / albums tree view
    artist_album_renderer = gtk.CellRendererText()
    col = gtk.TreeViewColumn('', artist_album_renderer, text = 0)
    col.set_cell_data_func(artist_album_renderer, self.get_artists_albums_cell_data)
    self.tvArtistsAlbums.append_column(col)
    self.tvArtistsAlbums.set_model(self.artists_albums_model)
    if self.supports_not_collapsible():
      self.update_artists_collapsible()
    self.tvArtistsAlbums.get_selection().connect('changed', self.on_artists_albums_selection_changed)
    self.tvArtistsAlbums.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
    self.tvArtistsAlbums.connect('button-press-event', self.on_results_button_press_event)

    # Set up the saved searches model
    self.searches_model = gtk.ListStore(str, str, str)
    self.searches_model.set_sort_func(0, case_insensitive_cmp)
    self.searches_model.set_sort_column_id(0, gtk.SORT_ASCENDING)
    self.search_iters = {}
    self.update_searches_model()

    # Set up the saved searches tree view
    self.tvSearches.append_column(gtk.TreeViewColumn('', cell_renderer, text = 0))
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

    # Set up the no_results model
    self.no_results_model = gtk.ListStore(str, str, str, int, str, int, str, str)
    self.no_results_model.append()

    # Get the column order and do a sanity check
    column_order = self.config.get('interface', 'column_order').split(' ')
    a = column_order[:]
    a.sort()
    b = self.result_columns.keys()
    b.sort()
    if a != b:
      column_order = self.DEFAULT_COLUMN_ORDER.split(' ')

    # What fields does the user wish to see and do a sanity check
    visible_columns = self.config.get('interface', 'visible_columns').split(' ')
    visible_columns = [column for column in visible_columns if column in column_order]
    if not visible_columns:
      visible_columns = self.DEFAULT_VISIBLE_COLUMNS

    # Set up the results tree view
    results_renderer = gtk.CellRendererText()
    for column_field in column_order:
      column_id, column_name, column_long = self.result_columns[column_field]
      column = gtk.TreeViewColumn(None, results_renderer, text = column_id)
      column.field = column_field
      column.column_id = column_id
      column.column_long = column_long
      column.set_sizing(gtk.TREE_VIEW_COLUMN_AUTOSIZE)
      column.set_reorderable(True)
      column.set_visible(column_field in visible_columns)
      column.set_cell_data_func(results_renderer, self.get_results_cell_data)
      self.tvResults.append_column(column)
      # Haxory and trixory to be able to catch right click on the header
      column.set_clickable(True)
      column.set_widget(gtk.Label(column_name))
      column.get_widget().show()
      parent = column.get_widget().get_ancestor(gtk.Button)
      if parent:
        parent.connect('button-press-event', self.on_results_header_button_press_event)
    self.tvResults.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
    self.tvResults.set_model(self.results_model)
    self.tvResults.connect('columns-changed', self.on_results_columns_changed)
    self.tvResults.connect('button-press-event', self.on_results_button_press_event)

    # Fix and hook up the expanders
    self.btnSearchOptions.connect('clicked', self.on_section_button_clicked)
    self.btnSearches.connect('clicked', self.on_section_button_clicked)
    self.btnArtistsAlbums.connect('clicked', self.on_section_button_clicked)
    self.btnArtistsAlbums.connect('button-press-event', self.on_artists_albums_button_press_event)

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
    for i in range(0, 8):
      accel_group.connect_group(ord(str(i + 1)), gtk.gdk.MOD1_MASK, 0, self.on_toggle_search_field)

    # Create the status icon
    if self.supports_status_icon():
      self.build_status_icon_menu()
      self.status_icon = gtk.status_icon_new_from_pixbuf(self.icons[24])
      self.status_icon.set_tooltip('MethLab')
      self.status_icon.connect('activate', self.on_status_icon_activate)
      self.status_icon.connect('popup-menu', self.on_status_icon_popup_menu)
      self.status_icon.set_visible(self.config.getboolean('interface', 'show_status_icon'))
    else:
      self.status_icon = None

    # Haxory and trixory to prevent widgets from needlessly rearranging
    self.swSearches.realize()
    self.tvSearches.realize()
    self.swArtistsAlbums.realize()
    self.tvArtistsAlbums.realize()
    self.hpaned1.set_position(self.hpaned1.get_position())

    # Connect destroy signal and show the window
    self.window.connect('delete_event', self.on_window_delete)
    self.window.connect('destroy', gtk.main_quit)
    if not (self.status_icon and self.config.getboolean('interface', 'show_status_icon') and (start_hidden or self.config.getboolean('interface', 'start_hidden'))):
      self.show_window()

    # Create the DBUS service
    if MethLabDBusService:
      self.dbus_service = MethLabDBusService(self)

    # Finished initializing
    self.inhibit_search = 0

    # Set focus to the search bar
    self.entSearch.grab_focus()

    # Start updating the library
    if need_purge or self.config.getboolean('options', 'update_on_startup'):
      if need_purge:
        self.db.purge()
      self.update_db()

  def supports_status_icon(self):
    return hasattr(gtk, 'status_icon_new_from_pixbuf')

  def supports_not_collapsible(self):
    try:
      self.tvArtistsAlbums.get_property('show-expanders')
      self.tvArtistsAlbums.get_property('level-indentation')
    except TypeError:
      return False
    return True

  def build_menus(self):
    # Create the File menu
    self.filemenu = gtk.Menu()
    filemenu_item = gtk.MenuItem(_('_File'))
    filemenu_item.set_submenu(self.filemenu)
    self.menubar.append(filemenu_item)

    # File -> Update library now
    self.filemenu_update = gtk.ImageMenuItem(_('_Update library now'))
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
    settingsmenu_item = gtk.MenuItem(_('_Settings'))
    settingsmenu_item.set_submenu(self.settingsmenu)
    self.menubar.append(settingsmenu_item)

    # Settings -> Double-click in list
    menu = gtk.Menu()
    item = gtk.MenuItem(_('Double-_click in list'))
    item.set_submenu(menu)
    self.settingsmenu.append(item)

    # Settings -> Double-click in list -> Plays results
    item = gtk.RadioMenuItem(None, _('_Plays results'))
    item.set_active(self.config.get('interface', 'double_click_action') == 'play')
    item.connect('activate', self.on_settings_set_double_click_action, 'play')
    menu.append(item)

    # Settings -> Double-click in list -> Enqueues results
    item = gtk.RadioMenuItem(item, _('_Enqueues results'))
    item.set_active(self.config.get('interface', 'double_click_action') != 'play')
    item.connect('activate', self.on_settings_set_double_click_action, 'enqueue')
    menu.append(item)

    # Separator
    self.settingsmenu.append(gtk.SeparatorMenuItem())

    if self.supports_status_icon():
      # Settings -> Show status icon
      item1 = gtk.CheckMenuItem(_('Show status _icon'))
      item1.set_active(self.config.getboolean('interface', 'show_status_icon'))
      self.settingsmenu.append(item1)

      # Settings -> Close to tray
      item2 = gtk.CheckMenuItem(_('Close to _tray'))
      item2.set_sensitive(self.config.getboolean('interface', 'show_status_icon'))
      item2.set_active(self.config.getboolean('interface', 'close_to_tray'))
      item2.connect('toggled', self.on_settings_close_to_tray_toggled)
      self.settingsmenu.append(item2)

      # Settings -> Start hidden
      item3 = gtk.CheckMenuItem(_('Start _hidden'))
      item3.set_sensitive(self.config.getboolean('interface', 'show_status_icon'))
      item3.set_active(self.config.getboolean('interface', 'start_hidden'))
      item3.connect('toggled', self.on_settings_start_hidden_toggled)
      self.settingsmenu.append(item3)

      # Connect 'Show status icon's toggled signal since it adds item2
      # as a user arg.
      item1.connect('toggled', self.on_settings_show_status_icon_toggled, item2, item3)

      # Seperator
      self.settingsmenu.append(gtk.SeparatorMenuItem())

    # Settings -> Database source
    self.dbsourcemenu = gtk.Menu()
    dbsourcemenu_item = gtk.MenuItem(_('Database _source'))
    dbsourcemenu_item.set_submenu(self.dbsourcemenu)
    self.settingsmenu.append(dbsourcemenu_item)

    # Settings -> Database source -> <...>
    group = None
    for db_source_class in DB_SOURCES:
      item = gtk.RadioMenuItem(group, db_source_class.name_tr)
      if group is None:
        group = item
      item.set_active(db_source_class == self.db.get_scanner_class())
      item.connect('toggled', self.on_settings_db_source_toggled, db_source_class)
      self.dbsourcemenu.append(item)

    # Settings -> Directories
    self.settingsmenu_directories = gtk.ImageMenuItem(_('_Directories'))
    self.settingsmenu_directories.set_image(gtk.image_new_from_stock(gtk.STOCK_DIRECTORY, gtk.ICON_SIZE_MENU))
    self.settingsmenu_directories.connect('activate', self.on_settings_directories)
    self.settingsmenu.append(self.settingsmenu_directories)

    # Settings -> Update on startup
    self.settingsmenu_update_on_startup = gtk.CheckMenuItem(_('_Update library on startup'))
    self.settingsmenu_update_on_startup.set_active(self.config.getboolean('options', 'update_on_startup'))
    self.settingsmenu_update_on_startup.connect('toggled', self.on_settings_update_on_startup_toggled)
    self.settingsmenu.append(self.settingsmenu_update_on_startup)

    # Separator
    self.settingsmenu.append(gtk.SeparatorMenuItem())

    # Settings -> Audio player
    self.drivermenu = gtk.Menu()
    drivermenu_item = gtk.MenuItem(_('_Audio player'))
    drivermenu_item.set_submenu(self.drivermenu)
    self.settingsmenu.append(drivermenu_item)

    # Settings -> Audio player -> <...>
    group = None
    for driver in DRIVERS:
      item = gtk.RadioMenuItem(group, driver.name_tr)
      if group is None:
        group = item
      if self.ap_driver.__class__ == driver:
        item.set_active(True)
      item.connect('toggled', self.on_settings_driver_toggled, driver.name)
      self.drivermenu.append(item)

    # Create the Help menu
    self.helpmenu = gtk.Menu()
    helpmenu_item = gtk.MenuItem(_('_Help'))
    helpmenu_item.set_submenu(self.helpmenu)
    self.menubar.append(helpmenu_item)

    # Help -> About
    self.helpmenu_about = gtk.ImageMenuItem(gtk.STOCK_ABOUT)
    self.helpmenu_about.connect('activate', self.on_about)
    self.helpmenu.append(self.helpmenu_about)

    # Show everything
    self.menubar.show_all()

  def build_status_icon_menu(self):
    # Build the status icon popup menu
    self.status_icon_menu = gtk.Menu()

    # Show MethLab
    item = gtk.MenuItem(_('_Show MethLab'))
    item.connect('activate', self.on_status_icon_menu_show)
    self.status_icon_menu.append(item)

    # Hide MethLab
    item = gtk.MenuItem(_('_Hide MethLab'))
    item.connect('activate', self.on_status_icon_menu_hide)
    self.status_icon_menu.append(item)

    # Seperator
    self.status_icon_menu.append(gtk.SeparatorMenuItem())

    # Quit
    item = gtk.ImageMenuItem(gtk.STOCK_QUIT)
    item.connect('activate', gtk.main_quit)
    self.status_icon_menu.append(item)

    # Show everything
    self.status_icon_menu.show_all()

  # Helper function to show an error dialog
  def error_dialog(self, message):
    dialog = gtk.MessageDialog(self.window, 
      flags = gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
      type = gtk.MESSAGE_ERROR, 
      buttons = (gtk.BUTTONS_OK),
      message_format = message
    )
    dialog.run()
    dialog.destroy()

  # Set which backend driver to use
  def set_driver(self, drivername):
    for d in DRIVERS:
      if d.name == drivername:
        driver = d
        break
    else:
      self.error_dialog(_('The audio player driver you have previously selected is not or no longer available.\n\nFalling back to the dummy driver.'))
      driver = DummyDriver
    try:
      self.ap_driver = driver()
    except Exception, e:
      self.error_dialog(_('An error has occured while activating the selected driver.\n\nThe error is: %s\n\nFalling back to the dummy driver.') % str(e.message))
      self.ap_driver = DummyDriver()

  def set_db_source(self, db_source):
    self.db.purge()
    self.db.set_scanner_class(db_source)
    self.update_db()

  def set_config(self, section, option, value):
    if type(value) != str:
      value = `value`
    if not self.config.has_section(section):
      self.config.add_section(option)
    self.config.set(section, option, value)
    config_path = os.path.expanduser(self.CONFIG_PATH)
    config_dir = os.path.split(config_path)[0]
    if not os.path.exists(config_dir):
      os.makedirs(config_dir)
    self.config.write(open(config_path, 'w'))

  # Call this to get a list of enabled search fields (according to the model)
  def get_active_search_fields(self):
    active_fields = []
    iter = self.search_options_model.get_iter_first()
    while iter:
      field, active = self.search_options_model.get(iter, 0, 1)
      if active:
        active_fields.append(field)
      iter = self.search_options_model.iter_next(iter)
    return active_fields

  # Update DB's search view. If requested, also save the active search fields
  def update_search_fields(self, save = True):
    active_fields = self.get_active_search_fields()
    self.db.set_search_fields(*active_fields)
    if save:
      self.set_config('options', 'search_fields', ' '.join(active_fields))

  # Set the active search fields and save them to the config.
  def set_active_search_fields(self, fields):
    iter = self.search_options_model.get_iter_first()
    while iter:
      field = self.search_options_model.get_value(iter, 0)
      self.search_options_model.set_value(iter, 1, field in fields)
      iter = self.search_options_model.iter_next(iter)
    self.update_search_fields()

  # Call this to get the sort order
  def get_sort_order(self):
    fields = []
    iter = self.search_options_model.get_iter_first()
    while iter:
      fields.append(self.search_options_model.get_value(iter, 0))
      iter = self.search_options_model.iter_next(iter)
    return fields

  # Update DB's sort order. If requested, also save the active search fields
  def update_sort_order(self, save = True):
    field_order = self.get_sort_order()
    self.db.set_sort_order(*field_order)
    if save:
      self.set_config('options', 'sort_order', ' '.join(field_order))

  def get_artists_albums_cell_data(self, column, cell, model, iter):
    value = model.get_value(iter, 0)
    if not value:
      cell.set_property('style', pango.STYLE_ITALIC)
      cell.set_property('text', 'untitled')
    else:
      cell.set_property('style', pango.STYLE_NORMAL)

  def get_results_cell_data(self, column, cell, model, iter):
    if model == self.no_results_model:
      if column is self.tvResults.get_column(0):
        cell.set_property('style', pango.STYLE_ITALIC)
        cell.set_property('text', _('Your search did not return any results.'))
      else:
        cell.set_property('style', pango.STYLE_NORMAL)
        cell.set_property('text', '')
      return

    field = column.field
    column_id = column.column_id
    value = model.get_value(iter, column_id)
    if not value:
      cell.set_property('style', pango.STYLE_ITALIC)
      if field in ('artist', 'album', 'title'):
        cell.set_property('text', 'untitled')
      elif field == 'genre':
        cell.set_property('text', 'unknown')
      elif field in ('track', 'year'):
        cell.set_property('text', '')
    else:
      cell.set_property('style', pango.STYLE_NORMAL)

  def update_artists_collapsible(self):
    collapsible = self.config.getboolean('interface', 'artists_collapsible')
    self.tvArtistsAlbums.set_enable_tree_lines(not collapsible)
    self.tvArtistsAlbums.set_property('show-expanders', collapsible)
    if collapsible:
      self.tvArtistsAlbums.set_property('level-indentation', 0)
    else:
      self.tvArtistsAlbums.set_property('level-indentation', 25)
      self.tvArtistsAlbums.expand_all()

  def update_artists_albums_model(self):
    artists = [row['artist'] for row in self.db.get_artists()]
    for artist in artists:
      if not self.artist_iters.has_key(artist.lower()):
        iter = self.artists_albums_model.append(None)
        self.artists_albums_model.set_value(iter, 0, artist)
        self.artist_iters[artist.lower()] = iter
    artists_lower = [artist.lower() for artist in artists]
    for artist, iter in self.artist_iters.items():
      if not artist in artists_lower:
        self.artists_albums_model.remove(iter)
        del self.artist_iters[artist]
        for (artist_, album_), iter in self.album_iters.items():
          if artist_ == artist:
            del self.album_iters[(artist_, album_)]

    artists_albums = [(row['artist'], row['album']) for row in self.db.get_artists_albums()]
    for artist, album in artists_albums:
      key = (artist.lower(), album.lower())
      if not self.album_iters.has_key(key):
        artist_iter = self.artist_iters[artist.lower()]
        iter = self.artists_albums_model.append(artist_iter)
        self.artists_albums_model.set_value(iter, 0, album)
        self.album_iters[key] = iter
    artists_albums_lower = [(artist.lower(), album.lower()) for artist, album in artists_albums]
    for (artist, album), iter in self.album_iters.items():
      if not (artist, album) in artists_albums_lower:
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
    if self.tvResults.get_model() != self.results_model:
      self.tvResults.set_model(self.results_model)
      self.tvResults.set_sensitive(True)

    query = self.entSearch.get_text()
    if not query:
      return
    try:
      if query[0] == '@':
        results = self.db.query_tracks(query[1:])
      else:
        results = self.db.search_tracks(query)
    except sqlite.OperationalError, e:
      self.flash_search_entry()
      return
    except QueryTranslatorException, e:
      self.flash_search_entry()
      return

    if add_to_history:
      self.add_to_history(query)

    have_results = False
    for result in results:
      have_results = True
      iter = self.results_model.append()
      self.results_model.set(iter,
        0, result[0],
        1, result['artist'],
        2, result['album'],
        3, result['track'],
        4, result['title'],
        5, result['year'],
        6, result['genre'],
        7, result['comment']
      )

    if not have_results:
      self.tvResults.set_model(self.no_results_model)
      self.tvResults.set_sensitive(False)

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
    if self.tvResults.get_model() == self.no_results_model:
      return []

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
      _('Please wait...'),
      self.window,
      gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT
    )
    dialog.set_has_separator(False)
    dialog.vbox.pack_start(gtk.Label(_('Please wait while MethLab updates the library...')))
    dialog.connect('delete_event', lambda w, e: True)
    dialog.show_all()
    try:
      self.db.update(yield_func)
    except Exception, e:
      print e
    dialog.destroy()
    self.update_artists_albums_model()
    if not self.config.getboolean('interface', 'artists_collapsible'):
      self.tvArtistsAlbums.expand_all()
    self.search()

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

  def show_window(self):
    if self.window.get_property('visible'):
      self.window.window.raise_()
      self.window.emit('map')
    else:
      self.restore_geometry()
      self.window.show()
    self.window.grab_focus()
    self.entSearch.grab_focus()

  def hide_window(self):
    self.save_geometry()
    if self.status_icon:
      self.window.hide()

  def save_geometry(self):
    geometry = self.window.get_size() + self.window.get_position()
    self.set_config('interface', 'geometry', ' '.join([str(i) for i in geometry]))

  def restore_geometry(self):
    try:
      width, height, top, left = [int(s) for s in self.config.get('interface', 'geometry').split()]
    except Exception, e:
      width, height, top, left = self.DEFAULT_GEOMETRY
    self.window.resize(width, height)
    if top != None and left != None:
      self.window.move(top, left)

  def on_window_delete(self, window, event):
    self.save_geometry()
    if self.status_icon and \
       self.config.getboolean('interface', 'show_status_icon') and \
       self.config.getboolean('interface', 'close_to_tray'):
      self.hide_window()
      return True
    return False

  def on_section_button_clicked(self, button):
    if button == self.btnSearchOptions:
      self.swSearchOptions.show()
      self.swSearches.hide()
      self.swArtistsAlbums.hide()
      self.entSearch.grab_focus()
    elif button == self.btnSearches:
      self.swSearches.show()
      self.swSearchOptions.hide()
      self.swArtistsAlbums.hide()
      self.tvSearches.realize()
      self.tvSearches.grab_focus()
    else:
      self.swArtistsAlbums.show()
      self.swSearchOptions.hide()
      self.swSearches.hide()
      self.tvArtistsAlbums.realize()
      self.tvArtistsAlbums.grab_focus()

  def on_search_options_row_deleted(self, model, path):
    self.update_sort_order()
    self.search()

  def on_search_field_toggled(self, cell_renderer_toggle, path):
    iter = self.search_options_model.get_iter(path)
    active = self.search_options_model.get_value(iter, 1)
    self.search_options_model.set_value(iter, 1, not active)
    self.update_search_fields()
    query = self.entSearch.get_text()
    if query[:1] != '@':
      self.search()

  def on_artists_albums_button_press_event(self, widget, event):
    if event.button == 3:
      menu = gtk.Menu()
      # Collapsible artists menu item
      if self.supports_not_collapsible():
        item = gtk.CheckMenuItem(_('Collapsible artists'))
        item.set_active(self.config.getboolean('interface', 'artists_collapsible'))
        item.connect('toggled', self.on_artists_albums_popup_collapsible_artists_toggled)
        menu.append(item)
      # Search album on artist as well menu item
      item = gtk.CheckMenuItem(_('Search album on artist as well'))
      item.set_active(self.config.getboolean('options', 'search_on_artist_and_album'))
      item.connect('toggled', self.on_artists_albums_popup_search_on_artist_and_album_toggled)
      menu.append(item)
      # Run the menu
      menu.show_all()
      menu.popup(None, None, None, event.button, event.time)
      return True

  def on_artists_albums_popup_collapsible_artists_toggled(self, menuitem):
    self.set_config('interface', 'artists_collapsible', menuitem.get_active())
    self.update_artists_collapsible()

  def on_artists_albums_popup_search_on_artist_and_album_toggled(self, menuitem):
    self.set_config('options', 'search_on_artist_and_album', menuitem.get_active())

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
        album = query_escape(model.get_value(iter, 0))
        if self.config.getboolean('options', 'search_on_artist_and_album'):
          artist = query_escape(model.get_value(parent, 0))
          queries.append('(artist = %s AND album = %s)' % (artist, album))
        else:
          queries.append('(album = %s)' % album)

    self.entSearch.set_text('@' + ' OR '.join(queries))
    self.search()

  def on_searches_selection_changed(self, selection):
    model, iter = selection.get_selected()
    if iter is None:
      return
    self.inhibit_search += 1
    query, fields = model.get(iter, 1, 2)
    if query[:1] != '@':
      fields = fields.split(' ')
      self.set_active_search_fields(fields)
    self.entSearch.set_text(query)
    self.inhibit_search -= 1
    self.search()

  def on_searches_button_press_event(self, treeview, event):
    data = treeview.get_path_at_pos(int(event.x), int(event.y))
    if data is not None:
      path, col, r_x, r_y = data
      iter = treeview.get_model().get_iter(path)
    else:
      iter = None

    if event.type == gtk.gdk.BUTTON_PRESS:
      if event.button == 1:
        if iter:
          treeview.get_selection().unselect_all()
          treeview.get_selection().select_iter(iter)
          return True
      elif event.button == 3:
        if iter:
          name = treeview.get_model().get_value(iter, 0)
          treeview.get_selection().select_iter(iter)
          menu = gtk.Menu()
          item = gtk.MenuItem(_('Remove'))
          item.connect('activate', self.on_searches_popup_remove, name)
          menu.append(item)
          menu.show_all()
          menu.popup(None, None, None, event.button, event.time)
        else:
          treeview.get_selection().unselect_all()
        return True
    elif event.type == gtk.gdk._2BUTTON_PRESS and event.button == 1:
      if iter:
        files = self.get_selected_result_paths()
        if files:
          if self.config.get('interface', 'double_click_action') == 'play':
            self.ap_driver.play_files(files)
          else:
            self.ap_driver.enqueue_files(files)

  def on_searches_popup_remove(self, menuitem, name):
    self.db.delete_search(name)
    self.tvSearches.get_model().remove(self.search_iters[name])
    del self.search_iters[name]

  def on_search_focus_in_event(self, widget, event):
    self.btnSearchOptions.clicked()

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

  def on_results_header_button_press_event(self, widget, event):
    if event.button == 3:
      columns = self.tvResults.get_columns()
      visible_columns = [column for column in columns if column.get_visible()]
      one_visible_column = len(visible_columns) == 1
      menu = gtk.Menu()
      for column in columns:
        item = gtk.CheckMenuItem(column.column_long)
        if column in visible_columns:
          item.set_active(True)
          if one_visible_column:
            item.set_sensitive(False)
        else:
          item.set_active(False)
        item.connect('activate', self.on_result_header_popup_activate, column)
        menu.append(item)
      menu.show_all()
      menu.popup(None, None, None, event.button, event.time)
      return True
    return False

  def on_results_button_press_event(self, treeview, event):
    if event.button == 1 and event.type == gtk.gdk._2BUTTON_PRESS:
      data = treeview.get_path_at_pos(int(event.x), int(event.y))
      if data is not None:
        path, col, r_x, r_y = data
        iter = treeview.get_model().get_iter(path)
        treeview.get_selection().select_iter(iter)

        files = self.get_selected_result_paths()
        if files:
          if self.config.get('interface', 'double_click_action') == 'play':
            self.ap_driver.play_files(files)
          else:
            self.ap_driver.enqueue_files(files)

  def on_result_header_popup_activate(self, menuitem, column):
    column.set_visible(not column.get_visible())
    visible_columns = ' '.join([column.field for column in self.tvResults.get_columns() if column.get_visible()])
    self.set_config('interface', 'visible_columns', visible_columns)

  def on_results_columns_changed(self, treeview):
    columns = treeview.get_columns()
    if len(columns) != len(self.result_columns):
      # Don't save the column order during destruction
      return
    column_order = ' '.join([column.field for column in columns])
    self.set_config('interface', 'column_order', column_order)

  def on_play_results(self, button):
    files = self.get_selected_result_paths()
    if files:
      self.ap_driver.play_files(files)

  def on_enqueue_results(self, button):
    files = self.get_selected_result_paths()
    if files:
      self.ap_driver.enqueue_files(files)

  def on_save_search(self, button):
    query = self.entSearch.get_text()
    if not query:
      return

    if query[0] != '@':
      fields = self.get_active_search_fields()
      if not fields:
        return
    else:
      fields = []

    sel = self.tvSearches.get_selection()
    if query[:1] == '@':
      name = query
    else:
      fields_long = [self.result_columns[field][2] for field in fields]
      if len(fields_long) == 1:
        name = _("'%(query)s' in %(field)s field") % { 'query': query, 'field': fields_long[0] }
      else:
        name = _("'%(query)s' in %(fields)s and %(last_field)s fields") % {
          'query': query,
          'fields': ', '.join(fields_long[:-1]),
          'last_field': fields_long[-1]
        }

    dialog = gtk.Dialog \
    (
      _('Save search'),
      self.window,
      gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
      (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
       gtk.STOCK_OK,     gtk.RESPONSE_ACCEPT)
    )
    dialog.vbox.pack_start(gtk.Label(_('Name of the search')))
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
        self.btnSearches.clicked()
    dialog.destroy()

  def on_clear_search(self, button):
    self.entSearch.set_text('')
    self.entSearch.grab_focus()

  def on_file_update(self, menuitem):
    self.update_db()

  def on_settings_show_status_icon_toggled(self, menuitem, close_to_tray, start_hidden):
    active = menuitem.get_active()
    self.set_config('interface', 'show_status_icon', active)
    close_to_tray.set_sensitive(active)
    start_hidden.set_sensitive(active)
    self.status_icon.set_visible(active)

  def on_settings_close_to_tray_toggled(self, menuitem):
    active = menuitem.get_active()
    self.set_config('interface', 'close_to_tray', active)

  def on_settings_start_hidden_toggled(self, menuitem):
    active = menuitem.get_active()
    self.set_config('interface', 'start_hidden', active)

  def on_settings_directories(self, menuitem):
    def on_add_directory(button, model):
      dialog = gtk.FileChooserDialog \
        (
          _('Add directory'),
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
    treeview.append_column(gtk.TreeViewColumn(_('Directory'), gtk.CellRendererText(), text = 0))
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
          self.db.delete_root(os.path.join(root, ''))
          changed = True
      for dir in dirs:
        if not dir in roots:
          self.db.add_root(dir)
          changed = True

    dialog.destroy()

    if changed:
      self.update_db()

  def on_settings_driver_toggled(self, menuitem, driver):
    if menuitem.get_active():
      self.set_driver(driver)
      self.set_config('options', 'driver', driver)

  def on_settings_db_source_toggled(self, menuitem, db_source_class):
    if menuitem.get_active():
      self.set_db_source(db_source_class)
      self.set_config('options', 'db_source', db_source_class.name)

  def on_settings_update_on_startup_toggled(self, menuitem):
    self.set_config('options', 'update_on_startup', menuitem.get_active())

  def on_settings_set_double_click_action(self, menuitem, action):
    self.set_config('interface', 'double_click_action', action)

  def on_about(self, menuitem):
    dialog = gtk.AboutDialog()
    dialog.set_logo(self.icons[64])
    dialog.set_name('MethLab')
    dialog.set_version('0.0.0')
    c1 = _('Copyright (c) 2007 Ingmar Steen.')
    c2 = _('The bundled xmmsalike library is (C) 2006 Ben Wolfson and Risto A. Paju')
    c3 = _('The bundled mpdclient3 library is (C) 2006 Scott Horowitz')
    dialog.set_copyright(c1 + '\n' + c2 + '\n' + c3)
    dialog.set_license(LICENSE)
    dialog.set_website('http://methlab.thegraveyard.org/')
    dialog.set_authors([_('Ingmar Steen <iksteen@gmail.com> (Main developer)')])
    dialog.run()
    dialog.destroy()

  def on_toggle_search_field(self, accel_group, acceleratable, keyval, modifier):
    path = int(chr(keyval)) - 1
    iter = self.search_options_model.get_iter(path)
    value = self.search_options_model.get_value(iter, 1)
    self.search_options_model.set(iter, 1, not value)

  def on_status_icon_activate(self, status_icon):
    if self.window.has_toplevel_focus():
      self.hide_window()
    else:
      self.show_window()

  def on_status_icon_popup_menu(self, status_icon, button, activate_time):
    self.status_icon_menu.popup(None, None, None, button, activate_time)

  def on_status_icon_menu_show(self, menuitem):
    self.show_window()

  def on_status_icon_menu_hide(self, menuitem):
    self.hide_window()
