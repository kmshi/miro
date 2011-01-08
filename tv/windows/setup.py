# Miro - an RSS based video player application
# Copyright (C) 2005, 2006, 2007, 2008, 2009, 2010, 2011
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

import os.path
import os
import shutil
import time
import socket
import copy
import sys
import string
import subprocess
import zipfile as zip
from glob import glob, iglob
from xml.sax.saxutils import escape
from distutils import sysconfig 
from distutils.core import Command
import distutils.command.install_data
from distutils.ccompiler import new_compiler
from distutils import file_util, dir_util


###############################################################################
## Paths and configuration                                                   ##
###############################################################################

# The location of the NSIS compiler
NSIS_PATH = 'C:\\Program Files\\NSIS\\makensis.exe'

# This is the version of the binary kit to use
BINARY_KIT_VERSION = open("binary_kit_version").read().strip()

# If you're using the prebuilt DTV Dependencies Binary Kit, just set
# the path to it here, and ignore everything after this point. In
# fact, if you unpacked or checked out the binary kit in the same
# directory as DTV itself, the default value here will work.
#
# Otherwise, if you build the dependencies yourself instead of using
# the Binary Kit, ignore this setting and change all of the settings
# below.
BINARY_KIT_ROOT = "miro-binary-kit-win-%s" % BINARY_KIT_VERSION

if not os.path.exists or not os.path.isdir(BINARY_KIT_ROOT):
    print "Binary kit %s is missing.  Run 'setup_binarykit.sh'." % BINARY_KIT_ROOT
    sys.exit(1)

ZLIB_INCLUDE_PATH = os.path.join(BINARY_KIT_ROOT, 'zlib', 'include')
ZLIB_LIB_PATH = os.path.join(BINARY_KIT_ROOT, 'zlib', 'lib')
ZLIB_RUNTIME_LIBRARY_PATH = os.path.join(BINARY_KIT_ROOT, 'zlib')

OPENSSL_INCLUDE_PATH = os.path.join(BINARY_KIT_ROOT, 'openssl', 'include')
OPENSSL_LIB_PATH = os.path.join(BINARY_KIT_ROOT, 'openssl', 'lib')
OPENSSL_LIBRARIES = ['ssleay32', 'libeay32']

# GTK_ROOT_PATH = os.path.join(BINARY_KIT_ROOT, 'gtk+-bundle_2.20.0-20100406_win32')
GTK_ROOT_PATH = os.path.join(BINARY_KIT_ROOT, 'gtk+-bundle_2.16.6-20091215_win32')
GTK_INCLUDE_PATH = os.path.join(GTK_ROOT_PATH, 'include')
GTK_LIB_PATH = os.path.join(GTK_ROOT_PATH, 'lib')
GTK_BIN_PATH = os.path.join(GTK_ROOT_PATH, 'bin')
GTK_INCLUDE_DIRS = [
    os.path.join(GTK_INCLUDE_PATH, 'atk-1.0'),
    os.path.join(GTK_INCLUDE_PATH, 'gtk-2.0'),
    os.path.join(GTK_INCLUDE_PATH, 'glib-2.0'),
    os.path.join(GTK_INCLUDE_PATH, 'pango-1.0'),
    os.path.join(GTK_INCLUDE_PATH, 'cairo'),
    os.path.join(GTK_LIB_PATH, 'glib-2.0', 'include'),
    os.path.join(GTK_LIB_PATH, 'gtk-2.0', 'include'),
]

PYGOBJECT_INCLUDE_DIR = os.path.join(BINARY_KIT_ROOT, 'pygobject')

# path to the Mozilla "xulrunner-sdk" distribution.
XULRUNNER_SDK_PATH = os.path.join(BINARY_KIT_ROOT, 'xulrunner-sdk')
XULRUNNER_SDK_BIN_PATH = os.path.join(XULRUNNER_SDK_PATH, 'bin')

VLC_PATH = os.path.join(BINARY_KIT_ROOT, 'libvlc')
LIBTORRENT_PATH = os.path.join(BINARY_KIT_ROOT, 'libtorrent')
MUTAGEN_PATH = os.path.join(BINARY_KIT_ROOT, 'mutagen-1.20')

