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

from miro import database
from miro import app
from miro import views
from miro import eventloop
from miro import feed
from miro import folder
from miro.platform import resources
from miro import guide
from miro import playlist
from miro import sorts
from miro.util import checkU, getSingletonDDBObject
from miro.databasehelper import TrackedIDList

from xml.dom.minidom import parse
from miro.gtcache import gettext as _
import logging

###############################################################################
#### Tabs                                                                  ####
###############################################################################


# Database object representing a static (non-feed-associated) tab.
class StaticTab(database.DDBObject):
    tabTitles = {
        'librarytab': _('Library'),
        'newtab': _('New'),
        'searchtab': _('Video Search'),
        'downloadtab': _('Downloading'),
    }

    tabIcons = {
        'librarytab': 'collection-icon-tablist.png',
        'newtab': 'newvideos-icon-tablist.png',
        'searchtab': 'search-icon-tablist.png',
        'downloadtab': 'download-icon-tab.png',
    }

    def __init__(self, tabTemplateBase, contentsTemplate, state, order):
        self.tabTemplateBase = tabTemplateBase
        self.contentsTemplate = contentsTemplate
        self.order = order
        self.templateState = state
        database.DDBObject.__init__(self)

    def getTitle(self):
        return self.tabTitles[self.tabTemplateBase]

    def getIconURL(self):
        return resources.url("images/%s" % self.tabIcons[self.tabTemplateBase])

    def getNumberColor(self):
        if self.tabTemplateBase == 'downloadtab':
            return 'orange'
        elif self.tabTemplateBase == 'newtab':
            return 'green'
        else:
            return None

    def getNumber(self):
        if self.tabTemplateBase == 'downloadtab':
            return views.downloadingItems.len()
        elif self.tabTemplateBase == 'newtab':
            return views.unwatchedItems.len()
        else:
            return 0

    def enableNewVideoPlayButton(self):
        return (self.tabTemplateBase == 'newtab' and 
                views.unwatchedItems.len() > 0)

