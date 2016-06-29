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
from gi.repository import Gtk, Gdk, GObject, Gedit, Gio, GtkSource, GdkPixbuf
from AddiksDBGP.helpers import *
from AddiksDBGP.AddiksDBGPApp import AddiksDBGPApp

class AddiksDBGPView(GObject.Object, Gedit.ViewActivatable):
    view = GObject.property(type=Gedit.View)

    def __init__(self):
        GObject.Object.__init__(self)
        self._gutter_renderer = None
        self._gutter_breakpoint_icons = {}
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

    def _get_breakpoint_icon(self, withCondition=False):
        fileName = "breakpoint.png"
        if withCondition:
            fileName = "breakpoint-condition.png"

        if fileName not in self._gutter_breakpoint_icons:
            iconPath = os.path.dirname(__file__) + "/../images/" + fileName
            gfile = Gio.File.new_for_path(iconPath)
            gicon = Gio.FileIcon.new(gfile)
            self._gutter_breakpoint_icons[fileName] = gicon
        return self._gutter_breakpoint_icons[fileName]

    def _get_empty_pixbuf(self):
        if self._gutter_empty_pixbuf == None:
            colorspace = GdkPixbuf.Colorspace.RGB
            self._gutter_empty_pixbuf = GdkPixbuf.Pixbuf.new(colorspace, True, 8, 16, 16)
            self._gutter_empty_pixbuf.fill(0x00000000)
        return self._gutter_empty_pixbuf

    def _on_breakpoint_gutter_query_activatable(self, renderer, textIter, area, event):
        if event.get_event_type() == Gdk.EventType.BUTTON_PRESS:
            isButton, button = event.get_button()
            document = self.view.get_buffer()
            if document.get_location() != None:
                gutter = self.view.get_gutter(Gtk.TextWindowType.LEFT)
                filePath = document.get_location().get_path()
                line = textIter.get_line()+1 

                if button == 3:
                    builder = AddiksDBGPApp.get().getGladeBuilder()
                    menuBreakpoints = builder.get_object("menuBreakpoints")
                    menuBreakpoints.popup(None, None, None, None, button, event.time)
                    menuBreakpoints.addiks_window = None
                    menuBreakpoints.addiks_filePath = filePath
                    menuBreakpoints.addiks_line = line
                    menuBreakpoints.addiks_gutter = gutter

                else:
                    AddiksDBGPApp.get().toggle_breakpoint(filePath, line)
                    gutter.queue_draw() # force redraw

                return True

    def _on_breakpoint_gutter_query_data(self, renderer, textIterStart, textIterEnd, state):
        document = self.view.get_buffer()
        if document.get_location() != None:
            filePath = document.get_location().get_path()
            line = textIterStart.get_line()+1
            if line in AddiksDBGPApp.get().get_breakpoints(filePath):
                hasCondition = AddiksDBGPApp.get().breakpoint_has_condition(filePath, line)
                renderer.set_gicon(self._get_breakpoint_icon(hasCondition))
            else:
                renderer.set_pixbuf(self._get_empty_pixbuf())

    def update_stack_marks(self, document=None, foo=None, bar=None):
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