FFMPEG_PATH = os.path.join(
    BINARY_KIT_ROOT, 'ffmpeg', 'ffmpeg-r25766-swscale-r32562-mingw32-static')
FFMPEG2THEORA_PATH = os.path.join(BINARY_KIT_ROOT, 'ffmpeg2theora')

VCREDIST90_PATH = os.path.join(BINARY_KIT_ROOT, 'vc90redist')

def find_data_files(dest_path_base, source_path):
    retval = []
    for path, dirs, files in os.walk(source_path):
        if not path.startswith(source_path):
            raise AssertionError()
        dest_path = path.replace(source_path, dest_path_base)
        source_files = [os.path.join(path, f) for f in files]
        retval.append((dest_path, source_files))
        if '.svn' in dirs:
            dirs.remove('.svn')
    return retval

# Name of python binary, so we can build the download daemon in
# another process. (Can we get this from Python itself?)
PYTHON_BINARY = "python"

###############################################################################
## End of configuration. No user-servicable parts inside                     ##
###############################################################################

from distutils.core import setup
from distutils.extension import Extension
from distutils.core import Command
from distutils import log
import py2exe
import py2exe.build_exe
import os
import sys
import re
from Pyrex.Distutils import build_ext

# The name of this platform.
platform = 'windows'

# Find the top of the source tree and set search path
root_dir = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), '..')
root_dir = os.path.normpath(os.path.abspath(root_dir))
platform_dir = os.path.join(root_dir, 'windows')
platform_package_dir = os.path.join(platform_dir, 'plat')
widgets_dir = os.path.join(platform_package_dir, 'frontends', 'widgets')
portable_dir = os.path.join(root_dir, 'lib')
portable_widgets_dir = os.path.join(portable_dir, 'frontends', 'widgets')
portable_xpcom_dir = os.path.join(portable_widgets_dir, 'gtk', 'xpcom')
test_dir = os.path.join(root_dir, 'resources')
resources_dir = os.path.join(root_dir, 'resources')
extensions_dir = os.path.join(root_dir, 'extensions')

sys.path.insert(0, root_dir)
# when we install the portable modules, they will be in the miro
# package, but at this point, they are in a package named "lib",
# so let's hack it
import lib
sys.modules['miro'] = lib

from miro import util

# put the libtorrent extension on the path, so py2exe can find the
# .pyd file
sys.path.insert(0, LIBTORRENT_PATH)
sys.path.insert(0, MUTAGEN_PATH)

#### Extensions ####
ngrams_ext = \
    Extension("miro.ngrams",
        [os.path.join(portable_dir, 'ngrams.c')],
    )

pygtkhacks_ext = Extension(
    "miro.frontends.widgets.gtk.pygtkhacks",
    sources=[
        os.path.join(portable_widgets_dir, 'gtk', 'pygtkhacks.pyx'),
        ],
    include_dirs=GTK_INCLUDE_DIRS + [PYGOBJECT_INCLUDE_DIR],
    library_dirs=[GTK_LIB_PATH],
    libraries=[
        'gtk-win32-2.0',
        'pango-1.0',
        ]
    )

xulrunnerbrowser_ext_dir = os.path.join(widgets_dir, 'XULRunnerBrowser')
xulrunnerbrowser_ext = Extension(
    "miro.plat.frontends.widgets.xulrunnerbrowser",
    include_dirs=[
        os.path.join(XULRUNNER_SDK_PATH, 'sdk', 'include'),
        os.path.join(XULRUNNER_SDK_PATH, 'include'),
        os.path.join(XULRUNNER_SDK_PATH, 'include', 'xpcom'),
        portable_xpcom_dir,
        ] + GTK_INCLUDE_DIRS,
    define_macros=[
        ("XP_WIN", 1), 
        ("XPCOM_GLUE", 1),
        ("PCF_USING_XULRUNNER19", 1),
        ],
    extra_compile_args=[
        "/Zc:wchar_t-"
        ],
    library_dirs=[
        os.path.join(XULRUNNER_SDK_PATH, 'lib'),
        GTK_LIB_PATH,
        ],
    libraries=[
        'xpcomglue',
        'xul',
        'user32',
        'gdk-win32-2.0',
        'gtk-win32-2.0',
        ],
    language="c++",
    sources=[
        os.path.join(xulrunnerbrowser_ext_dir, 'xulrunnerbrowser.pyx'),
        os.path.join(portable_xpcom_dir, 'HttpObserver.cc'),
        os.path.join(xulrunnerbrowser_ext_dir, 'MiroBrowserEmbed.cpp'),
        os.path.join(xulrunnerbrowser_ext_dir, 'MiroWindowCreator.cpp'),
        os.path.join(xulrunnerbrowser_ext_dir, 'FixFocus.cpp'),
        os.path.join(xulrunnerbrowser_ext_dir, 'Init.cpp'),
        ]
    )

