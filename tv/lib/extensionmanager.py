# Miro - an RSS based video player application
# Copyright (C) 2010, 2011
# Participatory Culture Foundation
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

"""miro.extensionmanager -- Extension manager that loads and manages
extensions.

For more information on the extension system see:
http://develop.participatoryculture.org/index.php/ExtensionSystem
"""

import traceback
import logging
import os
import sys
import ConfigParser
from miro import app
from miro import prefs

# need to do this otherwise py2exe won't pick up the api module
from miro import api

class Extension:
    def __init__(self):
        self.name = "Unknown"
        self.version = "0.0"
        self.description = "No description"
        self.ext_module = None
        # whether or not to enable this extension by default
        self.enabled_by_default = False
        # whether or not this extension has been loaded
        self.loaded = False

    def __repr__(self):
        return "%s (%s)" % (self.name, self.version)

def get_extensions(ext_dir):
    """Finds all ``.miroext`` files in extension directories.  Pulls
    the following information from the ``.miroext`` files:

    * extension.name (string)
    * extension.version (string)
    * extension.module (string)
    * [optional] extension.description (string)
    * [optional] extension.enabled_by_default (bool)
    """
    if not os.path.isdir(ext_dir):
        # skip directories that don't exist
        return []

    # go through all the extension directories and get a listing of
    # files.  we're looking for files ending with .miroext
    extensions = []
    files = os.listdir(ext_dir)
    files = [os.path.join(ext_dir, m) for m in files
             if m.endswith(".miroext")]

    for f in files:
        if not os.path.isfile(f):
            logging.debug("%s is not a file; skipping", f)
            continue

        cf = ConfigParser.RawConfigParser()
        try:
            cf.read(f)
            e = Extension()
            e.name = cf.get("extension", "name")
            e.version = cf.get("extension", "version")
            e.ext_module = cf.get("extension", "module")

            if cf.has_option("extension", "description"):
                e.description = cf.get("extension", "description")

            if cf.has_option("extension", "enabled_by_default"):
                e.enabled_by_default = cf.getboolean(
                    "extension", "enabled_by_default")
                e.enabled = e.enabled_by_default

            extensions.append(e)
        except (ConfigParser.NoSectionError,
                ConfigParser.NoOptionError,
                ConfigParser.ParsingError):
            logging.warning("Extension file %s is malformed.\n%s",
                            f, traceback.format_exc())

    return extensions

class ExtensionManager(object):
    def __init__(self, core_ext_dirs, user_ext_dirs):
        self.core_ext_dirs = core_ext_dirs
        self.user_ext_dirs = user_ext_dirs
        self.enabled_extensions = app.config.get(prefs.ENABLED_EXTENSIONS)
        self.disabled_extensions = app.config.get(prefs.DISABLED_EXTENSIONS)

        # list of core extensions--we keep this list to know whether we
        # can make this extension enabled_by_default
        self.core_extensions = []

        # list of all extensions--core and user
        self.extensions = []

    def get_extension_by_name(self, name):
        for mem in self.extensions:
            if mem.name == name:
                return mem
        raise ValueError("No extension by %s" % name)

    def is_enabled(self, ext):
        return ext.name in self.enabled_extensions

    def should_load(self, ext):
        if ext.name in self.disabled_extensions:
            return False
        if ext.name in self.enabled_extensions:
            return True

        if ext in self.core_extensions and ext.enabled_by_default:
            self.enable_extension(ext)
        else:
            self.disable_extension(ext)

        return ext.enabled_by_default

    def enable_extension(self, ext):
        if ext.name in self.disabled_extensions:
            self.disabled_extensions.remove(ext.name)
            app.config.set(prefs.DISABLED_EXTENSIONS, self.disabled_extensions)

        if ext.name not in self.enabled_extensions:
            self.enabled_extensions.append(ext.name)
            app.config.set(prefs.ENABLED_EXTENSIONS, self.enabled_extensions)

    def import_extension(self, ext):
        """Imports an extension.

        :raises ImportError: throws ImportError from importing the
            extension
        """
        logging.info("extension manager: importing: %r", ext)
        __import__(ext.ext_module)

    def load_extension(self, ext):
        """Loads an extension by calling the ``load`` function.

        :raises StandardError: throws whatever the extension throws
            when loading
        """
        logging.info("extension manager: loading: %r", ext)
        load = getattr(sys.modules[ext.ext_module], "load")
        load()
        ext.loaded = True

    def disable_extension(self, ext):
        if ext.name not in self.disabled_extensions:
            self.disabled_extensions.append(ext.name)
            app.config.set(prefs.DISABLED_EXTENSIONS, self.disabled_extensions)

        if ext.name in self.enabled_extensions:
            self.enabled_extensions.remove(ext.name)
            app.config.set(prefs.ENABLED_EXTENSIONS, self.enabled_extensions)

    def unload_extension(self, ext):
        """Unloads an extension by calling the ``unload`` function.

        :raises StandardError: throws whatever the extension throws
            when unloading
        """
        if not ext.ext_module in sys.modules:
            return
        logging.info("extension manager: unloading: %r", ext)
        unload = getattr(sys.modules[ext.ext_module], "unload")
        unload()
        ext.loaded = False

    def load_extensions(self):
        """Loads all extensions that are enabled.
        """
        extensions = []
        for d in self.core_ext_dirs:
            logging.info("Loading core extensions in %s", d)
            exts = get_extensions(d)
            if exts:
                sys.path.insert(0, d)
                extensions.extend(exts)

        self.core_extensions = list(extensions)

        for d in self.user_ext_dirs:
            try:
                d = d % {
                    "supportdir": app.config.get(prefs.SUPPORT_DIRECTORY)
                    }
            except KeyError:
                logging.exception("bad extension directory '%s'", d)
                continue

            logging.info("Loading user extensions in %s", d)
            exts = get_extensions(d)
            if exts:
                sys.path.insert(0, d)
                extensions.extend(exts)

        self.extensions = extensions

        # FIXME - if we need extensions to load in a certain order
        # this is the place we'd sort them

        for mem in extensions:
            if not self.should_load(mem):
                continue
            try:
                self.import_extension(mem)
                self.load_extension(mem)
            except StandardError:
                logging.exception(
                    "Import/Load error when loading %r.  Disabling.", mem)
                self.disable_extension(mem)
                continue
