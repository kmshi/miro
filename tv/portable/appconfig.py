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

"""miro.appconfig -- Contains the AppConfig class, which handles holding
the values of app.config.  If Miro is using a theme, then the theme's
app.config value overrides the default one.

Most uses of AppConfig will come from the global variable app.configfile.
This is setup in config.load().
"""

import logging

from miro import app
from miro import util
from miro.platform import resources

class AppConfig(object):
    def __init__(self, theme=None):
        app_config_path = resources.path('app.config')
        self.default_vars = util.readSimpleConfigFile(app_config_path)
        self.load_theme(theme)

    def load_theme(self, theme):
        if theme is not None:
            logging.info("Using theme %s" % theme)
            theme_app_config = resources.theme_path(theme, 'app.config')
            self.theme_vars = util.readSimpleConfigFile(theme_app_config)
        else:
            self.theme_vars = {}

    def get(self, key, useThemeData=True):
        if useThemeData and key in self.theme_vars:
            return self.theme_vars[key]
        else:
            return self.default_vars[key]

    def contains(self, key, useThemeData=True):
        return ((useThemeData and key in self.theme_vars) or 
                (key in self.default_vars))
