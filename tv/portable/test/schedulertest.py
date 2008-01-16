import unittest
from time import time, sleep
import threading

from miro import eventloop
from test.framework import EventLoopTest

class SchedulerTest(EventLoopTest):
    def setUp(self):
        self.gotArgs = []
        self.gotKwargs = []
        EventLoopTest.setUp(self)
    
    def callback(self, *args, **kwargs):
        self.gotArgs.append(args)
        self.gotKwargs.append(kwargs)
        if 'stop' in kwargs.keys():
            eventloop.quit()

    def testCallbacks(self):
        eventloop.addIdle(self.callback, "foo")
        eventloop.addTimeout(0.1, self.callback, "foo", args=("chris",), 
                kwargs={'hula':"hula"})
        eventloop.addTimeout(0.2, self.callback, "foo", args=("ben",), 
                kwargs={'hula':'moreHula', 'stop':1})
        self.runEventLoop()
        self.assertEquals(self.gotArgs[0], ())
        self.assertEquals(self.gotArgs[1], ("chris",))
        self.assertEquals(self.gotArgs[2], ("ben",))
        self.assertEquals(self.gotKwargs[0], {})
        self.assertEquals(self.gotKwargs[1], {'hula':'hula'})
        self.assertEquals(self.gotKwargs[2], {'hula':'moreHula', 'stop':1})

    def testQuitWithStuffStillScheduled(self):
        eventloop.addTimeout(0.1, self.callback, "foo", kwargs={'stop':1})
        eventloop.addTimeout(2, self.callback, "foo")
        self.runEventLoop()
        self.assertEquals(len(self.gotArgs), 1)

    def testTiming(self):
        startTime = time()
        eventloop.addTimeout(0.2, self.callback, "foo", kwargs={'stop':1})
        self.runEventLoop()
        endTime = time()
        self.assertAlmostEqual(startTime + 0.2, endTime, places=1)

    def testLotsOfThreads(self):
        timeouts = [0, 0, 0.1, 0.2, 0.3]
        threadCount = 8
        def thread():
            sleep(0.5)
            for timeout in timeouts:
                eventloop.addTimeout(timeout, self.callback, "foo")
        for i in range(threadCount):
            t = threading.Thread(target=thread)
            t.start()
        eventloop.addTimeout(1, self.callback, "foo", kwargs={'stop':1})
        self.runEventLoop()
        totalCalls = len(timeouts) * threadCount + 1
        self.assertEquals(len(self.gotArgs), totalCalls)
