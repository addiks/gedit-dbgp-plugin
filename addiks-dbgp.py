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

from gi.repository import GLib, Gtk, Gdk, GObject, Gedit, PeasGtk, Gio, GtkSource, GdkPixbuf, Notify
from profilemanager import ProfileManager
from session import DebugSession
from helpers import *
from inspect import getmodule
from gladehandler import GladeHandler
import os
import random
import time
from time import sleep
import subprocess
import socket
from os.path import expanduser
from _thread import start_new_thread
import xml.etree.ElementTree as ElementTree

class AddiksDBGPApp(GObject.Object, Gedit.AppActivatable):
    app = GObject.property(type=Gedit.App)

    def __init__(self):
        GObject.Object.__init__(self)
        Notify.init("gedit_addiks_xdebug")
        self._debug_profile_manager = None
        self._listening_sockets = []
        self._active_sessions = []
        self._breakpoints = None
        self._glade_builder = None
        self._glade_handler = None
        
    def do_activate(self):
        AddiksDBGPApp.__instance = self

    def do_deactivate(self):
        AddiksDBGPApp.__instance = None

    def do_update_state(self):
        pass

    def open_window_file(self, filePath, line=0, column=0):

        found = False
        tab = None
        window = None

        for view in self.get_all_views():
            document = view.view.get_buffer()
            if document != None and document.get_location() != None:
                viewFilePath = document.get_location().get_path()
                if filePath == viewFilePath:
                    found = True
                    window = self.get_window_by_view(view.view).window
                    tab = window.get_tab_from_location(document.get_location())
                    window.set_active_tab(tab)
        
        location = Gio.File.new_for_path(filePath)

        if not found:

            for window in self.get_all_windows():
                window = window.window
                tab = window.create_tab_from_location(location, None, line, column, False, True)
                found = True
                break
                
            if not found:
                window = self.app.create_window()
                tab = window.create_tab_from_location(location, None, line, column, False, True)

        # move to line
        view = tab.get_view()
        document = view.get_buffer()
        textIter = document.get_end_iter().copy()
        textIter.set_line(line-1)
        textIter.set_line_offset(0)
        view.scroll_to_iter(textIter, 0.3, False, 0.0, 0.5)

        start_new_thread(self.delayed_present, (window, ))

        return tab

    def delayed_present(self, window):
        sleep(0.01)
        GLib.idle_add(window.present)

    def show_profile_manager(self, foo=None):
        self.get_profile_manager().show()

    def show_breakpoints(self, foo=None):

        builder = self._getGladeBuilder()

        windowBreakpoints = builder.get_object("windowBreakpoints")
        liststoreBreakpoints = builder.get_object("liststoreBreakpoints")
        treeviewBreakpoints = builder.get_object("treeviewBreakpoints")

        selection = treeviewBreakpoints.get_selection()
        selection.set_mode(Gtk.SelectionMode.MULTIPLE)

        breakpoints = self.get_all_breakpoints()
        for filePath in breakpoints:
            for line in breakpoints[filePath]:
                rowIter = liststoreBreakpoints.append()
                liststoreBreakpoints.set_value(rowIter, 0, filePath)
                liststoreBreakpoints.set_value(rowIter, 1, line)

        windowBreakpoints.show_all()

    def get_profile_manager(self):
        if self._debug_profile_manager == None:
            self._debug_profile_manager = ProfileManager(self)
        return self._debug_profile_manager

    def __show_dialog(self, message):
        GLib.idle_add(self.__do_show_dialog, message)

    def __do_show_dialog(self, message):

        notification = Notify.Notification.new("Gedit - XDebug client", message)
        success = notification.show()

        if not success:
            dialog = Gtk.MessageDialog(
                None, 
                None, 
                Gtk.MessageType.ERROR, 
                Gtk.ButtonsType.CLOSE, 
                message)
            dialog.connect("response", lambda a, b, c=None: dialog.destroy());
            dialog.run()

    ### SINGLETON

    __instance = None
    
    @staticmethod
    def get():
        if AddiksDBGPApp.__instance == None:
            AddiksDBGPApp.__instance = AddiksDBGPApp()
        return AddiksDBGPApp.__instance
        
    ### WINDOW / VIEW MANAGEMENT

    windows = []

    def get_all_windows(self):
        return self.windows

    def register_window(self, window):
        if window not in self.windows:
            self.windows.append(window)

    def unregister_window(self, window):
        if window in self.windows:
            self.windows.remove(window)

    def get_window_by_view(self, view):
        for window in self.windows:
            if view in window.window.get_views():
                return window

    views = []

    def get_all_views(self):
        return self.views

    def register_view(self, view):
        if view not in self.views:
            self.views.append(view)

    def unregister_view(self, view):
        if view in self.views:
            self.views.remove(view)


    ### DBGP PORT LISTEN

    def _connectDbgp(self, host, port, ideKey):
        self._dbgpSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._dbgpSocket.connect((host, port))

    def _disconnectDbgp(self, host, port, ideKey):
        if self._dbgpSocket != None:
            pass

    ### SOCKETS

    def start_listening(self, foo=None):
        ports = []
        dbgpProxies = []
        for profileName in self.get_profile_manager().get_profiles():
            profile = self.get_profile_manager().get_profile(profileName)
            ports.append(profile['port'])
            if profile['dbgp_active']:
                dbgpProxies.append([
                    profile['dbgp_host'],
                    profile['dbgp_port'],
                    profile['dbgp_ide_key'],
                ])
        openedSockets = []
        port = None
        try:
            for port in set(ports):
                listenSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._listening_sockets.append(listenSocket)
                listenSocket.bind(("0.0.0.0", int(port)))
                openedSockets.append(listenSocket)
                start_new_thread(self._listenPort, (listenSocket, ))

            for dbgpHost, dbgpPort, ideKey in dbgpProxies:
                start_new_thread(self.dbgp_proxy_start, (dbgpHost, dbgpPort, ideKey, ports[0], ))

            for view in self.get_all_views():
                view.show_breakpoint_gutter()

            for window in self.get_all_windows():
                window.set_listen_menu_set_started()

        except OSError as exception:
            for listenSocket in openedSockets:
                listenSocket.close()
            self.__show_dialog("Cannot open port, the port "+str(int(port))+" is already in use")

    def does_listen(self):
        return len(self._listening_sockets)>0
    
    def _listenPort(self, listenSocket):
        listenSocket.listen(5)
        listenSocket.settimeout(0.5)
        while listenSocket in self._listening_sockets:
            try:
                (clientSocket, address) = listenSocket.accept()
                start_new_thread(self._acceptClient, (clientSocket, address, ))
            except (socket.timeout, OSError):
                pass

    def _acceptClient(self, clientSocket, address=None):
        session = DebugSession(self, clientSocket)
        self._active_sessions.append(session)
        session.init()

    def stop_listening(self, foo=None):
        for socket in self._listening_sockets:
            socket.close()
        self._listening_sockets = []

        for view in self.get_all_views():
            view.hide_breakpoint_gutter()

        for window in self.get_all_windows():
            window.set_listen_menu_set_stopped()

    def dbgp_proxy_start(self, hostname, port, ideKey, listenPort=9001):
        dbgpSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        dbgpSocket.settimeout(0.5)
        address = (str(hostname), int(port))
        try:
            dbgpSocket.connect(address)
            dbgpSocket.send(bytes("proxyinit -p "+str(int(listenPort))+" -k "+ideKey+" -m 0\0", 'UTF-8'))
            responseXmlData = dbgpSocket.recv(1024).decode("utf-8")
            responseXml = ElementTree.fromstring(responseXmlData)
            if responseXml.attrib['success'] != "1":
                errorMessage = responseXml[0][0].text
                self.__show_dialog("Error registering with dbgp-Proxy "+repr(address)+": "+errorMessage)
        except ConnectionRefusedError:
            self.__show_dialog("Error connecting to dbgp-Proxy "+repr(address)+": Connection refused!")
        except (TimeoutError, socket.timeout):
            self.__show_dialog("Error connecting to dbgp-Proxy "+repr(address)+": Timeout!")

        except ElementTree.ParseError:
            # retry with size before packet
            dbgpSocket.close()
            dbgpSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            dbgpSocket.settimeout(0.5)
            try:
                dbgpSocket.connect(address)
                packetData = "proxyinit -p "+str(int(listenPort))+" -k "+ideKey+" -m 0\0"
                dbgpSocket.send(bytes(str(len(packetData)) + "\0" + packetData), 'UTF-8')
                responseXmlData = dbgpSocket.recv(1024).decode("utf-8")
                responseXml = ElementTree.fromstring(responseXmlData)
                if responseXml.attrib['success'] != "1":
                    errorMessage = responseXml[0][0].text
                    self.__show_dialog("Error registering with dbgp-Proxy "+repr(address)+": "+errorMessage)
            except ConnectionRefusedError:
                self.__show_dialog("Error connecting to dbgp-Proxy "+repr(address)+": Connection refused!")
            except (TimeoutError, socket.timeout):
                self.__show_dialog("Error connecting to dbgp-Proxy "+repr(address)+": Timeout!")

    def dbgp_proxy_stop(self, ideKey):
        dbgpSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        address = (hostname, int(port))
        try:
            dbgpSocket.connect(address)
            dbgpSocket.send(bytes("proxystop -k "+ideKey+"\0", 'UTF-8'))
            responseXmlData = dbgpSocket.recv(1024).decode("utf-8")
            responseXml = ElementTree.fromstring(responseXmlData)
            if responseXml.attrib['success'] != "1":
                errorMessage = responseXml[0][0].text
                self.__show_dialog("Error registering with dbgp-Proxy "+repr(address)+": "+errorMessage)
        except ConnectionRefusedError:
            self.__show_dialog("Error connecting to dbgp-Proxy "+repr(address)+": Connection refused!")

    def get_active_sessions(self):
        return self._active_sessions

    def remove_session(self, session):
        if session in self._active_sessions:
            self._active_sessions.remove(session)

    def _runBrowser(self, url, ideKey):

        if '?' in url:
            url = url + "&"
        else:
            url = url + "?"

        url = url + "XDEBUG_SESSION_START=" + ideKey

        os.system("xdg-open '"+url+"'")

    def _stopBrowser(self, url, ideKey):

        if '?' in url:
            url = url + "&"
        else:
            url = url + "?"

        url = url + "XDEBUG_SESSION_STOP=" + ideKey

        os.system("xdg-open '"+url+"'")

    ### SESSION MANAGEMENT

    def session_run(self, foo=None):
        sessions = self.get_active_sessions()
        if len(sessions) > 0:
            sessions[0].run()

    def session_run_to_end(self, foo=None):
        sessions = self.get_active_sessions()
        if len(sessions) > 0:
            sessions[0].run(True)

    def session_step_into(self, foo=None):
        sessions = self.get_active_sessions()
        if len(sessions) > 0:
            sessions[0].step_into()

    def session_step_over(self, foo=None):
        sessions = self.get_active_sessions()
        if len(sessions) > 0:
            sessions[0].step_over()

    def session_step_out(self, foo=None):
        sessions = self.get_active_sessions()
        if len(sessions) > 0:
            sessions[0].step_out()

    def session_stop(self, foo=None):
        sessions = self.get_active_sessions()
        if len(sessions) > 0:
            sessions[0].stop()

    ### BREAKPOINTS

    def _get_breakpoints_filepath(self):
        userDir = os.path.expanduser("~")
        filePath = userDir + "/.local/share/addiks/gedit/xdebug/breakpoints"
        return filePath

    def _save_breakpoints(self):
        filePath = self._get_breakpoints_filepath()
        if not os.path.exists(os.path.dirname(filePath)):
            os.makedirs(os.path.dirname(filePath))
        file_put_contents(filePath, repr(self.get_all_breakpoints()))

    def get_all_breakpoints(self):
        if self._breakpoints == None:
            self._breakpoints = {}
            filePath = self._get_breakpoints_filepath()
            if os.path.exists(filePath):
                self._breakpoints = eval(file_get_contents(filePath))
        return self._breakpoints

    def clear_breakpoints(self):
        pass

    def get_breakpoints(self, filePath):
        breakpoints = self.get_all_breakpoints()
        if filePath not in breakpoints:
            breakpoints[filePath] = []
        return breakpoints[filePath]

    def toggle_breakpoint(self, filePath, line):
        breakpoints = self.get_all_breakpoints()
        if filePath not in breakpoints:
            breakpoints[filePath] = []
        if line in breakpoints[filePath]:
            breakpoints[filePath].remove(line)
            for session in self.get_active_sessions():
                start_new_thread(session.remove_breakpoint_by_file_line, (filePath, line, ))
        else:
            breakpoints[filePath].append(line)
            for session in self.get_active_sessions():
                start_new_thread(session.set_breakpoint, ({
                    'type':     'line',
                    'filename': filePath,
                    'lineno':   line,
                }, ))
        self._save_breakpoints()

    ### PATHS

    def get_data_dir(self):
        home = expanduser("~")
        basedir = home + "/.local/share/gedit/addiks/xdebug"
        return basedir

    ### GLADE
       
    def _getGladeHandler(self):
        if self._glade_handler == None:
            self.__initGlade()
        return self._glade_handler

    def _getGladeBuilder(self):
        if self._glade_builder == None:
            self.__initGlade()
        return self._glade_builder

    def __initGlade(self):
        self._glade_builder = Gtk.Builder()
        self._glade_builder.add_from_file(os.path.dirname(__file__)+"/debugger.glade")
        self._glade_handler = GladeHandler(self, self._glade_builder)
        self._glade_builder.connect_signals(self._glade_handler)
        