# Setting the path here allows py2exe to find the DLLS
os.environ['PATH'] = ';'.join([
        OPENSSL_LIB_PATH, ZLIB_RUNTIME_LIBRARY_PATH, 
        LIBTORRENT_PATH, GTK_BIN_PATH, os.environ['PATH']])

# Private extension modules to build.
ext_modules = [
    ngrams_ext,
    pygtkhacks_ext,
    xulrunnerbrowser_ext,
]

def fill_template(templatepath, outpath, **vars):
    s = open(templatepath, 'rt').read()
    s = string.Template(s).safe_substitute(**vars)
    f = open(outpath, "wt")
    f.write(s)
    f.close()

# Data files
data_files = []
data_files.extend(find_data_files('xulrunner', XULRUNNER_SDK_BIN_PATH))

image_loader_path = os.path.join('lib', 'gtk-2.0', '2.10.0', 'loaders')
theme_engine_path = os.path.join('lib', 'gtk-2.0', '2.10.0', 'engines')
theme_path = os.path.join('share', 'themes')
for path in (image_loader_path, theme_engine_path, theme_path):
    src_path = os.path.join(GTK_ROOT_PATH, path)
    data_files.extend(find_data_files(path, src_path))

data_files.append(('', iglob(os.path.join(GTK_BIN_PATH, '*.dll'))))
data_files.extend(find_data_files(
        'vlc-plugins', os.path.join(VLC_PATH, 'vlc-plugins')))
data_files.append(('', [os.path.join(VLC_PATH, 'libvlc.dll')]))
data_files.append(('', [os.path.join(VLC_PATH, 'libvlccore.dll')]))
data_files.append(('', [os.path.join(LIBTORRENT_PATH, 'libtorrent.pyd')]))
data_files.append(('', [
            os.path.join(FFMPEG_PATH, 'bin', 'ffmpeg.exe'),
            os.path.join(FFMPEG2THEORA_PATH, 'bin', 'ffmpeg2theora.exe')]))
data_files.append(('', glob(os.path.join(FFMPEG_PATH, 'presets', '*.ffpreset'))))
data_files.extend(find_data_files('Microsoft.VC90.CRT',
    os.path.join(VCREDIST90_PATH, 'Microsoft.VC90.CRT')))

# handle the resources subdirectories.
for dir in ('searchengines', 'images', 'conversions', 'devices'):
    dest_dir = os.path.join('resources', dir)
    source_dir = os.path.join(resources_dir, dir)
    data_files.extend(find_data_files(dest_dir, source_dir))

data_files.append(('resources', [os.path.join(root_dir, 'CREDITS')]))

data_files.extend(find_data_files("extensions", extensions_dir))

locale_temp_dir = os.path.join(os.path.dirname(__file__), "build", "locale")

def copy_locale_files():
    print "*** copying locale files ***"
    # handle locale files
    locale_files = []
    for source in glob(os.path.join(resources_dir, "locale", "*.mo")):
        lang = os.path.basename(source)[:-3]
        dest = os.path.join(locale_temp_dir, lang, "LC_MESSAGES", "miro.mo")
        locale_files.append((source, dest))

    dir_util.create_tree(os.path.dirname(__file__),
                         [dst for src, dst in locale_files])

    for source, dest in locale_files:
        file_util.copy_file(source, dest, update=True, verbose=True)

# FIXME - this should be done inside a build command
copy_locale_files()
data_files.extend(find_data_files(os.path.join("resources", "locale"),
                                  locale_temp_dir))

