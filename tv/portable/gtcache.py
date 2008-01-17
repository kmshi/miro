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

# Caching gettext functions

import gettext as _gt
import locale
from miro import config
from miro import prefs
from miro import platform
import os

_gtcache = None

def init():
    global _gtcache
    _gtcache = {}
    if not platform.utils.localeInitialized:
        raise Exception, "locale not initialized"
    locale.setlocale(locale.LC_ALL, '')

    _gt.bindtextdomain("miro", config.get(prefs.GETTEXT_PATHNAME))
    _gt.textdomain("miro")
    _gt.bind_textdomain_codeset("miro","UTF-8")

def gettext(text):
    text = text.encode('utf-8')
    try:
        return _gtcache[text]
    except KeyError:
        out = _gt.gettext(text).decode('utf-8')
        _gtcache[text] = out
        return out
    except TypeError:
        print "DTV: WARNING: gettext not initialized for string \"%s\"" % text
        import traceback
        traceback.print_stack()
        return text

def ngettext(text1, text2, count):
    text1 = text1.encode('utf-8')
    text2 = text2.encode('utf-8')
    try:
        return _gtcache[(text1,text2,count)]
    except:
        out = _gt.ngettext(text1, text2, count).decode('utf-8')
        _gtcache[(text1,text2,count)] = out
        return out
