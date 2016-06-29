# Copyright (C) 2015 Gerrit Addiks <gerrit@addiks.net>
# https://github.com/addiks/gedit-dbgp-plugin
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import random
import time
import subprocess
import socket
import xml.etree.ElementTree as ElementTree
from inspect import getmodule
from time import sleep
from os.path import expanduser
from _thread import start_new_thread
from gi.repository import GLib, Gtk, Gdk, GObject, Gedit, PeasGtk, Gio, GtkSource, GdkPixbuf, Notify
from AddiksDBGP.helpers import *
from AddiksDBGP.ProfileManager import ProfileManager
from AddiksDBGP.DebugSession import DebugSession
from AddiksDBGP.GladeHandler import GladeHandler
from AddiksDBGP.AddiksDBGPApp import AddiksDBGPApp, ACTIONS

class AddiksDBGPWindow(GObject.Object, Gedit.WindowActivatable):
    window = GObject.property(type=Gedit.Window)
    _ui_manager = None

    def __init__(self):
        GObject.Object.__init__(self)

    def do_activate(self):
        AddiksDBGPApp.get().register_window(self)

        plugin_path = os.path.dirname(__file__)

        self._actions = Gtk.ActionGroup("AddiksDBGPMenuActions")
        self._actionsGio = {}
        for actionName, title, shortcut, callbackName in ACTIONS:
            action = Gio.SimpleAction(name=actionName)
            callback = None
            if callbackName != None:
                callback = getattr(AddiksDBGPApp.get(), callbackName)
                action.connect('activate', callback)
            self._actions.add_actions([(actionName, Gtk.STOCK_INFO, title, shortcut, "", callback),])
            self._actionsGio[actionName] = action
            self.window.add_action(action)
            self.window.lookup_action(actionName).set_enabled(True)

        if "get_ui_manager" in dir(self.window):# build menu for gedit 3.10 (global menu per window)
            self._ui_manager = self.window.get_ui_manager()
            self._ui_manager.insert_action_group(self._actions)
            self._ui_merge_id = self._ui_manager.add_ui_from_string(file_get_contents(plugin_path + "/../menubar.3-10.xml"))

            debugMenu = self._ui_manager.get_widget("/ui/MenuBar/AddiksDbgpDebug").get_submenu()

            xdebugMenuItem = Gtk.MenuItem()
            xdebugMenuItem.set_label("XDebug / HTTP")
            xdebugMenuItem.show()

            debugMenu.attach(xdebugMenuItem, 0, 1, 0, 1)

            xdebugMenu = Gtk.Menu()
            xdebugMenuItem.set_submenu(xdebugMenu)

            for profileName in AddiksDBGPApp.get().get_profile_manager().get_profiles():

                menuItem = Gtk.MenuItem()
                menuItem._addiks_profile_name = profileName
                menuItem.set_label("Send start-debugging request to: "+profileName)
                menuItem.connect("activate", self.on_run_session_per_menu)
                menuItem.show()

                xdebugMenu.attach(menuItem, 0, 1, 0, 1)

            seperator = Gtk.SeparatorMenuItem()
            seperator.show()
            xdebugMenu.attach(seperator, 0, 1, 0, 1)

            for profileName in AddiksDBGPApp.get().get_profile_manager().get_profiles():

                menuItem = Gtk.MenuItem()
                menuItem._addiks_profile_name = profileName
                menuItem.set_label("Send stop-debugging request to: "+profileName)
                menuItem.connect("activate", self.on_stop_session_per_menu)
                menuItem.show()

                xdebugMenu.attach(menuItem, 0, 1, 0, 1)

            self._ui_manager.ensure_update()

        if AddiksDBGPApp.get().does_listen():
            self.set_listen_menu_set_started()
        else:
            self.set_listen_menu_set_stopped()

    def on_run_session_per_menu(self, menuItem=None):
        profileName = menuItem._addiks_profile_name
        profile = AddiksDBGPApp.get().get_profile_manager().get_profile()
        AddiksDBGPApp.get()._runBrowser(profile['url'], profile['dbgp_ide_key'])

    def on_stop_session_per_menu(self, menuItem=None):
        profileName = menuItem._addiks_profile_name
        profile = AddiksDBGPApp.get().get_profile_manager().get_profile()
        AddiksDBGPApp.get()._stopBrowser(profile['url'], profile['dbgp_ide_key'])

    def do_deactivate(self):
        AddiksDBGPApp.get().unregister_window(self)

    def do_update_state(self):
        pass

    def get_accel_group(self):
        if self._ui_manager != None:
            return self._ui_manager.get_accel_group()

    def set_listen_menu_set_started(self):
        self._actions.get_action("StartListeningAction").set_visible(False)
        self._actions.get_action("StopListeningAction").set_visible(True)
        self._actionsGio["StartListeningAction"].set_enabled(False)
        self._actionsGio["StopListeningAction"].set_enabled(True)

    def set_listen_menu_set_stopped(self):
        self._actions.get_action("StartListeningAction").set_visible(True)
        self._actions.get_action("StopListeningAction").set_visible(False)
        self._actionsGio["StartListeningAction"].set_enabled(True)
        self._actionsGio["StopListeningAction"].set_enabled(False)