class AddiksDBGPView(GObject.Object, Gedit.ViewActivatable):
    view = GObject.property(type=Gedit.View)

    def __init__(self):
        GObject.Object.__init__(self)
        self._gutter_renderer = None
        self._gutter_breakpoint_icon = None
        self._gutter_empty_pixbuf = None
        self.__drawArea = None

    def do_activate(self):
        AddiksDBGPApp.get().register_view(self)

        document = self.view.get_buffer()

        window = AddiksDBGPApp.get().get_window_by_view(self.view)

        if document != None:
            document.connect("loaded", self.update_stack_marks)

            location = document.get_location()
            if location != None:
                tab = window.window.get_tab_from_location(location)

                viewFrame = tab.get_children()[0]
                
                scrolledWindow = viewFrame.get_child()

                self.__drawArea = scrolledWindow
                self.__drawArea.set_property("app-paintable", True)
                self.__drawArea.connect("size-allocate", self.on_drawingarea_size_allocate)
                self.__drawArea.connect_after("draw", self.on_drawingarea_draw)

        if AddiksDBGPApp.get().does_listen():
            self.show_breakpoint_gutter()

    def on_drawingarea_size_allocate(self, widget, allocationRect, data=None):
        widget.queue_draw()

    def on_drawingarea_draw(self, widget, cairo, data=None):
        textView = self.view
        lineCount = textView.get_buffer().get_end_iter().get_line()
        
        viewHeight = widget.get_allocated_height()
        viewWidth  = widget.get_allocated_width()

        width = 3
        document = self.view.get_buffer()
        filePath = document.get_location().get_path()
        for session in AddiksDBGPApp.get().get_active_sessions():
            for entry in session.get_prepared_stack():
                localFilePath = session.mapRemoteToLocalPath(entry['filename'][7:])
                if 'filename' in entry and filePath == localFilePath:
                    line = int(entry['lineno'])
                    top    = int((line   / lineCount) * viewHeight)
                    cairo.rectangle(viewWidth-width, top, width, 7)

        cairo.set_source_rgb(0, 255, 0)
        cairo.fill()

        return False

    def do_deactivate(self):
        AddiksDBGPApp.get().unregister_view(self)

        if AddiksDBGPApp.get().does_listen():
            self.hide_breakpoint_gutter()

    def show_breakpoint_gutter(self):
        renderer = self.get_gutter_renderer()
        gutter = self.view.get_gutter(Gtk.TextWindowType.LEFT)
        gutter.insert(renderer, -40) # -40 is order-number; line numbers are on -30

    def hide_breakpoint_gutter(self):
        renderer = self.get_gutter_renderer()
        gutter = self.view.get_gutter(Gtk.TextWindowType.LEFT)
        gutter.remove(renderer)

    def get_gutter_renderer(self):
        if self._gutter_renderer == None:
            renderer = GtkSource.GutterRendererPixbuf()
            renderer.set_size(16)
            renderer.connect("query-data",         self._on_breakpoint_gutter_query_data)
            renderer.connect("query_activatable",  self._on_breakpoint_gutter_query_activatable)
            self._gutter_renderer = renderer
        return self._gutter_renderer

    def _get_breakpoint_icon(self):
        if self._gutter_breakpoint_icon == None:
            iconPath = os.path.dirname(__file__)+"/breakpoint.png"
            gfile = Gio.File.new_for_path(iconPath)
            gicon = Gio.FileIcon.new(gfile)
            self._gutter_breakpoint_icon = gicon
        return self._gutter_breakpoint_icon
    
    def _get_empty_pixbuf(self):
        if self._gutter_empty_pixbuf == None:
            colorspace = GdkPixbuf.Colorspace.RGB
            self._gutter_empty_pixbuf = GdkPixbuf.Pixbuf.new(colorspace, True, 8, 16, 16)
            self._gutter_empty_pixbuf.fill(0x00000000)
        return self._gutter_empty_pixbuf
            
    def _on_breakpoint_gutter_query_activatable(self, renderer, textIter, area, event):  
        if event.get_event_type() == Gdk.EventType.BUTTON_PRESS:
            document = self.view.get_buffer()
            if document.get_location() != None:
                filePath = document.get_location().get_path()   
                line = textIter.get_line()+1 

                AddiksDBGPApp.get().toggle_breakpoint(filePath, line)
    
                # force redraw
                renderer = self.get_gutter_renderer()
                gutter = self.view.get_gutter(Gtk.TextWindowType.LEFT)
                gutter.queue_draw()

    def _on_breakpoint_gutter_query_data(self, renderer, textIterStart, textIterEnd, state):
        document = self.view.get_buffer()
        if document.get_location() != None:
            filePath = document.get_location().get_path()
            if textIterStart.get_line()+1 in AddiksDBGPApp.get().get_breakpoints(filePath):
                renderer.set_gicon(self._get_breakpoint_icon())
            else:          
                renderer.set_pixbuf(self._get_empty_pixbuf())

    def update_stack_marks(self, document=None, foo=None):
        if document == None:
            document = self.view.get_buffer()

        document.remove_tag(self.get_stack_tag(True),  document.get_start_iter(), document.get_end_iter())
        document.remove_tag(self.get_stack_tag(False), document.get_start_iter(), document.get_end_iter())

        if document.get_location() != None:
            filePath = document.get_location().get_path()
            for session in AddiksDBGPApp.get().get_active_sessions():
                for entry in session.get_prepared_stack():
                    localFilePath = session.mapRemoteToLocalPath(entry['filename'][7:])
                    if 'filename' in entry and filePath == localFilePath:
                        tag = self.get_stack_tag(int(entry['level']) == 0)

                        #continue
                        beginIter = document.get_end_iter().copy()
                        beginIter.set_line(int(entry['lineno'])-1)
                        beginIter.set_line_offset(0)

                        endIter = beginIter.copy()
                        endIter.set_line(int(entry['lineno'])-1)
                        endIter.set_line_offset(1)
                        endIter.forward_to_line_end()

                        document.apply_tag(tag, beginIter, endIter)

    def get_stack_tag(self, isTop=False):

        color  = "#CAFFCA"
        tagKey = "xdebug_stack_entry"

        if isTop:
            tagKey += "_top"
            color  = "#A0FFA0"

        document = self.view.get_buffer()
        tagTable = document.get_tag_table()
        tag = tagTable.lookup(tagKey)

        if tag == None:
            tag = document.create_tag(tagKey, background=color)

        return tag

    
