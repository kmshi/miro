# Miro - an RSS based video player application
# Copyright (C) 2010, 2011
# Participatory Culture Foundation
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
#
# In addition, as a special exception, the copyright holders give
# permission to link the code of portions of this program with the OpenSSL
# library.
#
# You must obey the GNU General Public License in all respects for all of
# the code used other than OpenSSL. If you modify file(s) with this
# exception, you may extend this exception to your version of the file(s),
# but you are not obligated to do so. If you do not wish to do so, delete
# this exception statement from your version. If you delete this exception
# statement from all source files in the program, then also delete it here.

import logging
import dbus

from miro import app


class MediaKeyHandler(object):
    def __init__(self, app_window):
        self.bus = dbus.Bus(dbus.Bus.TYPE_SESSION)
        self.bus_object = self.bus.get_object(
            'org.gnome.SettingsDaemon', '/org/gnome/SettingsDaemon/MediaKeys')

        self.bus_object.GrabMediaPlayerKeys(
            "Miro", 0, dbus_interface='org.gnome.SettingsDaemon.MediaKeys')

        self.bus_object.connect_to_signal(
            'MediaPlayerKeyPressed', self.handle_mediakey)

        app_window.connect("active-change", self.on_window_focus)

    def handle_mediakey(self, application, *mmkeys):
        if application != 'Miro':
            return
        for key in mmkeys:
            if key == "Play":
                app.widgetapp.on_play_clicked()
            elif key == "Stop":
                app.widgetapp.on_stop_clicked()
            elif key == "Next":
                app.widgetapp.on_forward_clicked()
            elif key == "Previous":
                app.widgetapp.on_previous_clicked()

    def on_window_focus(self, window):
        self.bus_object.GrabMediaPlayerKeys(
            "Miro", 0, dbus_interface='org.gnome.SettingsDaemon.MediaKeys')
        return False


def get_media_key_handler(app_window):
    try:
        return MediaKeyHandler(app_window)
    except dbus.DBusException:
        logging.debug("cannot load MediaKeyHandler")
