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
import threading
from miro import httpclient
from fasttypes import LinkedList
from miro.eventloop import asIdle, addIdle, addTimeout
from miro.download_utils import nextFreeFilename, getFileURLPath
from miro.util import unicodify, call_command
from miro.platformutils import unicodeToFilename
from miro import config
from miro import prefs
import time
import random
from miro import imageresize

RUNNING_MAX = 3
    
def clearOrphans():
    import views
    knownIcons = set()
    for item in views.items:
        if item.iconCache and item.iconCache.filename:
            knownIcons.add(os.path.normcase(item.iconCache.filename))
            for resized in item.iconCache.resized_filenames.values():
                knownIcons.add(os.path.normcase(resized))
    for feed in views.feeds:
        if feed.iconCache and feed.iconCache.filename:
            knownIcons.add(os.path.normcase(feed.iconCache.filename))
            for resized in feed.iconCache.resized_filenames.values():
                knownIcons.add(os.path.normcase(resized))
    cachedir = config.get(prefs.ICON_CACHE_DIRECTORY)
    if os.path.isdir(cachedir):
        existingFiles = [os.path.normcase(os.path.join(cachedir, f)) 
                for f in os.listdir(cachedir)]
        for filename in existingFiles:
            if (os.path.exists(filename) and
                os.path.basename(filename)[0] != '.' and
                os.path.basename(filename) != 'extracted' and
                not filename in knownIcons):
                try:
                    os.remove (filename)
                except OSError:
                    pass

class IconCacheUpdater:
    def __init__ (self):
        self.idle = LinkedList()
        self.vital = LinkedList()
        self.runningCount = 0
        self.inShutdown = False

    @asIdle
    def requestUpdate (self, item, is_vital = False):
        if is_vital:
            item.dbItem.confirmDBThread()
            if item.filename and os.access (item.filename, os.R_OK) \
                   and item.url == item.dbItem.getThumbnailURL():
                is_vital = False
        if self.runningCount < RUNNING_MAX:
            addIdle (item.requestIcon, "Icon Request")
            self.runningCount += 1
        else:
            if is_vital:
                self.vital.prepend(item)
            else:
                self.idle.prepend(item)

    def updateFinished (self):
        if self.inShutdown:
            self.runningCount -= 1
            return

        if len (self.vital) > 0:
            item = self.vital.pop()
        elif len (self.idle) > 0:
            item = self.idle.pop()
        else:
            self.runningCount -= 1
            return
        
        addIdle (item.requestIcon, "Icon Request")

    @asIdle
    def clearVital (self):
        self.vital = LinkedList()

    @asIdle
    def shutdown (self):
        self.inShutdown = True

