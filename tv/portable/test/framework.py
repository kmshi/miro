import unittest
import threading

from miro import database
from miro import eventloop
from miro import frontend
from miro import app
from miro import downloader
from miro import views
from miro import util
from miro import databaseupgrade
from miro import signals
from miro import storedatabase
from miro import subscription
from miro import selection
from time import sleep

util.setupLogging()

# Generally, all test cases should extend DemocracyTestCase or
# EventLoopTest.  DemocracyTestCase cleans up any database changes you
# might have made, and EventLoopTest provides an API for accessing the
# eventloop in addition to managing the thread pool and cleaning up
# any events you may have scheduled.
# 
# Our general strategy here is to "revirginize" the environment after
# each test, rather than trying to reset applicable pieces of the
# environment before each test. This way, when writing new tests you
# don't have to anticipate what another test may have changed, you
# just have to make sure you clean up what you changed. Usually, that
# is handled transparently through one of these test cases

class HadToStopEventLoop(Exception):
    pass

class DummyMainFrame:
    def __init__(self):
        self.displays = {}
        self.mainDisplay = "mainDisplay"
        self.channelsDisplay = "channelsDisplay"
        self.collectionDisplay = "collectionDisplay"
        self.videoInfoDisplay = "videoInfoDisplay"

    def selectDisplay(self, display, area):
        self.displays[area] = display

    def getDisplay(self, area):
        return self.displays.get(area)

    def onSelectedTabChange(self, tabType, multiple, guideURL, videoFilename):
        pass

class DummyVideoDisplay:
    def fileDuration (self, filename, callback):
        pass

    def fillMovieData (self, filename, movie_data, callback):
        pass

class DummyController:
    def __init__(self):
        self.selection = selection.SelectionHandler()
        self.frame = DummyMainFrame()
        self.videoDisplay = DummyVideoDisplay()

class DemocracyTestCase(unittest.TestCase):
    def setUp(self):
        app.db = database.defaultDatabase
        database.set_thread(threading.currentThread())
        views.initialize()
        # reset the event loop
        util.chatter = False
        self.sawError = False
        self.errorSignalOkay = False
        signals.system.connect('error', self.handle_error)
        app.controller = DummyController()

    def tearDown(self):
        try:
            signals.system.disconnect('error', self.handle_error)
        except KeyError:
            raise AssertionError("Exception disconnecting the error callback."
                    "  Did you forget to call DemocracyTestCase.setUp()?")
        util.chatter = True

        # Remove any leftover database
        database.resetDefaultDatabase()

        # Remove anything that may have been accidentally queued up
        eventloop._eventLoop = eventloop.EventLoop()

    def handle_error(self, obj, report):
        if self.errorSignalOkay:
            self.sawError = True
        else:
            raise Exception("error signal")

class EventLoopTest(DemocracyTestCase):
    def setUp(self):
        DemocracyTestCase.setUp(self)
        self.hadToStopEventLoop = False

    def stopEventLoop(self, abnormal = True):
        self.hadToStopEventLoop = abnormal
        eventloop.quit()

    def runPendingIdles(self):
        idleQueue = eventloop._eventLoop.idleQueue
        urgentQueue = eventloop._eventLoop.urgentQueue
        while idleQueue.hasPendingIdle() or urgentQueue.hasPendingIdle():
            urgentQueue.processIdles()
            idleQueue.processNextIdle()

    def runEventLoop(self, timeout=10, timeoutNormal=False):
        eventloop.threadPoolInit()
        try:
            self.hadToStopEventLoop = False
            timeout = eventloop.addTimeout(timeout, self.stopEventLoop, 
                                           "Stop test event loop")
            eventloop._eventLoop.quitFlag = False
            eventloop._eventLoop.loop()
            if self.hadToStopEventLoop and not timeoutNormal:
                raise HadToStopEventLoop()
            else:
                timeout.cancel()
        finally:
            eventloop.threadPoolQuit()

    def addTimeout(self,delay, function, name, args=None, kwargs=None):
        eventloop.addTimeout(delay, function, name, args, kwargs)

    def addWriteCallback(self, socket, callback):
        eventloop.addWriteCallback(socket, callback)

    def removeWriteCallback(self, socket):
        eventloop.removeWriteCallback(socket)

    def addIdle(self, function, name, args=None, kwargs=None):
        eventloop.addIdle(function, name, args=None, kwargs=None)

    def hasIdles(self):
        return not (eventloop._eventLoop.idleQueue.queue.empty() and
                    eventloop._eventLoop.urgentQueue.queue.empty())

    def processThreads(self):
        eventloop._eventLoop.threadPool.initThreads()
        while not eventloop._eventLoop.threadPool.queue.empty():
            sleep(0.05)
        eventloop._eventLoop.threadPool.closeThreads()

    def processIdles(self):
        eventloop._eventLoop.idleQueue.processIdles()
        eventloop._eventLoop.urgentQueue.processIdles()

class DownloaderTestCase(EventLoopTest):
    def setUp(self):
        EventLoopTest.setUp(self)
        downloader.startupDownloader()

    def tearDown(self):
        downloader.shutdownDownloader(eventloop.quit)
        self.runEventLoop()
        EventLoopTest.tearDown(self)
