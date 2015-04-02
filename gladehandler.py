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

from gi.repository import GLib, Gtk, Gdk
from helpers import *
from os.path import expanduser
from _thread import start_new_thread
import traceback

class GladeHandler:
    def __init__(self, plugin, builder, profile_manager=None, session=None, path_mapping_manager=None):
        self._plugin               = plugin
        self._profile_manager      = profile_manager
        self._path_mapping_manager = path_mapping_manager
        self._builder              = builder
        self._session              = session
        self._watches              = {}

    def onCloseWindow(self, widget=None, data=None):
        widget.hide()
        return True

    ### PROFILE MANAGER

    def updateDbgpVisibility(self, checkbox=None):
        builder   = self._builder
        checkbox  = builder.get_object("checkbuttonUseDbgp")

        hostInput     = builder.get_object("entryDbgpHost")
        KeyInput      = builder.get_object("entryDbgpIDEKey")
        portInput     = builder.get_object("spinbuttonDbgpPort")
        pathMapButton = builder.get_object("buttonConfigurePathMapping")

        hostInput    .set_sensitive(checkbox.get_active())
        portInput    .set_sensitive(checkbox.get_active())

    def onProfileChanged(self, profileList=None):
        builder = self._builder
        profileList = builder.get_object("comboboxProfileList")
        activeTreeIter = profileList.get_active_iter()
        profileModel = profileList.get_model()
        profileName = profileModel.get_value(activeTreeIter, 0)
        self._profile_manager.set_active_profile(profileName)
        self._profile_manager.load_profile(profileName)

    def onProfileModified(self, widget=None):
        builder = self._builder
        active_profile_name = self._profile_manager.get_active_profile()
        profile = self._profile_manager.get_profile_defaults()
        profile.update({
            'url':          builder.get_object("entryURL")          .get_text(),
            'port':         builder.get_object("spinbuttonPort")    .get_value(),
            'dbgp_active':  builder.get_object("checkbuttonUseDbgp").get_active(),
            'dbgp_host':    builder.get_object("entryDbgpHost")     .get_text(),
            'dbgp_port':    builder.get_object("spinbuttonDbgpPort").get_value(),
            'dbgp_ide_key': builder.get_object("entryDbgpIDEKey")   .get_text()
        })
        self._profile_manager.store_profile(active_profile_name, profile)

    def onProfileAdd(self, button=None):
        builder = self._builder
        dialog = Gtk.Dialog("Add debug profile", builder.get_object("windowProfiles"))
        dialog.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        dialog.add_button(Gtk.STOCK_OK, Gtk.ResponseType.OK)
        dialogBox = dialog.get_content_area()

        userEntry = Gtk.Entry()
        dialogBox.pack_end(userEntry, False, False, 0)

        dialog.show_all()
        response = dialog.run()
        profileName = userEntry.get_text()
        dialog.destroy()

        if (response == Gtk.ResponseType.OK) and (profileName != ''):
            self._profile_manager.create_profile(profileName)

    def onProfileRemove(self, button=None):
        self._profile_manager.drop_profile()

    def onStartDebugSession(self, button=None):
        self._profile_manager.onStartDebugSession()

    def onShowPathMappingWindow(self, button=None):
        self._profile_manager.get_pathmapping_manager().show()
        
    ### SESSION

    def onRun(self, button=None):
        start_new_thread(self._session.run, ())

    def onRunToEnd(self, button=None):
        start_new_thread(self._session.run, (True, ))

    def onSessionStop(self, button=None):
        start_new_thread(self._session.stop, ())

    def onStepInto(self, button=None):
        start_new_thread(self._session.step_into, ())

    def onStepOver(self, button=None):
        start_new_thread(self._session.step_over, ())

    def onStepOut(self, button=None):
        start_new_thread(self._session.step_out, ())

    def onClearWatches(self, button=None):
        self._session.clear_watches()

    def onAddWatch(self, button=None):
        builder = self._builder

        dialog = Gtk.Dialog("Add watch", builder.get_object("windowSession"))
        dialog.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        dialog.add_button(Gtk.STOCK_OK, Gtk.ResponseType.OK)
        dialogBox = dialog.get_content_area()

        userEntry = Gtk.Entry()
        dialogBox.pack_end(userEntry, False, False, 0)

        dialog.show_all()
        response = dialog.run()
        watchDefinition = userEntry.get_text()
        dialog.destroy()

        if (response == Gtk.ResponseType.OK) and (watchDefinition != ''):
            self._session.add_watch(watchDefinition)

    def onRemoveWatch(self, button=None):
        builder = self._builder
        treeviewWatches  = builder.get_object("treeviewWatches")
        treestoreWatches = builder.get_object("treestoreWatches")

        selection = treeviewWatches.get_selection()

        store, selected_rows = selection.get_selected_rows()

        for path in selected_rows:
            treeIter = treestoreWatches.get_iter(path)
            definition = treestoreWatches.get_value(treeIter, 0)
            self._session.remove_watch(definition)

    def onEditWatch(self, button=None):
        builder = self._builder
        treeviewWatches  = builder.get_object("treeviewWatches")
        treestoreWatches = builder.get_object("treestoreWatches")

        selection = treeviewWatches.get_selection()

        store, selected_rows = selection.get_selected_rows()

        for path in selected_rows:
            treeIter   = treestoreWatches.get_iter(path)
            fullName   = treestoreWatches.get_value(treeIter, 2)
            value      = treestoreWatches.get_value(treeIter, 1)

            dialog = Gtk.Dialog("Add watch", builder.get_object("windowSession"))
            dialog.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
            dialog.add_button(Gtk.STOCK_OK,     Gtk.ResponseType.OK)
            dialogBox = dialog.get_content_area()

            typeListStore = Gtk.ListStore(str)
            types = []
            for typeName, typeType, typeXsiType in self._session.get_types():
                treeIter = typeListStore.append()
                typeListStore.set_value(treeIter, 0, typeName)
                types.append(typeName)

            cellRenderer = Gtk.CellRendererText()

            labelFullName = Gtk.Label()
            labelFullName.set_text(fullName)

            typeComboBox = Gtk.ComboBox()
            typeComboBox.set_model(typeListStore)
            typeComboBox.pack_start(cellRenderer, True)
            typeComboBox.add_attribute(cellRenderer, "text", 0)
            typeComboBox.set_active(0)

            userEntryTextBuffer = Gtk.TextBuffer()
            userEntryTextBuffer.set_text(value)

            userEntryTextView = Gtk.TextView()
            userEntryTextView.set_buffer(userEntryTextBuffer)

            dialogBox.pack_start(labelFullName,     False, False, 0)
            dialogBox.pack_start(typeComboBox,      False, False, 0)
            dialogBox.pack_start(userEntryTextView, False, False, 0)

            dialog.show_all()
            response = dialog.run()
            newValue = userEntryTextBuffer.get_text()
            newType = types[typeComboBox.get_active()]
            dialog.destroy()

            if (response == Gtk.ResponseType.OK) and (newValue != ''):
                self._session.set_property(fullName, newType, newValue)

    def onWatchExpanded(self, treeView=None, treeIter=None, treePath=None, userData=None):
        builder = self._builder
        treeviewWatches  = builder.get_object("treeviewWatches")
        treestoreWatches = builder.get_object("treestoreWatches")

        fullName = treestoreWatches.get_value(treeIter, 2)
        self._session.expand_watch(fullName)

    def onWatchCollapsed(self, treeView=None, treeIter=None, treePath=None, userData=None):
        builder = self._builder
        treeviewWatches  = builder.get_object("treeviewWatches")
        treestoreWatches = builder.get_object("treestoreWatches")

        fullName = treestoreWatches.get_value(treeIter, 2)
        self._session.collapse_watch(fullName)

    def onStackEntryOpen(self, treeView=None, rowNr=0, treeViewColumn=None):
        builder = self._builder
        treeviewStack  = builder.get_object("treeviewStack")
        liststoreStack = builder.get_object("liststoreStack")

        treePath = Gtk.TreePath(rowNr)
        treeIter = liststoreStack.get_iter(treePath)
        uri      = liststoreStack.get(treeIter, 0)[0]
        lineNr   = liststoreStack.get(treeIter, 1)[0]

        self._session.open_uri_resouce(uri, int(lineNr))

    def getWatchesScrollPosition(self):
        builder = self._builder
        scrolledWindow = builder.get_object("scrolledwindowWatches")

        top  = scrolledWindow.get_vadjustment().get_value()
        left = scrolledWindow.get_hadjustment().get_value()

        return [top, left]

    def setWatchesScrollPosition(self, positions):
        GLib.idle_add(self._do_setWatchesScrollPosition, positions)

    def _do_setWatchesScrollPosition(self, positions):
        builder = self._builder
        scrolledWindow = builder.get_object("scrolledwindowWatches")

        top, left = positions
        print(top)
        print(left)
        print(scrolledWindow.get_vadjustment().get_upper())
        print(scrolledWindow.get_vadjustment().get_lower())

        scrolledWindow.get_vadjustment().set_value(top)
        scrolledWindow.get_hadjustment().set_value(left)

    def clearWatches(self):
        GLib.idle_add(self._do_clearWatches)

    def _do_clearWatches(self):
        builder = self._builder
        treestoreWatches = builder.get_object("treestoreWatches")
        treestoreWatches.clear()

    def addWatchRow(self, fullName=None, title=None, value=None, parentFullName=None):
        GLib.idle_add(self._do_addWatchRow, fullName, title, value, parentFullName)

    def _do_addWatchRow(self, fullName=None, title=None, value=None, parentFullName=None):
        parentIter = None
        if parentFullName != None:
            parentIter = self._watches[parentFullName]

        builder = self._builder
        treestoreWatches = builder.get_object("treestoreWatches")
        rowIter = treestoreWatches.append(parentIter)

        if fullName != None:
            self._watches[fullName] = rowIter
            treestoreWatches.set_value(rowIter, 0, title)
            treestoreWatches.set_value(rowIter, 1, value)
            treestoreWatches.set_value(rowIter, 2, fullName)

    def setWatchRowValue(self, fullName, value):
        GLib.idle_add(self._do_setWatchRowValue, fullName, value)

    def _do_setWatchRowValue(self, fullName, value):
        builder = self._builder
        treestoreWatches = builder.get_object("treestoreWatches")
        rowIter = self._watches[fullName]
        treestoreWatches.set_value(rowIter, 1, value)

    def expandWatchRow(self, fullName):
        GLib.idle_add(self._do_expandWatchRow, fullName)

    def _do_expandWatchRow(self, fullName):
        builder = self._builder
        treeviewWatches = builder.get_object("treeviewWatches")
        treestoreWatches = builder.get_object("treestoreWatches")
        rowIter = self._watches[fullName]
        rowPath = treestoreWatches.get_path(rowIter)
        treeviewWatches.expand_row(rowPath, False)
    
    def clearStack(self):
        GLib.idle_add(self._do_clearStack)

    def _do_clearStack(self):
        builder = self._builder
        liststoreStack = builder.get_object("liststoreStack")
        liststoreStack.clear()

    def addStackRow(self, filepath, line, where):
        GLib.idle_add(self._do_addStackRow, filepath, line, where)
        
    def _do_addStackRow(self, filepath, line, where):
        builder = self._builder
        liststoreStack = builder.get_object("liststoreStack")
        rowIter = liststoreStack.append()
        filename = filepath.split("/")[-1]
        liststoreStack.set_value(rowIter, 0, filepath)
        liststoreStack.set_value(rowIter, 1, line)
        liststoreStack.set_value(rowIter, 2, where)
        liststoreStack.set_value(rowIter, 3, filename)


    ### PATH MAPPING

    def onPathmappingAdd(self, button=None):
        builder = self._builder

        dialog = Gtk.Dialog("Add path-mapping", builder.get_object("windowPathmapping"))
        dialog.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        dialog.add_button(Gtk.STOCK_OK, Gtk.ResponseType.OK)
        dialogBox = dialog.get_content_area()

        labelLocal      = Gtk.Label()
        labelRemote     = Gtk.Label()
        userEntryLocal  = Gtk.Entry()
        userEntryRemote = Gtk.Entry()

        labelLocal .set_text("Absolute local path in workspace")
        labelRemote.set_text("Absolute remote path on server")

        grid = Gtk.Grid()
        grid.attach(labelLocal,      0, 0, 1, 1)
        grid.attach(labelRemote,     0, 1, 1, 1)
        grid.attach(userEntryLocal,  1, 0, 1, 1)
        grid.attach(userEntryRemote, 1, 1, 1, 1)

        dialogBox.pack_end(grid,  False, False, 0)

        dialog.show_all()
        response   = dialog.run()
        localPath  = userEntryLocal.get_text()
        remotePath = userEntryRemote.get_text()
        dialog.destroy()

        if response == Gtk.ResponseType.OK and localPath != '' and remotePath != '':
            self._path_mapping_manager.add_path_mapping(localPath, remotePath)

    def onPathmappingRemove(self, button=None):
        builder = self._builder
        treeviewPathmapping  = builder.get_object("treeviewPathmapping")
        liststorePathmapping = builder.get_object("liststorePathmapping")

        selection = treeviewPathmapping.get_selection()

        store, selected_rows = selection.get_selected_rows()

        for path in selected_rows:
            treeIter   = liststorePathmapping.get_iter(path)
            localPath  = liststorePathmapping.get_value(treeIter, 0)
            remotePath = liststorePathmapping.get_value(treeIter, 1)
            self._path_mapping_manager.remove_path_mapping(localPath, remotePath)



