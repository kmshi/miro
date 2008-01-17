# Miro - an RSS based video player application
# Copyright (C) 2005-2007 Participatory Culture Foundation
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

import os
from miro import prefs
import gconf
import threading
from miro.platform import resources

client = gconf.client_get_default()
gconf_lock = threading.RLock()

def _get_gconf(fullkey, default = None):
    gconf_lock.acquire()
    try:
        value = client.get (fullkey)
        if (value != None):
            if (value.type == gconf.VALUE_STRING):
                return value.get_string()
            if (value.type == gconf.VALUE_INT):
                return value.get_int()
            if (value.type == gconf.VALUE_BOOL):
                return value.get_bool()
            if (value.type == gconf.VALUE_FLOAT):
                return value.get_float()
        return default
    finally:
        gconf_lock.release()

class gconfDict:
    def get(self, key, default = None):
        if (type(key) != str):
            raise TypeError()
        fullkey = '/apps/miro/' + key
        return _get_gconf(fullkey, default)

    def __contains__(self, key):
        gconf_lock.acquire()
        try:
            fullkey = '/apps/miro/' + key
            return client.get(fullkey) is not None
        finally:
            gconf_lock.release()

    def __getitem__(self, key):
        rv = self.get(key)
        if rv is None:
            raise KeyError
        else:
            return rv

    def __setitem__(self, key, value):
        gconf_lock.acquire()
        try:
            if (type(key) != str):
                raise TypeError()
            fullkey = '/apps/miro/' + key
            if (type(value) == str):
                client.set_string(fullkey, value)
            elif (type(value) == int):
                client.set_int(fullkey, value)
            elif (type(value) == bool):
                client.set_bool(fullkey, value)
            elif (type(value) == float):
                client.set_float(fullkey, value)
            else:
                raise TypeError()
        finally:
            gconf_lock.release()

def load():
    return gconfDict()

def save(data):
    pass

def get(descriptor):
    value = descriptor.default

    if descriptor == prefs.MOVIES_DIRECTORY:
        value = os.path.expanduser('~/Movies/Miro')
        try:
            os.makedirs (value)
        except:
            pass
    elif descriptor == prefs.THEME_DIRECTORY:
        value = '/usr/share/miro/themes'

    elif descriptor == prefs.NON_VIDEO_DIRECTORY:
        value = os.path.expanduser('~/Desktop')

    elif descriptor == prefs.GETTEXT_PATHNAME:
        value = resources.path("../../locale")

    elif descriptor == prefs.SUPPORT_DIRECTORY:
        value = os.path.expanduser('~/.miro')

    elif descriptor == prefs.ICON_CACHE_DIRECTORY:
        value = os.path.expanduser('~/.miro/icon-cache')

    elif descriptor == prefs.DB_PATHNAME:
        value = get(prefs.SUPPORT_DIRECTORY)
        value = os.path.join(value, 'tvdump')

    elif descriptor == prefs.BSDDB_PATHNAME:
        value = get(prefs.SUPPORT_DIRECTORY)
        value = os.path.join(value, 'database')

    elif descriptor == prefs.SQLITE_PATHNAME:
        value = get(prefs.SUPPORT_DIRECTORY)
        value = os.path.join(value, 'sqlitedb')

    elif descriptor == prefs.LOG_PATHNAME:
        value = get(prefs.SUPPORT_DIRECTORY)
        value = os.path.join(value, 'miro-log')
    
    elif descriptor == prefs.DOWNLOADER_LOG_PATHNAME:
        value = get(prefs.SUPPORT_DIRECTORY)
        return os.path.join(value, 'miro-downloader-log')

    elif descriptor == prefs.HTTP_PROXY_ACTIVE:
        return _get_gconf ("/system/http_proxy/use_http_proxy")

    elif descriptor == prefs.HTTP_PROXY_HOST:
        return _get_gconf ("/system/http_proxy/host")

    elif descriptor == prefs.HTTP_PROXY_PORT:
        return _get_gconf ("/system/http_proxy/port")

    elif descriptor == prefs.HTTP_PROXY_AUTHORIZATION_ACTIVE:
        return _get_gconf ("/system/http_proxy/use_authentication")

    elif descriptor == prefs.HTTP_PROXY_AUTHORIZATION_USERNAME:
        return _get_gconf ("/system/http_proxy/authentication_user")

    elif descriptor == prefs.HTTP_PROXY_AUTHORIZATION_PASSWORD:
        return _get_gconf ("/system/http_proxy/authentication_password")

    elif descriptor == prefs.HTTP_PROXY_IGNORE_HOSTS:
        return _get_gconf ("/system/http_proxy/ignore_hosts", [])

    return value