class Tab:
    idCounter = 0

    def __init__(self, tabTemplateBase, contentsTemplate, templateState, obj):
        self.tabTemplateBase = tabTemplateBase
        self.contentsTemplate = contentsTemplate
        self.templateState = templateState
        self.display = None
        self.id = "tab%d" % Tab.idCounter
        Tab.idCounter += 1
        self.selected = False
        self.active = False
        self.obj = obj

        if obj.__class__ == guide.ChannelGuide:
            self.type = 'guide'
        elif obj.__class__ == StaticTab: 
            self.type = 'statictab'
        elif obj.__class__ in (feed.Feed, folder.ChannelFolder): 
            self.type = 'feed'
        elif obj.__class__ in (playlist.SavedPlaylist, folder.PlaylistFolder):
            self.type = 'playlist'
        else:
            raise TypeError("Bad tab object type: %s" % type(obj))

    def getDragSourceType(self):
        selection = app.controller.selection.tabListSelection
        if self.type == 'feed':
            if (isinstance(self.obj, folder.ChannelFolder) or
                    (self.selected and selection.isFolderSelected())):
                return 'channelfolder'
            else:
                return 'channel'
        elif self.type == 'playlist':
            if (isinstance(self.obj, folder.PlaylistFolder) or
                    (self.selected and selection.isFolderSelected())):
                return 'playlistfolder'
            else:
                return 'playlist'
        else:
            return ''

    def setActive(self, newValue):
        self.obj.confirmDBThread()
        self.active = newValue
        self.obj.signalChange(needsSave=False)

    def setSelected(self, newValue):
        self.obj.confirmDBThread()
        self.selected = newValue
        self.obj.signalChange(needsSave=False)

    def getSelected(self):
        self.obj.confirmDBThread()
        return self.selected

    def getActive(self):
        self.obj.confirmDBThread()
        return self.active

    # Returns "normal" "selected" or "selected-inactive"
    def getState(self):
        if not self.selected:
            return 'normal'
        elif not self.active:
            return 'selected-inactive'
        else:
            return 'selected'

    def redraw(self):
        # Force a redraw by sending a change notification on the underlying
        # DB object.
        self.obj.signalChange()

    def isStatic(self):
        """True if this Tab represents a StaticTab."""
        return isinstance(self.obj, StaticTab)

    def isFeed(self):
        """True if this Tab represents a Feed."""
        return isinstance(self.obj, feed.Feed)

    def isChannelFolder(self):
        """True if this Tab represents a Channel Folder."""
        return isinstance(self.obj, folder.ChannelFolder)

    def isGuide(self):
        """True if this Tab represents a Channel Guide."""
        return isinstance(self.obj, guide.ChannelGuide)

    def isPlaylist(self):
        """True if this Tab represents a Playlist."""
        return isinstance(self.obj, playlist.SavedPlaylist)

    def isPlaylistFolder(self):
        """True if this Tab represents a Playlist Folder."""
        return isinstance(self.obj, folder.PlaylistFolder)

    def feedURL(self):
        """If this Tab represents a Feed or a Guide, the URL. Otherwise None."""
        if self.isFeed() or self.isGuide():
            return self.obj.getURL()
        else:
            return None

    def objID(self):
        """If this Tab represents a Feed, the feed's ID. Otherwise None."""
        if isinstance (self.obj, database.DDBObject):
            return self.obj.getID()
        else:
            return None

    def getID(self):
        """Gets an id that can be used to lookup this tab from views.allTabs.

        NOTE: Tabs are mapped database objects, they don't have actual
        DDBObject ids.
        """
        return self.obj.getID()

    def signalChange(self, needsSave=True):
        """Call signalChange on the object that is mapped to this tab (the
        StaticTab, Feed, Playlist, etc.)
        """
        self.obj.signalChange(needsSave=needsSave)

    def idExists(self):
        """Returns True if the object that maps to this tab still exists in
        the DB.
        """

        return self.obj.idExists()

    def onDeselected(self, frame):
        self.display.onDeselect(frame)

    def getFragment(self):
        """URL fragment to use as an anchor.  This lets us scroll the tablist
        so that this tab is on top.
        """
        return 'tab-%d' % self.obj.getID()

def expandedFolderFilter(tab):
    folder = tab.obj.getFolder()
    return folder is None or folder.getExpanded()

