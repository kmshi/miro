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

from miro import app
import xine
import gtk
import traceback
import gobject
from miro import eventloop
from miro import config
from miro import prefs
import os
from miro.platform import options
from miro.platform import resources
from miro.download_utils import nextFreeFilename
from miro.platform.utils import confirmMainThread
from gtk_queue import gtkSyncMethod, gtkAsyncMethod

def waitForAttach(func):
    """Many xine calls can't be made until we attach the object to a X window.
    This decorator delays method calls until then.
    """
    def waitForAttachWrapper(self, *args):
        if self.attached:
            func(self, *args)
        else:
            self.attachQueue.append((func, args))
    return waitForAttachWrapper

class Renderer:
    def __init__(self):
        self.xine = xine.Xine()
        self.xine.setEosCallback(self.onEos)
        self.attachQueue = []
        self.attached = False

    def setWidget(self, widget):
        confirmMainThread()
        widget.connect_after("realize", self.onRealize)
        widget.connect("unrealize", self.onUnrealize)
        widget.connect("configure-event", self.onConfigureEvent)
        widget.connect("expose-event", self.onExposeEvent)
        self.widget = widget

    def onEos(self):
        eventloop.addIdle(app.controller.playbackController.onMovieFinished, "onEos: Skip to next track")

    def onRealize(self, widget):
        confirmMainThread()
        # flush gdk output to ensure that our window is created
        gtk.gdk.flush()
        displayName = gtk.gdk.display_get_default().get_name()
        xineDriver = options.defaultXineDriver
        if xineDriver is None:
            xineDriver = "xv"
        self.xine.attach(displayName, widget.window.xid, xineDriver, int(options.shouldSyncX), int(options.useXineHack))
        self.attached = True
        for func, args in self.attachQueue:
            try:
                func(self, *args)
            except Exception, e:
                print "Exception in attachQueue function"
                traceback.print_exc()
        self.attachQueue = []

    def onUnrealize(self, widget):
        confirmMainThread()
        self.xine.detach()
        self.attached = False

    def onConfigureEvent(self, widget, event):
        confirmMainThread()
        self.xine.setArea(event.x, event.y, event.width, event.height)

    def onExposeEvent(self, widget, event):
        confirmMainThread()
        self.xine.gotExposeEvent(event.area.x, event.area.y, event.area.width,
                event.area.height)

    @gtkSyncMethod
    def canPlayFile(self, filename):
        confirmMainThread()
        return self.xine.canPlayFile(filename)

    def goFullscreen(self):
        """Handle when the video window goes fullscreen."""
        confirmMainThread()
        # Sometimes xine doesn't seem to handle the expose events properly and
        # only thinks part of the window is exposed.  To work around this we
        # send it a couple of fake expose events for the entire window, after
        # a short time delay.

        def fullscreenExposeWorkaround():
            try:
                _, _, width, height, _ = self.widget.window.get_geometry()
                self.xine.gotExposeEvent(0, 0, width, height)
            except:
                return True
            return False

        gobject.timeout_add(500, fullscreenExposeWorkaround)
        gobject.timeout_add(1000, fullscreenExposeWorkaround)

    def exitFullscreen(self):
        """Handle when the video window exits fullscreen mode."""
        # nothing to do here
        confirmMainThread()

    @gtkAsyncMethod
    @waitForAttach
    def selectFile(self, filename):
        confirmMainThread()
        viz = config.get(prefs.XINE_VIZ);
        self.xine.setViz(viz);
        self.xine.selectFile(filename)
        def exposeWorkaround():
            try:
                _, _, width, height, _ = self.widget.window.get_geometry()
                self.xine.gotExposeEvent(0, 0, width, height)
            except:
                return True
            return False

        gobject.timeout_add(500, exposeWorkaround)

    def getProgress(self):
        confirmMainThread()
        try:
            pos, length = self.xine.getPositionAndLength()
        except:
            pass

    @gtkSyncMethod
    def getCurrentTime(self, callback):
        confirmMainThread()
        try:
            pos, length = self.xine.getPositionAndLength()
            callback(pos / 1000.0)
        except:
            callback(None)

    def setCurrentTime(self, seconds):
        confirmMainThread()
        self.seek(seconds)

    def playFromTime(self, seconds):
        confirmMainThread()
        self.seek (seconds)
        

    @waitForAttach
    def seek(self, seconds):
        confirmMainThread()
        self.xine.seek(int(seconds * 1000))

    def getDuration(self, callback):
        confirmMainThread()
        try:
            pos, length = self.xine.getPositionAndLength()
            callback(length / 1000)
        except:
            callback(None)

    # @waitForAttach  -- Not necessary because stop does this
    def reset(self):
        # confirmMainThread() -- Not necessary because stop does this
        self.stop()

    @gtkAsyncMethod
    @waitForAttach
    def setVolume(self, level):
        confirmMainThread()
        self.xine.setVolume(int(level * 100))

    @gtkAsyncMethod
    @waitForAttach
    def play(self):
        confirmMainThread()
        self.xine.play()

    @gtkAsyncMethod
    @waitForAttach
    def pause(self):
        confirmMainThread()
        self.xine.pause()

    #@waitForAttach -- Not necessary because stop does this
    def stop(self):
        # confirmMainThread() -- Not necessary since pause does this
        self.pause()

    @gtkSyncMethod
    def getRate(self):
        confirmMainThread()
        return self.xine.getRate()

    @gtkAsyncMethod
    @waitForAttach
    def setRate(self, rate):
        confirmMainThread()
        self.xine.setRate(rate)

    def movieDataProgramInfo(self, moviePath, thumbnailPath):
        return ((resources.path('../../../libexec/xine_extractor'), moviePath, thumbnailPath), None)
