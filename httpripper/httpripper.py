"""
Author: Jonas Wagner
Version: 0.1
Last Change: 2008-06-23

HTTPRipper a generic ripper for the web
Copyright (C) 2008 Jonas Wagner

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import datetime
import shutil
import threading
import SocketServer
import socket
import tempfile
import os
import time
from os import path
import sys

import logging

import locale
locale.setlocale(locale.LC_ALL, 'en_US.utf8')

import gtk, gobject

from x29a import mygtk
from x29a.utils import byteformat
mygtk.register_webbrowser_url_hook()

import prox as proxpy

NAME = "HTTPRipper"
VERSION = "0.1"
WEBSITE = "http://29a.ch/httpripper/"

def _(s):
    return s

def byteformatdatafunc(column, cell, model, treeiter):
    n = int(cell.get_property('text'))
    cell.set_property('text', byteformat(n))

class MainWindow(gtk.Window):
    def __init__(self):
        gtk.Window.__init__(self)
        self.port = 8080
        while True:
            try:
                self.server = HTTPProxyServer(self)
                break
            except socket.error:
                self.port += 1
        self.server.start()
        self.set_title(NAME)
        self.set_icon(mygtk.iconfactory.get_icon("httpripper", 32))
        self.set_default_size(600, 600)
        self.vbox = gtk.VBox()
        self.add(self.vbox)
        self.info = gtk.Label(
                _("HTTPRipper is running on localhost: %i") % self.port)
        self.vbox.pack_start(self.info, False, False)
        self.model = mygtk.ListStore(date=str, url=str, size=int, path=str,
                icon=str)
        self.treeview = gtk.TreeView(self.model)
        self.treeview.set_rules_hint(True)
        #self.treeview.set_fixed_height_mode(True) # makes it a bit faster
        self.treeview.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self.treeview.connect("row-activated", self.save_file)
        self.treeview.set_search_column(self.model.columns.url)
        col = self.treeview.insert_column_with_attributes(0, _("Time"),
                gtk.CellRendererText(), text=self.model.columns.date)
        col.set_sort_column_id(self.model.columns.date)
        col = self.treeview.insert_column_with_attributes(1, _("Size"),
                gtk.CellRendererText(), text=self.model.columns.size)
        col.set_cell_data_func(col.get_cell_renderers()[0], byteformatdatafunc)
        col.set_sort_column_id(self.model.columns.size)
        col = self.treeview.insert_column_with_attributes(2, _("URL"),
                gtk.CellRendererText(), text=self.model.columns.url)
        col.set_expand(True)
        col.set_sort_column_id(self.model.columns.url)
        col = self.treeview.insert_column_with_attributes(0, "",
                gtk.CellRendererPixbuf(),
                **({"icon_name": self.model.columns.icon}))
        self.vbox.pack_start(mygtk.scrolled(self.treeview))

        self.buttonbox = gtk.HButtonBox()
        self.vbox.pack_end(self.buttonbox, False, False)

        self.button_record = gtk.ToggleButton(gtk.STOCK_MEDIA_RECORD)
        self.button_record.set_use_stock(True)
        self.button_record.connect("clicked", self.record)
        self.buttonbox.pack_start(self.button_record)

        self.button_save = gtk.Button(stock=gtk.STOCK_SAVE_AS)
        self.button_save.connect("clicked", self.save)
        self.buttonbox.pack_start(self.button_save)

        self.button_clear = gtk.Button(stock=gtk.STOCK_CLEAR)
        self.button_clear.connect("clicked", self.clear)
        self.buttonbox.pack_start(self.button_clear)

        self.button_about = gtk.Button(stock=gtk.STOCK_ABOUT)
        self.button_about.connect("clicked", self.about)
        self.buttonbox.pack_start(self.button_about)

        self.connect("destroy", self.clear)
        self.connect("destroy", lambda *args: self.server.shutdown())
        self.connect("destroy", gtk.main_quit)

    def save(self, sender):
        model, rows = self.treeview.get_selection().get_selected_rows()
        if len(rows) == 1:
            self.save_file(self.treeview, rows[0], None)
        elif len(rows) > 1:
            self.save_files(rows)

    def save_files(self, rows):
        dialog = gtk.FileChooserDialog(
                title="Save As",
                parent=self,
                action=gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
                buttons=(
                    "Cancel", gtk.RESPONSE_CANCEL,
                    "Save", gtk.RESPONSE_OK
                )
        )
        if dialog.run() == gtk.RESPONSE_OK:
            for row in map(self.model.get_iter, rows):
                filepath = self.model.get_value(row, self.model.columns.path)
                url = self.model.get_value(row, self.model.columns.url)
                name = path.basename(url).split("?")[0]
                shutil.copy(filepath, path.join(dialog.get_filename(), name))
        dialog.destroy()

    def save_file(self, treeview, treepath, view_column):
        row = self.model.get_iter(treepath)
        filepath = self.model.get_value(row, self.model.columns.path)
        url = self.model.get_value(row, self.model.columns.url)
        # might break on windows?
        name = path.basename(url).split("?")[0]
        dialog = gtk.FileChooserDialog(
                title="Save As",
                parent=self,
                action=gtk.FILE_CHOOSER_ACTION_SAVE,
                buttons=(
                    "Cancel", gtk.RESPONSE_CANCEL,
                    "Save", gtk.RESPONSE_OK
                )
        )
        dialog.set_current_name(name)
        if dialog.run() == gtk.RESPONSE_OK:
            shutil.copy(filepath, dialog.get_filename())
        dialog.destroy()

    def new_file(self, url, filepath):
        self.model.append(
                date=datetime.datetime.now().time().strftime("%H:%M:%S"),
                url=url,
                size=path.getsize(filepath),
                icon="gtk-save",
                path=filepath
        )

    def clear(self, sender):
        for row in self.model:
            filepath = row[self.model.columns.path]
            os.remove(filepath)
        self.model.clear()
        self.treeview.columns_autosize()

    def record(self, sender):
        self.server.record = not self.server.record

    def about(self, sender):
        about = gtk.AboutDialog()
        about.set_transient_for(self)
        about.set_logo(mygtk.iconfactory.get_icon("httpripper", 128))
        about.set_name(NAME)
        about.set_version(VERSION)
#        about.set_comments("")
        about.set_authors(["Jonas Wagner"])
        about.set_copyright("Copyright (c) 2008 Jonas Wagner")
        about.set_website(WEBSITE)
        about.set_website_label(WEBSITE)
        about.set_license("""