app_config = os.path.join(resources_dir, 'app.config.template')
template_vars = util.read_simple_config_file(app_config)

# pixmap for the about dialog
icon_path = os.path.join("icons", "hicolor", "128x128", "apps")
data_files.append((os.path.join("resources", icon_path), 
                   [os.path.join(platform_dir, icon_path, "miro.png")]))

###########################################################################

#### Our specialized install_data command ####
class install_data(distutils.command.install_data.install_data):
    """install_data extends to default implementation so that it
    automatically installs app.config from app.config.template.
    """

    def install_app_config(self):
        template = os.path.join(resources_dir, 'app.config.template')
        dest = os.path.join(self.install_dir, 'resources', 'app.config')
        revision = util.query_revision()
        if revision is None:
            revision = "unknown"
            revisionurl = "unknown"
            revisionnum = "unknown"
        else:
            revisionurl = revision[0]
            revisionnum = revision[1]
            revision = "%s - %s" % revision

        print "Using %s" % revisionnum

        self.mkpath(os.path.dirname(dest))
        # We don't use the dist utils copy_file() because it only
        # copies the file if the timestamp is newer
        fill_template(template, dest,
            APP_REVISION=revision,
            APP_REVISION_NUM=revisionnum,
            APP_REVISION_URL=revisionurl,
            APP_PLATFORM='windows',
            BUILD_MACHINE="%s@%s" % (os.environ['username'],
                socket.gethostname()),
            BUILD_TIME=str(time.time()))
        self.outfiles.append(dest)

    def install_gdk_pixbuf_loaders(self):
        basename = os.path.join('etc', 'gtk-2.0', 'gdk-pixbuf.loaders')
        source = os.path.join(GTK_ROOT_PATH, basename)
        dest = os.path.join(self.install_dir, basename)
        contents = open(source).read()
        # Not sure why they have paths like this in the file, but we
        # need to change them.
        contents = contents.replace(
            "c:/devel/target/9c384abfa28a3e070eb60fc2972f823b/", "")
        self.mkpath(os.path.dirname(dest))
        open(dest, 'wt').write(contents)
        self.outfiles.append(dest)

    def run(self):
        distutils.command.install_data.install_data.run(self)
        self.install_app_config()
        self.install_gdk_pixbuf_loaders()

# We want to make sure we include msvcp90.dll in the dist directory.
# Recipe taken from
# http://www.py2exe.org/index.cgi/OverridingCriteraForIncludingDlls
DLLS_TO_INCLUDE = [
    'msvcp90.dll',
]
origIsSystemDLL = py2exe.build_exe.isSystemDLL
def isSystemDLL(pathname):
    if os.path.basename(pathname).lower() in DLLS_TO_INCLUDE:
        return True
    else:
        return origIsSystemDLL(pathname)
py2exe.build_exe.isSystemDLL = isSystemDLL

class bdist_miro(Command):
    description = "Build Miro"

    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        self.run_command('py2exe')
        self.copy_ico()

    def copy_ico(self):
        dist_dir = self.get_finalized_command('py2exe').dist_dir
        shortappname = template_vars["shortAppName"]
        self.copy_file("Miro.ico", 
                       os.path.join(dist_dir, "%s.ico" % shortappname))

class bdist_test(Command):
    description = "Builds Miro with unit tests"

    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        self.run_command('bdist_miro')
        self.copy_test_data()

    def copy_test_data(self):
        # copy test data over
        dist_dir = self.get_finalized_command('py2exe').dist_dir

        self.copy_tree(os.path.join(resources_dir, 'testdata'),
                       os.path.join(dist_dir, 'resources', 'testdata'))

class runmiro(Command):
    description = "build Miro and start it up"

    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        self.run_command('bdist_miro')
        olddir = os.getcwd()
        os.chdir(self.get_finalized_command('py2exe').dist_dir)
        os.system("%s" % template_vars['shortAppName'])
        os.chdir(olddir)

