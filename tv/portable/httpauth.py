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

from miro.download_utils import parseURL
from miro.frontends.html import dialogs
from miro import eventloop

def formatAuthString(auth):
    return "%s %s" % (auth.getAuthScheme(), auth.getAuthToken())

def findHTTPAuth(callback, host, path):
    """Find an HTTPAuthPassword object stored in the database.  Callback will
    be called with a string to use for the Authorization header or None if we
    can't find anything in the DB.
    """
    from miro import downloader

    auth = downloader.findHTTPAuth(host, path)
    if auth is not None:
        auth = formatAuthString(auth)
    eventloop.addIdle(callback, "http auth callback", args=(auth,))

def askForHTTPAuth(callback, url, realm, authScheme):
    """Ask the user for a username and password to login to a site.  Callback
    will be called with a string to use for the Authorization header or None
    if the user clicks cancel.
    """

    scheme, host, port, path = parseURL(url)
    def handleLoginResponse(dialog):
        from miro import downloader
        if dialog.choice == dialogs.BUTTON_OK:
            auth = downloader.HTTPAuthPassword(dialog.username,
                    dialog.password, host, realm, path, authScheme)
            callback(formatAuthString(auth))
        else:
            callback(None)
    dialogs.HTTPAuthDialog(url, realm).run(handleLoginResponse)