iconCacheUpdater = IconCacheUpdater()
class IconCache:
    def __init__ (self, dbItem, is_vital = False):
        self.etag = None
        self.modified = None
        self.filename = None
        self.resized_filenames = {}
        self.url = None

        self.updated = False
        self.updating = False
        self.needsUpdate = False
        self.dbItem = dbItem
        self.removed = False

        self.requestUpdate (is_vital=is_vital)

    def iconChanged (self, needsSave=True):
        try:
            self.dbItem.iconChanged(needsSave=needsSave)
        except:
            self.dbItem.signalChange(needsSave=needsSave)

    def remove (self):
        self.removed = True
        self._removeFile(self.filename)
        imageresize.removeResizedFiles(self.resized_filenames)

    def reset (self):
        self._removeFile(self.filename)
        imageresize.removeResizedFiles(self.resized_filenames)
        self.filename = None
        self.resized_filenamed = {}
        self.url = None
        self.etag = None
        self.modified = None
        self.removed = False
        self.updated = False
        self.updating = False
        self.needsUpdate = False
        self.iconChanged()

    def _removeFile(self, filename):
        try:
            os.remove (filename)
        except:
            pass

    def errorCallback(self, url, error = None):
        self.dbItem.confirmDBThread()

        if self.removed:
            iconCacheUpdater.updateFinished()
            return

        # Don't clear the cache on an error.
        if self.url != url:
            self.url = url
            self.etag = None
            self.modified = None
            self.iconChanged()
        self.updating = False
        if self.needsUpdate:
            self.needsUpdate = False
            self.requestUpdate(True)
        elif error is not None:
            addTimeout(3600,self.requestUpdate, "Thumbnail request for %s" % url)
        else:
            self.updated = True
        iconCacheUpdater.updateFinished ()

    def updateIconCache (self, url, info):
        self.dbItem.confirmDBThread()

        if self.removed:
            iconCacheUpdater.updateFinished()
            return

        needsSave = False
        needsChange = False

        if info == None or (info['status'] != 304 and info['status'] != 200):
            self.errorCallback(url)
            return
        try:
            # Our cache is good.  Hooray!
            if (info['status'] == 304):
                self.updated = True
                return

            needsChange = True

            # We have to update it, and if we can't write to the file, we
            # should pick a new filename.
            if (self.filename and not os.access (self.filename, os.R_OK | os.W_OK)):
                self.filename = None
                seedsSave = True

            cachedir = config.get(prefs.ICON_CACHE_DIRECTORY)
            try:
                os.makedirs (cachedir)
            except:
                pass

            try:
                # Write to a temp file.
                if (self.filename):
                    tmp_filename = self.filename + ".part"
                else:
                    tmp_filename = os.path.join(cachedir, info["filename"]) + ".part"

                tmp_filename = nextFreeFilename (tmp_filename)
                output = file (tmp_filename, 'wb')
                output.write(info["body"])
                output.close()
            except IOError:
                self._removeFile(tmp_filename)
                return

            self._removeFile(self.filename)

            # Create a new filename always to avoid browser caching in case a file changes.
            # Add a random unique id
            parts = unicodify(info["filename"]).split('.')
            uid = u"%08d" % (random.randint(0,99999999),)
            if len(parts) == 1:
                parts.append(uid)
            else:
                parts[-1:-1] = [uid]
            self.filename = u'.'.join(parts)
            self.filename = unicodeToFilename(self.filename, cachedir)
            self.filename = os.path.join(cachedir, self.filename)
            self.filename = nextFreeFilename (self.filename)
            needsSave = True

            try:
                os.rename (tmp_filename, self.filename)
            except:
                self.filename = None
                needsSave = True
            else:
                self.resizeIcon()


            if (info.has_key ("etag")):
                etag = unicodify(info["etag"])
            else:
                etag = None

            if (info.has_key ("modified")):
                modified = unicodify(info["modified"])
            else:
                modified = None

            if self.etag != etag:
                needsSave = True
                self.etag = etag
            if self.modified != modified:
                needsSave = True
                self.modified = modified
            if self.url != url:
                needsSave = True
                self.url = url
            self.updated = True
        finally:
            if needsChange:
                self.iconChanged(needsSave=needsSave)
            self.updating = False
            if self.needsUpdate:
                self.needsUpdate = False
                self.requestUpdate(True)
            iconCacheUpdater.updateFinished ()

    def requestIcon (self):
        if self.removed:
            iconCacheUpdater.updateFinished()
            return

        self.dbItem.confirmDBThread()
        if (self.updating):
            self.needsUpdate = True
            iconCacheUpdater.updateFinished ()
            return
        try:
            url = self.dbItem.getThumbnailURL()
        except:
            url = self.url

        # Only verify each icon once per run unless the url changes
        if (self.updated and url == self.url):
            iconCacheUpdater.updateFinished ()
            return

        self.updating = True

        # No need to extract the icon again if we already have it.
        if url is None or url.startswith(u"/") or url.startswith(u"file://"):
            self.errorCallback(url)
            return

        # Last try, get the icon from HTTP.
        if (url == self.url and self.filename and os.access (self.filename, os.R_OK)):
            httpclient.grabURL (url, lambda info: self.updateIconCache(url, info), lambda error: self.errorCallback(url, error), etag=self.etag, modified=self.modified)
        else:
            httpclient.grabURL (url, lambda info: self.updateIconCache(url, info), lambda error: self.errorCallback(url, error))

    def requestUpdate (self, is_vital = False):
        if hasattr (self, "updating") and hasattr (self, "dbItem"):
            if self.removed:
                return

            iconCacheUpdater.requestUpdate (self, is_vital = is_vital)

    def onRestore(self):
        self.removed = False
        self.updated = False
        self.updating = False
        self.needsUpdate = False
        self.requestUpdate ()

    def isValid(self):
        self.dbItem.confirmDBThread()
        return self.filename and os.path.exists(self.filename)

    def getFilename(self):
        self.dbItem.confirmDBThread()
        if self.url and self.url.startswith (u"file://"):
            return getFileURLPath(self.url)
        elif self.url and self.url.startswith (u"/"):
            return self.url
        else:
            return self.filename

    def getResizedFilename(self, width, height):
        try:
            return imageresize.getImage(self.resized_filenames, width, height)
        except KeyError:
            return self.getFilename()

    def resizeIcon(self):
        imageresize.removeResizedFiles(self.resized_filenames)
        self.resized_filenames = imageresize.multiResizeImage(self.filename,
                self.dbItem.ICON_CACHE_SIZES)