class bdist_nsis(Command):
    description = "create Miro installer using NSIS"

    user_options = [
        ('generic', None, 'Build a generic installer instead of the Miro-branded installer.'),
        ('nozugo', None, 'Do not include the silent Zugo toolbar installer.'),
        ('mozilla', None, 'Do not show the toolbar option to international users.'),
        ('install-icon=', None, 'ICO file to use for the installer.'),
        ('install-image=', None, 'BMP file to use for the welcome/finish pages.')
        ]

    def initialize_options(self):
        self.generic = False
        self.nozugo = False
        self.mozilla = False
        self.install_icon = None
        self.install_image = None

    def finalize_options(self):
        if self.generic and (self.install_icon or self.install_icon):
            raise AssertionError("cannot specify install images with "
                                 "generic installer")
        if self.generic:
            self.install_icon = 'miro-installer-generic.ico'
            self.install_image = 'miro-install-generic.bmp'
        if self.install_icon is None:
            self.install_icon = 'miro-installer.ico'
        if self.install_image is None:
            self.install_image = 'miro-install-image.bmp'

    def run(self):
        self.run_command('bdist_miro')
        self.dist_dir = self.get_finalized_command('py2exe').dist_dir

        log.info("building installer")

        self.copy_file(os.path.join(platform_dir, 'Miro.nsi'), self.dist_dir)
        if not self.nozugo:
            self.copy_file(os.path.join(platform_dir, 'zugo-silent.exe'), self.dist_dir)
        self.copy_file(self.install_icon, self.dist_dir)
        self.copy_file(self.install_image, self.dist_dir)

        nsis_vars = {}
        for our_name, nsis_name in [('appVersion', 'CONFIG_VERSION'),
                                    ('projectURL', 'CONFIG_PROJECT_URL'),
                                    ('shortAppName', 'CONFIG_SHORT_APP_NAME'),
                                    ('longAppName', 'CONFIG_LONG_APP_NAME'),
                                    ('publisher', 'CONFIG_PUBLISHER')]:
            nsis_vars[nsis_name] = template_vars[our_name]

        nsis_vars['CONFIG_EXECUTABLE'] = "%s.exe" % template_vars['shortAppName']
        nsis_vars['CONFIG_DOWNLOADER_EXECUTABLE'] = "%s_Downloader.exe" % \
                template_vars['shortAppName']
        nsis_vars['CONFIG_MOVIE_DATA_EXECUTABLE'] = "%s_MovieData.exe" % \
                template_vars['shortAppName']
        nsis_vars['CONFIG_ICON'] = "%s.ico" % template_vars['shortAppName']
        nsis_vars['CONFIG_PROG_ID'] = template_vars['longAppName'].replace(" ", ".") + ".1"
        nsis_vars['MIRO_INSTALL_ICON'] = self.install_icon
        nsis_vars['MIRO_INSTALL_IMAGE'] = self.install_image
        nsis_vars['CONFIG_BINARY_KIT'] = BINARY_KIT_ROOT
        if not self.nozugo:
            nsis_vars['MIROBAR_EXE'] = 'zugo-silent.exe'
        if self.generic:
            nsis_vars['GENERIC_INSTALLER'] = '1'
        if self.mozilla:
            nsis_vars['MOZILLA_INSTALLER'] = '1'

        output_file = '%s-%s'
        # One stage installer
        if self.generic:
            output_file = "%s-generic" % output_file
        if self.nozugo:
            output_file = "%s-nozugo" % output_file
        if self.mozilla:
            output_file = '%s-mozilla' % output_file
            
        output_file = (output_file % 
                       (template_vars['shortAppName'], template_vars['appVersion']))
        nsis_vars['CONFIG_OUTPUT_FILE'] = '%s.exe' % output_file
        nsis_vars['CONFIG_TWOSTAGE'] = "No"

        nsis_args = ["/D%s=%s" % (k, v) for (k, v) in nsis_vars.iteritems()]
        nsis_args.append(os.path.join(self.dist_dir, "Miro.nsi"))

        if os.access(output_file, os.F_OK):
            os.remove(output_file)
        if subprocess.call([NSIS_PATH] + nsis_args) != 0:
            print "ERROR creating the 1 stage installer, quitting"
            return

        # Two stage installer
        if self.generic:
            output_file = '%s-%s-generic-twostage.exe'
        else:
            output_file = "%s-%s-twostage.exe"
        output_file = (output_file % 
                       (template_vars['shortAppName'], template_vars['appVersion']))
        nsis_vars['CONFIG_OUTPUT_FILE'] = output_file
        nsis_vars['CONFIG_TWOSTAGE'] = "Yes"
        nsis_vars.pop('MIROBAR_EXE', None)

        nsis_args = ["/D%s=%s" % (k, v) for (k, v) in nsis_vars.iteritems()]
        nsis_args.append(os.path.join(self.dist_dir, "Miro.nsi"))

        if os.access(output_file, os.F_OK):
            os.remove(output_file)
        subprocess.call([NSIS_PATH] + nsis_args)

        zip_path = os.path.join(self.dist_dir, "%s-Contents-%s.zip" %
            (template_vars['shortAppName'], template_vars['appVersion']))
        self.zipfile = zip.ZipFile(zip_path, 'w', zip.ZIP_DEFLATED)
        self.add_file(nsis_vars['CONFIG_EXECUTABLE'])
        self.add_file(nsis_vars['CONFIG_ICON'])
        self.add_file(nsis_vars['CONFIG_MOVIE_DATA_EXECUTABLE'])
        self.add_glob("*.dll")

        self.add_directory("defaults")
        self.add_directory("resources")
        self.add_directory("xulrunner")

        self.zipfile.close()

    def add_glob(self, wildcard):
        wildcard = os.path.join(self.dist_dir, wildcard)
        length = len(self.dist_dir)
        for filename in iglob(wildcard):
            if filename[:length] == self.dist_dir:
                filename = filename[length:]
                while (len(filename) > 0 
                       and (filename[0] == '/' or filename[0] == '\\')):
                    filename = filename[1:]
            print "Compressing %s" % filename
            self.zipfile.write(os.path.join(self.dist_dir, filename), filename)

    def add_file(self, filename):
        length = len(self.dist_dir)
        if filename[:length] == self.dist_dir:
            filename = filename[length:]
            while (len(filename) > 0 
                   and (filename[0] == '/' or filename[0] == '\\')):
                filename = filename[1:]
        print "Compressing %s" % filename
        self.zipfile.write(os.path.join(self.dist_dir, filename), filename)

    def add_directory(self, dirname):
        for root, dirs, files in os.walk(os.path.join(self.dist_dir, dirname)):
            for name in files:
                self.add_file(os.path.join(root, name))