class TabOrder(database.DDBObject):
    """TabOrder objects keep track of the order of the tabs.  Democracy
    creates 2 of these, one to track channels/channel folders and another to
    track playlists/playlist folders.
    """
    def __init__(self, type):
        """Construct a TabOrder.  type should be either "channel", or
        "playlist".
        """
        checkU(type)
        self.type = type
        self.tab_ids = []
        self._initRestore()
        decorated = [(t.obj.getTitle().lower(), t) for t in self.tabView]
        decorated.sort()
        for sortkey, tab in decorated:
            self.trackedTabs.appendID(tab.getID())
        database.DDBObject.__init__(self)

    def onRestore(self):
        self._initRestore()
        eventloop.addIdle(self.checkForNonExistentIds, 
                "checking for non-existent TabOrder ids")

    def _initRestore(self):
        if self.type == u'channel':
            self.tabView = views.feedTabs
        elif self.type == u'playlist':
            self.tabView = views.playlistTabs
        else:
            raise ValueError("Bad type for TabOrder")
        self.trackedTabs = TrackedIDList(self.tabView, self.tab_ids)
        self.trackedTabs.setFilter(expandedFolderFilter)
        self.tabView.addAddCallback(self.onAddTab)
        self.tabView.addRemoveCallback(self.onRemoveTab)

    def checkForNonExistentIds(self):
        changed = False
        for id in self.tab_ids[:]:
            if not self.tabView.idExists(id):
                self.trackedTabs.removeID(id)
                logging.warn("Throwing away non-existent TabOrder id: %s", id)
                changed = True
        if changed:
            self.signalChange()

    def makeLastTabVisible(self, obj):
        try:
            tabDisplay = app.controller.tabDisplay
        except AttributeError:
            # haven't created the tab display yet, just ignore this call
            return
        tabToShow = obj
        # try to go back a little to make the view prettier
        self.trackedTabs.view.moveCursorToID(obj.objID())
        for i in range(3):
            last = self.trackedTabs.view.getPrev()
            if last is None:
                break
            tabToShow = last
        if hasattr(tabDisplay, 'navigateToFragment'):
            tabDisplay.navigateToFragment(tabToShow.getFragment())
        else:
            logging.warn("HTMLDisplay.navigateToFragment not implemented")

    def getView(self):
        """Get a database view for this tab ordering."""
        return self.trackedTabs.view

    def getAllTabs(self):
        """Get all the tabs in this tab ordering (in order), regardless if
        they are visible in the tab list or not.
        """
        return [self.tabView.getObjectByID(id) for id in self.tab_ids \
                if self.tabView.idExists(id) ]

    def onAddTab(self, obj, id):
        if id not in self.trackedTabs:
            self.trackedTabs.appendID(id, sendSignalChange=False)
            obj.signalChange(needsSave=False)
            self.signalChange()
            self.makeLastTabVisible(obj)

    def onRemoveTab(self, obj, id):
        if id in self.trackedTabs:
            self.trackedTabs.removeID(id)
        self.signalChange()

    def handleDNDReorder(self, anchorItem, draggedIDs):
        """Handle drag-and-drop reordering of the tab order."""

        for iid in draggedIDs:
            if iid not in self.trackedTabs:
                raise ValueError("ID not in TabOrder: %s", iid)
        if anchorItem is None:
            newFolder = None
        else:
            newFolder = anchorItem.getFolder()

        childrenIDs = set()
        for id in draggedIDs:
            tab = self.trackedTabs.view.getObjectByID(id)
            tab.obj.setFolder(newFolder)
            if isinstance(tab.obj, folder.FolderBase):
                for child in tab.obj.getChildrenView():
                    childrenIDs.add(child.getID())
        toMove = draggedIDs.union(childrenIDs)
        self.moveTabs(anchorItem, toMove, sendSignalChange=False)
        self.signalChange()

    def moveTabs(self, anchorItem, toMove, sendSignalChange=True):
        if anchorItem is not None:
            self.trackedTabs.moveIDList(toMove, anchorItem.getID())
        else:
            self.trackedTabs.moveIDList(toMove, None)
        if sendSignalChange:
            self.signalChange()

# Remove all static tabs from the database
def removeStaticTabs():
    app.db.confirmDBThread()
    for obj in views.staticTabsObjects:
        obj.remove()

# Reload the StaticTabs in the database from the statictabs.xml resource file.
def reloadStaticTabs():
    app.db.confirmDBThread()
    # Wipe all of the StaticTabs currently in the database.
    removeStaticTabs()

    # Load them anew from the resource file.
    # NEEDS: maybe better error reporting?
    document = parse(resources.path('statictabs.xml'))
    for n in document.getElementsByTagName('statictab'):
        tabTemplateBase = n.getAttribute('tabtemplatebase')
        contentsTemplate = n.getAttribute('contentstemplate')
        state = n.getAttribute('state')
        order = int(n.getAttribute('order'))
        StaticTab(tabTemplateBase, contentsTemplate, state, order)

def tabIterator():
    """Iterates over all tabs in order"""
    for tab in views.guideTabs:
        yield tab
    for tab in views.staticTabs:
        yield tab
    for tab in getSingletonDDBObject(views.channelTabOrder).getView():
        yield tab
    for tab in getSingletonDDBObject(views.playlistTabOrder).getView():
        yield tab

def getViewForTab(tab):
    if tab.type == 'guide':
        return views.guideTabs
    elif tab.type == 'statictab':
        return views.staticTabs
    elif tab.type == 'feed':
        return getSingletonDDBObject(views.channelTabOrder).getView()
    elif tab.type == 'playlist':
        return getSingletonDDBObject(views.playlistTabOrder).getView()
    raise AssertionError("Unknown tab type")
