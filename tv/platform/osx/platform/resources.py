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

import urllib
from miro.platform import bundle

# Find the full path to a resource data file. 'relative_path' is
# expected to be supplied in Unix format, with forward-slashes as
# separators. The output, though, uses the native platform separator.
def path(relative_path):
    rsrcpath = os.path.join(bundle.getBundleResourcePath(), u'resources', relative_path)
    return os.path.abspath(rsrcpath)

# As path(), but return a file: URL instead.
def url(relative_path):
    return u"file://" + urllib.quote(path(relative_path))

def absoluteUrl(absolute_path):
    """Like url, but without adding the resource directory.
    """
    return u"file://" + urllib.quote(absolute_path)

def theme_path(theme, relative_path):
    return os.path.join(bundle.getBundlePath(), "Contents", "Theme", theme,
            relative_path)