if __name__ == "__main__":
    setup(
        windows=[
            {
                'script': 'Miro.py',
                'dest_base': template_vars['shortAppName'],
                'icon_resources': [(0, "Miro.ico")],
                },
            {
                'script': 'Miro_Downloader.py',
                'dest_base': '%s_Downloader' % template_vars['shortAppName'],
                'icon_resources': [(0, "Miro.ico")],
                },
            ],
        console=[
            {
                'script': 'moviedata_util.py',
                'dest_base': '%s_MovieData' % template_vars['shortAppName'],
                'icon_resources': [(0, "Miro.ico")],
                },
            {
                'script': 'mirotest.py',
                'dest_base': 'mirotest',
                'icon_resources': [(0, "Miro.ico")],
                }
            ],
        ext_modules=ext_modules,
        packages=[
            'miro',
            'miro.dl_daemon',
            'miro.dl_daemon.private',
            'miro.frontends',
            'miro.frontends.widgets',
            'miro.frontends.widgets.gtk',
            'miro.test',
            'miro.plat',
            'miro.plat.renderers',
            'miro.plat.frontends',
            'miro.plat.frontends.widgets',
            ],
        package_dir={
            'miro': portable_dir,
            'miro.plat': platform_package_dir,
            },
        data_files=data_files,
        cmdclass={
            'build_ext': build_ext,
            'install_data': install_data,
            'bdist_miro': bdist_miro,
            'bdist_nsis': bdist_nsis,
            'bdist_test': bdist_test,
            'runmiro': runmiro,
            },
        options={
            'py2exe': {
                'packages': [
                    'encodings',
                    ],
                'includes': ('cairo, pango, pangocairo, atk, gobject, '
                             'gio, libtorrent, mutagen'),
                },
            },
        )
