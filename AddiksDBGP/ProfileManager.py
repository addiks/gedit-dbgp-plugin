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
from gi.repository import Gtk, Gdk
from _thread import start_new_thread
from AddiksDBGP.helpers import *
from AddiksDBGP.DebugSession import DebugSession
from AddiksDBGP.GladeHandler import GladeHandler
from AddiksDBGP.PathMappingManager import PathMappingManager

class ProfileManager:
    def __init__(self, plugin):
        self._plugin = plugin
        self._glade_builder = None
        self._glade_handler = None
        self._profile_name = "default"
        self._profile = self.get_profile_defaults()
        self._session = None
        self._path_mapping = {}

    def show(self):
        builder = self._getGladeBuilder()
        window = builder.get_object("windowProfiles")

        activeProfileName = self.get_active_profile()
        if activeProfileName not in self.get_profiles():
            self.store_profile(activeProfileName)
        self.load_profile(activeProfileName)

        self.__updateProfileList()
        
        self._glade_handler.updateDbgpVisibility()
        window.show()

    def __updateProfileList(self):
        builder = self._getGladeBuilder()
        profileList = builder.get_object("comboboxProfileList")
        profileListStore = profileList.get_model()
        if profileListStore != None:
            profileListStore.clear()
            activeIter = None
            activeProfileName = self.get_active_profile()
            for profileName in self.get_profiles():
                rowIter = profileListStore.append()
                profileListStore.set_value(rowIter, 0, profileName)
                if profileName == activeProfileName:
                    activeIter = rowIter
            if activeIter != None:
                profileList.set_active_iter(activeIter)


    def _getGladeBuilder(self):
        if self._glade_builder == None:
            self._glade_builder = Gtk.Builder()
            self._glade_handler = GladeHandler(self._plugin, self._glade_builder, profile_manager=self)
            self._glade_builder.add_from_file(os.path.dirname(__file__)+"/debugger.glade")
            self._glade_builder.connect_signals(self._glade_handler)
        return self._glade_builder

    def onStartDebugSession(self):
        profile = self.get_profile()
        self._plugin._runBrowser(profile['url'], profile['dbgp_ide_key'])

    def load_profile(self, name):
        self._profile = self.get_profile(name)
        self._profile_name = name
        
        builder = self._glade_builder
        builder.get_object("entryURL")          .set_text(  self._profile['url'])
        builder.get_object("entryDbgpHost")     .set_text(  self._profile['dbgp_host'])
        builder.get_object("entryDbgpIDEKey")   .set_text(  self._profile['dbgp_ide_key'])
        builder.get_object("spinbuttonPort")    .set_value( self._profile['port'])
        builder.get_object("spinbuttonDbgpPort").set_value( self._profile['dbgp_port'])
        builder.get_object("checkbuttonUseDbgp").set_active(self._profile['dbgp_active'])

    def get_profile_defaults(self):
        return {
            'url': 'http://example.com/',
            'port': 9000,
            'dbgp_active': True,
            'dbgp_host': 'localhost',
            'dbgp_port': 9001,
            'dbgp_ide_key': 'GEDIT'
        }

    def store_profile(self, name, profileData={}):
        options = self.get_profile_defaults()
        options.update(profileData)

        path = self.__get_profiles_path()
        filePath = path + "/" + name
        file_put_contents(filePath, repr(options))

    def get_profile(self, name=None):
        if name==None:
            name = self.get_active_profile()
        path = self.__get_profiles_path()
        filePath = path + "/" + name
        profileData = file_get_contents(filePath)
        profile = eval(profileData)
        return profile

    def create_profile(self, name=None):
        self.set_active_profile(name)
        self.store_profile(name)
        self.load_profile(name)
        self.__updateProfileList()

    def drop_profile(self, name=None):
        if name==None:
            name = self.get_active_profile()
        if len(self.get_profiles())>1:
            path = self.__get_profiles_path()
            filePath = path + "/" + name
            os.unlink(filePath)
            for profileName in self.get_profiles():
                self.set_active_profile(profileName)
                self.load_profile(profileName)
            self.__updateProfileList()
        else:
            pass

    def get_profiles(self):
        profiles = []
        path = self.__get_profiles_path()
        for subdir, dirs, files in os.walk(path):
            for fileName in files:
                profiles.append(fileName)
        return profiles

    def set_active_profile(self, profile_name):
        file_put_contents(self.__get_active_profile_filepath(), profile_name)
        
    def get_active_profile(self):
        file_path = self.__get_active_profile_filepath()
        if not os.path.exists(file_path):
            file_put_contents(file_path, "default")
        return file_get_contents(file_path)

    def get_pathmapping_manager(self, profile_name=None):
        if profile_name == None:
            profile_name = self.get_active_profile()
        if profile_name not in self._path_mapping:
            self._path_mapping[profile_name] = PathMappingManager(self._plugin, profile_name)
        return self._path_mapping[profile_name]

    def __get_active_profile_filepath(self):
        return self._plugin.get_data_dir() + "/active-debug-profile"

    def __get_profiles_path(self):
        return self._plugin.get_data_dir() + "/debug-profiles/"
    