Copyright (C) 2008 Jonas Wagner
This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
""")
        about.run()
        about.destroy()

class Tee(object):
    def __init__(self, f1, f2):
        self.f1 = f1
        self.f2 = f2

    def write(self, data):
        self.f1.write(data)
        self.f2.write(data)

class HTTPProxyHandler(proxpy.HTTPProxyHandler):
    def forward_response_body(self, f1, f2, contentlength):
        if self.server.record:
            fd, name = tempfile.mkstemp(dir=self.server.tempdir)
            f3 = os.fdopen(fd, "w+b", 0)
            f2 = Tee(f2, f3)
        self.forward(f1, f2, contentlength)
        if self.server.record:
            self.server.on_new_file(self.url, name)

class HTTPProxyServer(proxpy.HTTPProxyServer, threading.Thread):

    def __init__(self, mainwin):
        self.tempdir = tempfile.mkdtemp(prefix="proxpy")
        self.record = False
        threading.Thread.__init__(self)
        self.setDaemon(True)
        self.mainwin = mainwin
        SocketServer.TCPServer.__init__(self, ("127.0.0.1", mainwin.port),
                HTTPProxyHandler)

    def run(self):
        self.serve_forever()

    def shutdown(self):
        shutil.rmtree(self.tempdir)
        SocketServer.shutdown(self)

    def on_new_file(self, url, filepath):
        gobject.idle_add(self.mainwin.new_file, url, filepath)

def main():
    logging.basicConfig(level=logging.DEBUG)
    if sys.platform == "win32":
        def release_gil_on_stupid_operating_system():
            """fix for a stupid problem with threads and gtk on windows!"""
            time.sleep(0.001)
            return True
        gobject.timeout_add(25, release_gil_on_stupid_operating_system)
    else:
        gtk.gdk.threads_init()
    win = MainWindow()
    win.show_all()
    gtk.main()

if __name__ == "__main__":

    main()