class AddiksDBGPWindow(GObject.Object, Gedit.WindowActivatable):
    window = GObject.property(type=Gedit.Window)

    def __init__(self):
        GObject.Object.__init__(self)

    def do_activate(self):
        AddiksDBGPApp.get().register_window(self)
        
        plugin_path = os.path.dirname(__file__)
        self._ui_manager = self.window.get_ui_manager()
        actions = [
            ['DebugAction',                "Debugging",                           "",    None],
            ['StartListeningAction',       "Start listening for debug-sessions",  "",    AddiksDBGPApp.get().start_listening],
            ['StopListeningAction',        "Stop listening for debug-sessions",   "",    AddiksDBGPApp.get().stop_listening],
            ['ManageProfilesAction',       "Manage profiles",                     "",    AddiksDBGPApp.get().show_profile_manager],
            ['ManageBreakpointsAction',    "Manage breakpoints",                  "",    AddiksDBGPApp.get().show_breakpoints],
            ['SessionStopAction',          "Stop session",                        "",    AddiksDBGPApp.get().session_stop],
            ['SessionStepIntoAction',      "Step into",                           "F5",  AddiksDBGPApp.get().session_step_into],
            ['SessionStepOverAction',      "Step over",                           "F6",  AddiksDBGPApp.get().session_step_over],
            ['SessionStepOutAction',       "Step out",                            "F7",  AddiksDBGPApp.get().session_step_out],
            ['SessionRunAction',           "Run",                                 "F8",  AddiksDBGPApp.get().session_run],
            ['SessionRunToEndAction',      "Run to end (ignore breakpoints)",     "F9",  AddiksDBGPApp.get().session_run_to_end],
        ]

        self._actions = Gtk.ActionGroup("AddiksDBGPMenuActions")
        for actionName, title, shortcut, callback in actions:
            self._actions.add_actions([(actionName, Gtk.STOCK_INFO, title, shortcut, "", callback),])

        self._ui_manager.insert_action_group(self._actions)
        self._ui_merge_id = self._ui_manager.add_ui_from_string(file_get_contents(plugin_path + "/menubar.xml"))
        
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
        return self._ui_manager.get_accel_group()

    def set_listen_menu_set_started(self):
        actionStart = self._actions.get_action("StartListeningAction")
        actionStop  = self._actions.get_action("StopListeningAction")
        actionStart.set_visible(False)
        actionStop.set_visible(True)

    def set_listen_menu_set_stopped(self):
        actionStart = self._actions.get_action("StartListeningAction")
        actionStop  = self._actions.get_action("StopListeningAction")
        actionStart.set_visible(True)
        actionStop.set_visible(False)


