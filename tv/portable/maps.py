# Miro - an RSS based video player application
# Copyright (C) 2005-2008 Participatory Culture Foundation
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

from miro import tabs
from miro import feed
from miro import folder
from miro import playlist
from miro import guide

# Given an object for which mappableToTab returns true, return a Tab
def mapToTab(obj):
    if isinstance(obj, guide.ChannelGuide):
        # Guides come first and default guide comes before the others.  The rest are currently sorted by URL.
        return tabs.Tab('guidetab', 'guide-loading', 'default', obj)
    elif isinstance(obj, tabs.StaticTab):
        return tabs.Tab(obj.tabTemplateBase, obj.contentsTemplate, obj.templateState, obj)
    elif isinstance(obj, feed.Feed):
        return tabs.Tab('feedtab', 'channel',  'default', obj)
    elif isinstance(obj, folder.ChannelFolder):
        return tabs.Tab('channelfoldertab', 'channel-folder', 'default', obj)
    elif isinstance(obj, folder.PlaylistFolder):
        return tabs.Tab('playlistfoldertab','playlist-folder', 'default', obj)
    elif isinstance(obj, playlist.SavedPlaylist):
        return tabs.Tab('playlisttab','playlist', 'default', obj)
    else:
        raise StandardError
    
