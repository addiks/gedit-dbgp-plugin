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

import csv
import os
from gi.repository import Gtk, Gdk
from gladehandler import GladeHandler
from helpers import file_put_contents

class PathMappingManager:

    def __init__(self, plugin, profile_name):
        self._plugin = plugin
        self._glade_builder = None
        self._profile_name = profile_name
        self._mapped_paths = {}
        self.load()

    def mapLocalToRemote(self, localPathToMap):
        for localPath in self._mapped_paths:
            remotePath = self._mapped_paths[localPath]
            if localPathToMap.startswith(localPath):
                appendix = localPathToMap[len(localPath):]
                localPathToMap = remotePath + appendix
        return localPathToMap

    def mapRemoteToLocal(self, remotePathToMap):
        for localPath in self._mapped_paths:
            remotePath = self._mapped_paths[localPath]
            if remotePathToMap.startswith(remotePath):
                appendix = remotePathToMap[len(remotePath):]
                remotePathToMap = localPath + appendix
        return remotePathToMap

    def show(self):
        builder = self._getGladeBuilder()
        window = builder.get_object("windowPathmapping")
        window.show_all()

    def add_path_mapping(self, localPath, remotePath):
        self._mapped_paths[localPath] = remotePath
        self.save()

    def remove_path_mapping(self, localPath, remotePath):
        if localPath in self._mapped_paths:
            del self._mapped_paths[localPath]
        self.save()

    def load(self):
        builder = self._getGladeBuilder()
        treeviewPathmapping  = builder.get_object("treeviewPathmapping")
        liststorePathmapping = builder.get_object("liststorePathmapping")
        liststorePathmapping.clear()

        fileHandle = open(self.__get_container_file(), "r")
        reader = csv.reader(fileHandle, delimiter=",")
        for localPath, remotePath in reader:
            self._mapped_paths[localPath] = remotePath

            rowIter = liststorePathmapping.append()
            liststorePathmapping.set_value(rowIter, 0, localPath)
            liststorePathmapping.set_value(rowIter, 1, remotePath)
        fileHandle.close()
        
    def save(self):
        fileHandle = open(self.__get_container_file(), "w")
        writer = csv.writer(fileHandle, delimiter=",")
        for localPath in self._mapped_paths:
            remotePath = self._mapped_paths[localPath]
            writer.writerow([localPath, remotePath])
        fileHandle.close()
        self.load()

    def __get_container_file(self):
        filePath = self._plugin.get_data_dir() + "/path_mapping/" + self._profile_name + ".csv"
        if not os.path.exists(filePath):
            file_put_contents(filePath, "")
        return filePath

    def _getGladeBuilder(self):
        if self._glade_builder == None:
            self._glade_builder = Gtk.Builder()
            self._glade_handler = GladeHandler(self._plugin, self._glade_builder, path_mapping_manager=self)
            self._glade_builder.add_from_file(os.path.dirname(__file__)+"/debugger.glade")
            self._glade_builder.connect_signals(self._glade_handler)
        return self._glade_builder

