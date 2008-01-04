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

import app
import os
import util
import config
import prefs
from download_utils import nextFreeFilename
from frontends.html.displaybase import VideoDisplayBase
from playbackcontroller import PlaybackControllerBase
from videorenderer import VideoRenderer

from xpcom import components
from threading import Lock
import time

selectItemLock = Lock()

###############################################################################
#### The Playback Controller                                               ####
###############################################################################

class PlaybackController (PlaybackControllerBase):
    
    def playItemExternally(self, itemID):
        item = PlaybackControllerBase.playItemExternally(self, itemID)
        # now play this item externally
        moviePath = ""
        try:
            moviePath = os.path.normpath(item.getVideoFilename())
            os.startfile(moviePath)
        except:
            print "DTV: movie %s could not be externally opened" % moviePath

###############################################################################
#### Right-hand pane video display                                         ####
###############################################################################

class VideoDisplay (VideoDisplayBase):
    "Video player shown in a MainFrame's right-hand pane."

    def initRenderers(self):
        self.renderers.append(VLCRenderer())

    def setArea(self, area):
        # we hardcode the videodisplay's area to be mainDisplayVideo
        pass
    def removedFromArea(self):
        # don't care about this either
        pass

    def goFullScreen(self):
        return app.vlcRenderer.goFullscreen(url)

    def exitFullScreen(self):
        return app.vlcRenderer.exitFullScreen(url)

    def setVolume(self, volume, moveSlider=True): 
        VideoDisplayBase.setVolume(self, volume)
        app.vlcRenderer.setVolume(self.volume)
        if moveSlider:
            app.jsBridge.positionVolumeSlider(self.volume)

    def fillMovieData (self, filename, movie_data, callback):
        print "fillMovieData (%s)" % (filename,)
#        dir = os.path.join (config.get(prefs.ICON_CACHE_DIRECTORY), "extracted")
#        try:
#            os.makedirs(dir)
#        except:
#            pass
#        screenshot = os.path.join (dir, os.path.basename(filename) + ".png")

#        movie_data["screenshot"] = nextFreeFilename(screenshot)
        movie_data["screenshot"] = u""

        self.movie_data = movie_data
        self.callback = callback

#       Uncomment this to enable duration extraction

#         print "Calling renderer"
        app.vlcRenderer.extractMovieData (filename, movie_data["screenshot"]);
#         print "renderer returned"

    def extractFinish (self, duration, screenshot_success):
        print "extractFinish (%d, %s)" % (duration, screenshot_success)
        self.movie_data["duration"] = int (duration)
        if screenshot_success:
            self.movie_data["screenshot"] = u""
#            if self.movie_data["screenshot"] and not os.path.exists(self.movie_data["screenshot"]):
#                self.movie_data["screenshot"] = u""
        else:
            self.movie_data["screenshot"] = None
        self.callback()

# This is a major hack to avoid VLC crashes by giving it time to
# process each stop or play command. --NN
def lockAndPlay(func):
    def locked(*args, **kwargs):
        global selectItemLock
        selectItemLock.acquire()
        try:
            ret = func(*args, **kwargs)
            time.sleep(1)
            return ret
        finally:
            selectItemLock.release()
    return locked

class VLCRenderer (VideoRenderer):
    """The VLC renderer is very thin wrapper around the xine-renderer xpcom
    component. 
    """

    def canPlayFile(self, filename):
        url = util.absolutePathToFileURL(filename)
        return app.vlcRenderer.canPlayURL(url)

    @lockAndPlay
    def selectFile(self, filename):
        url = util.absolutePathToFileURL(filename)
        return app.vlcRenderer.selectURL(url)
    def setVolume(self, volume): 
        return app.vlcRenderer.setVolume(volume)
    @lockAndPlay
    def reset(self): 
        return app.vlcRenderer.reset()
    @lockAndPlay
    def play(self): 
        return app.vlcRenderer.play()
    def pause(self): 
        return app.vlcRenderer.pause()
    @lockAndPlay
    def stop(self): 
        return app.vlcRenderer.stop()
    def goToBeginningOfMovie(self): 
        return app.vlcRenderer.goToBeginningOfMovie()
    def getDuration(self): 
        return app.vlcRenderer.getDuration()
    def getCurrentTime(self): 
        try:
            return app.vlcRenderer.getCurrentTime()
        except:
            return None
    def setCurrentTime(self, time): 
        return app.vlcRenderer.setCurrentTime(time)
    @lockAndPlay
    def playFromTime(self, time): 
        return app.vlcRenderer.playFromTime(time)
    def getRate(self): 
        return app.vlcRenderer.getRate()
    def setRate(self, rate): 
        return app.vlcRenderer.setRate(rate)

    def movieDataProgramInfo(self, videoPath, thumbnailPath):
        # We don't use the app name here, so custom
        # named versions can use the same code --NN
        moviedata_util_filename = "Miro_MovieData.exe"
        cmdLine = [moviedata_util_filename, videoPath, thumbnailPath]
        return cmdLine, None


###############################################################################
###############################################################################
