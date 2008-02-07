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

"""Contains the locations of special windows folders like "My Documents."""

import ctypes

_specialFolderCSIDLs = {
    'AppData': 0x001a,
    "My Music": 0x000d,
    "My Pictures": 0x0027,
    "My Videos": 0x000e,
    "My Documents": 0x0005,
    "Desktop": 0x0000,
    "Common AppData": 0x0023,
}

def getSpecialFolder(name):
    """Get the location of a special folder.  name should be one of the
    following: 'AppData', 'My Music', 'My Pictures', 'My Videos', 
    'My Documents', 'Desktop'.

    The path to the folder will be returned, or None if the lookup fails

    """

    buf = ctypes.create_unicode_buffer(260)
    buf2 = ctypes.create_unicode_buffer(1024) 
    SHGetSpecialFolderPath = ctypes.windll.shell32.SHGetSpecialFolderPathW
    GetShortPathName = ctypes.windll.kernel32.GetShortPathNameW
    csidl = _specialFolderCSIDLs[name]
    if SHGetSpecialFolderPath(None, buf, csidl, False):
        if GetShortPathName(buf, buf2, 1024):
            return buf2.value
        else:
            return buf.value
    else:
        return None

commonAppDataDirectory = getSpecialFolder("Common AppData")
appDataDirectory = getSpecialFolder('AppData')
baseMoviesDirectory = getSpecialFolder('My Videos')
nonVideoDirectory = getSpecialFolder('Desktop')
# The "My Videos" folder isn't guaranteed to be listed. If it isn't
# there, we do this hack.
if baseMoviesDirectory is None:
    baseMoviesDirectory = os.path.join(getSpecialFolder('My Documents'),'My Videos')


