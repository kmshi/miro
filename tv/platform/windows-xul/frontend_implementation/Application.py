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

import sys
from miro import app
import time
from miro import config
from miro import prefs
from miro.platform import resources
import os
from miro import searchengines
from miro import views
from miro.platform.utils import _getLocale as getLocale
from miro.frontends.html.main import HTMLApplication
from miro.platform.frontends.html import HTMLDisplay
from miro.platform import migrateappname

###############################################################################
#### Application object                                                    ####
###############################################################################
class Application(HTMLApplication):
    def Run(self):
        HTMLDisplay.initTempDir()

        lang = getLocale()
        if lang:
            if not os.path.exists(resources.path(r"..\chrome\locale\%s" % (lang,))):
                lang = "en-US"
        else:
            lang = "en-US"

        from xpcom import components
        ps_cls = components.classes["@mozilla.org/preferences-service;1"]
        ps = ps_cls.getService(components.interfaces.nsIPrefService)
        branch = ps.getBranch("general.useragent.")
        branch.setCharPref("locale", lang)

        import psyco
        #psyco.log('\\dtv.psyco')
        psyco.profile(.03)

        app.jsBridge.positionVolumeSlider(config.get(prefs.VOLUME_LEVEL))

        self.startup()

    def quitUI(self):
        app.jsBridge.closeWindow()

    def finishStartupSequence(self):
        from xpcom import components
        pybridge = components.classes["@participatoryculture.org/dtv/pybridge;1"].getService(components.interfaces.pcfIDTVPyBridge)
        self.initializeSearchEngines()
        migrateappname.migrateVideos('Democracy', 'Miro')
        pybridge.updateTrayMenus()

    def initializeSearchEngines(self):
        names = []
        titles = []
        for engine in views.searchEngines:
            names.append(engine.name)
            titles.append(engine.title)
        app.jsBridge.setSearchEngineInfo(names, titles)
        app.jsBridge.setSearchEngine(searchengines.getLastEngine())

    def onShutdown(self):
        # For overriding
        pass

    # This is called on OS X when we are handling a click on an RSS feed
    # button for Safari. NEEDS: add code here to register as a RSS feed
    # reader on Windows too. Just call this function when we're launched
    # to handle a click on a feed.
    def addAndSelectFeed(self, url):
        # For overriding
        pass

    def onUnwatchedItemsCountChange(self, obj, id):
        from xpcom import components

        HTMLApplication.onDownloadingItemsCountChange(self, obj, id)
        pybridge = components.classes["@participatoryculture.org/dtv/pybridge;1"].getService(components.interfaces.pcfIDTVPyBridge)
        pybridge.updateTrayMenus()

    def onDownloadingItemsCountChange(self, obj, id):
        from xpcom import components

        HTMLApplication.onDownloadingItemsCountChange(self, obj, id)
        pybridge = components.classes["@participatoryculture.org/dtv/pybridge;1"].getService(components.interfaces.pcfIDTVPyBridge)
        pybridge.updateTrayMenus()

###############################################################################
###############################################################################
