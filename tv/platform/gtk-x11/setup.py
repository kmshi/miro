#!/usr/bin/env python

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

# This needs to be above Paths and configuration :(
#
# This isn't being used right now, as it doesn't detect all the cases
# in which we need the xine hack
def use_xine_hack_default():
    try:
        # Non-debian based system will throw an exception here
        f = open('/etc/debian_version')
        if f.read().strip() == '4.0': # Debian etch
            f.close()
            return True
        else:
            # Ubuntu Feisty is Debian based but lists testing/unstable
            # in /etc/debian_version, so we check /etc/issue
            f.close()
            f = open('/etc/issue')
            osname = f.read()
            if (osname.find("Ubuntu") > -1) and (osname.find("7.04")>-1):
                f.close()
                return True
    except:
        pass
    return False

##############################################################################
## Paths and configuration                                                   ##
###############################################################################

BOOST_LIB = 'boost_python'

USE_XINE_HACK = True #use_xine_hack_default()

###############################################################################
## End of configuration. No user-servicable parts inside                     ##
###############################################################################

from distutils.cmd import Command
from distutils.core import setup
from distutils.extension import Extension
from distutils.errors import DistutilsOptionError
from distutils import dir_util
from distutils import log
from distutils.util import change_root
from glob import glob
from string import Template
import distutils.command.build_py
import distutils.command.build_py
import distutils.command.install_data
import os
import pwd
import subprocess
import sys
import re
import time
import shutil

from Pyrex.Distutils import build_ext

#### usefull paths to have around ####
# bdist_rpm and possibly other commands copies setup.py into a subdir of
# platform/gtk-x11.  This makes it hard to find the root directory.  We work
# our way up the path until our is_root_dir test passes.
def is_root_dir(dir):
    return os.path.exists(os.path.join(dir, "MIRO_ROOT"))

root_try = os.path.abspath(os.path.dirname(__file__))
while True:
    if is_root_dir(root_try):
        root_dir = root_try
        break
    if root_try == '/':
        raise RuntimeError("Couldn't find Miro root directory")
    root_try = os.path.abspath(os.path.join(root_try, '..'))
portable_dir = os.path.join(root_dir, 'portable')
portable_frontend_dir = os.path.join(portable_dir, 'frontends')
portable_html_frontend_dir = os.path.join(portable_frontend_dir, 'html')
dl_daemon_dir = os.path.join(portable_dir, 'dl_daemon')
test_dir = os.path.join(portable_dir, 'test')
compiled_templates_dir = os.path.join(portable_dir, 'compiled_templates')
compiled_templates_unittest_dir = os.path.join(compiled_templates_dir,'unittest')
resource_dir = os.path.join(root_dir, 'resources')
platform_dir = os.path.join(root_dir, 'platform', 'gtk-x11')
miroplatform_dir = os.path.join(platform_dir, 'miroplatform')
glade_dir = os.path.join(platform_dir, 'glade')
xine_dir = os.path.join(platform_dir, 'xine')
frontend_implementation_dir = os.path.join(platform_dir,
        'frontend_implementation')
debian_package_dir = os.path.join(platform_dir, 'debian_package')

sys.path[0:0] = ['%s/platform/%s' % (root_dir, 'gtk-x11'), '%s/platform' % root_dir, '%s/portable' % root_dir]

import template_compiler
import setup_portable
template_compiler.compileAllTemplates(root_dir)

# little hack get the version from the current app.config.template
import util
app_config = os.path.join(resource_dir, 'app.config.template')
appVersion = util.readSimpleConfigFile(app_config)['appVersion']

# RPM hack
if 'bdist_rpm' in sys.argv:
    appVersion = appVersion.replace('-', '_')

#### utility functions ####
def getlogin():
    try:
        return os.environ['LOGNAME']
    except KeyError:
        pass
    try:
        return os.environ['USER']
    except KeyError:
        pass
    pwd.getpwuid(os.getuid())[0] 

def read_file(path):
    f = open(path)
    try:
        return f.read()
    finally:
        f.close()

def write_file(path, contents):
    f = open(path, 'w')
    try:
        f.write(contents)
    finally:
        f.close()

def expand_file_contents(path, **values):
    """Do a string expansion on the contents of a file using the same rules as
    string.Template from the standard library.  
    """

    template = Template(read_file(path))
    expanded = template.substitute(**values)
    write_file(path, expanded)

def getCommandOutput(cmd, warnOnStderr = True, warnOnReturnCode = True):
    """Wait for a command and return its output.  Check for common errors and
    raise an exception if one of these occurs.
    """

    p = subprocess.Popen(cmd, shell=True, close_fds = True,
            stdout=subprocess.PIPE, stderr = subprocess.PIPE)
    stdout, stderr = p.communicate()
    if warnOnStderr and stderr != '':
        raise RuntimeError("%s outputted the following error:\n%s" % 
                (cmd, stderr))
    if warnOnReturnCode and p.returncode != 0:
        raise RuntimeError("%s had non-zero return code %d" % 
                (cmd, p.returncode))
    return stdout

def parsePkgConfig(command, components, options_dict = None):
    """Helper function to parse compiler/linker arguments from 
    pkg-config/mozilla-config and update include_dirs, library_dirs, etc.

    We return a dict with the following keys, which match up with keyword
    arguments to the setup function: include_dirs, library_dirs, libraries,
    extra_compile_args.

    Command is the command to run (pkg-config, mozilla-config, etc).
    Components is a string that lists the components to get options for.

    If options_dict is passed in, we add options to it, instead of starting
    from scratch.
    """

    if options_dict is None:
        options_dict = {
            'include_dirs' : [],
            'library_dirs' : [],
            'libraries' : [],
            'extra_compile_args' : []
        }
    commandLine = "%s --cflags --libs %s" % (command, components)
    output = getCommandOutput(commandLine).strip()
    for comp in output.split():
        prefix, rest = comp[:2], comp[2:]
        if prefix == '-I':
            options_dict['include_dirs'].append(rest)
        elif prefix == '-L':
            options_dict['library_dirs'].append(rest)
        elif prefix == '-l':
            options_dict['libraries'].append(rest)
        else:
            options_dict['extra_compile_args'].append(comp)
    return options_dict

#### The fasttypes extension ####
fasttypes_ext = \
    Extension("miro.fasttypes", 
        sources = [os.path.join(portable_dir, 'fasttypes.cpp')],
        libraries = [BOOST_LIB],
    )

##### The libtorrent extension ####
libtorrent_ext = setup_portable.libtorrent_extension(portable_dir)

#### MozillaBrowser Extension ####
try:
    packages = getCommandOutput("pkg-config --list-all")
except RuntimeError, error:
    sys.exit("Package config error:\n%s" % (error,))
if re.search("^xulrunner-xpcom", packages, re.MULTILINE):
    xpcom = 'xulrunner-xpcom'
    gtkmozembed = 'xulrunner-gtkmozembed'
elif re.search("^mozilla-xpcom", packages, re.MULTILINE):
    xpcom = 'mozilla-xpcom'
    gtkmozembed = 'mozilla-gtkmozembed'
elif re.search("^firefox-xpcom", packages, re.MULTILINE):
    xpcom = 'firefox-xpcom'
    gtkmozembed = 'firefox-gtkmozembed'
else:
    sys.exit("Can't find xulrunner-xpcom, mozilla-xpcom or firefox-xpcom")

if not "clean" in sys.argv:
    # build a miro script that wraps the miro.real script with an LD_LIBRARY_PATH
    # environment variable to pick up the xpcom we decided to use.
    try:
        fflib = getCommandOutput("pkg-config --variable=libdir %s" % xpcom)
        # pluck off the last \n
        fflib = fflib[:-1]
        f = open(os.path.join(platform_dir, "miro"), "w")
        f.write("#!/bin/sh\nLD_LIBRARY_PATH=%s miro.real \"$@\"\n" % fflib)
        f.close()
    except RuntimeError, error:
        sys.exit("Package config error:\n%s" % (error,))

mozilla_browser_options = parsePkgConfig("pkg-config" , 
        "gtk+-2.0 glib-2.0 pygtk-2.0 %s %s" % (gtkmozembed, xpcom))
mozilla_lib_path = parsePkgConfig('pkg-config', 
        '%s' % gtkmozembed)['library_dirs']
# Find the base mozilla directory, and add the subdirs we need.
def allInDir(directory, subdirs):
    for subdir in subdirs:
        if not os.path.exists(os.path.join(directory, subdir)):
            return False
    return True
xpcom_includes = parsePkgConfig("pkg-config", xpcom)
mozIncludeBase = None
for dir in xpcom_includes['include_dirs']:
    if allInDir(dir, ['dom', 'gfx', 'widget']):
        # we can be pretty confident that dir is the mozilla/firefox/xulrunner
        # base include directory
        mozIncludeBase = dir
        break
if mozIncludeBase is None:
    raise ValueError("Can't find mozilla include base directory")
for subdir in ['dom', 'gfx', 'widget', 'commandhandler', 'uriloader',
            'webbrwsr', 'necko', 'windowwatcher']:
    path = os.path.join(mozIncludeBase, subdir)
    mozilla_browser_options['include_dirs'].append(path)


nsI = True
for dir in mozilla_browser_options['include_dirs']:
    if os.path.exists(os.path.join (dir, "nsIServiceManagerUtils.h")):
        nsI = True
        break
    if os.path.exists(os.path.join (dir, "nsServiceManagerUtils.h")):
        nsI = False
        break

if nsI:
    mozilla_browser_options['extra_compile_args'].append('-DNS_I_SERVICE_MANAGER_UTILS=1')

mozilla_browser_ext = Extension("miro.MozillaBrowser",
        [ os.path.join(frontend_implementation_dir,'MozillaBrowser.pyx'),
          os.path.join(frontend_implementation_dir,'MozillaBrowserXPCOM.cc'),
          os.path.join(frontend_implementation_dir,'HttpObserver.cc'),
          os.path.join(frontend_implementation_dir,'PromptService.cc'),
          os.path.join(frontend_implementation_dir,'DragAndDrop.cc'),
          os.path.join(frontend_implementation_dir,'XPCOMUtil.cc'),
        ],
        runtime_library_dirs=mozilla_lib_path,
        **mozilla_browser_options)
#### Xlib Extension ####
xlib_ext = \
    Extension("miro.xlibhelper", 
        [ os.path.join(frontend_implementation_dir,'xlibhelper.pyx') ],
        library_dirs = ['/usr/X11R6/lib'],
        libraries = ['X11'],
    )

#### Xine Extension ####
xine_options = parsePkgConfig('pkg-config', 
        'libxine pygtk-2.0 gtk+-2.0 glib-2.0 gthread-2.0')

# If you get XINE crashes, uncommenting this might fix it. It's
# necessary on Debian Etch and Ubuntu Feisty right now.
#
# We have a horrible workaround for buggy X drivers in xine_impl.c
# controled by this variable
if USE_XINE_HACK:
    print "Using the Xine driver hack. If you experience trouble playing video,\n   try setting USE_XINE_HACK to False in setup.py."
    if xine_options.has_key('define_macros'):
        xine_options['define_macros'].append(('INCLUDE_XINE_DRIVER_HACK', '1'))
    else:
        xine_options['define_macros'] = [('INCLUDE_XINE_DRIVER_HACK', '1')]
xine_ext = Extension('miro.xine', [
                         os.path.join(xine_dir, 'xine.pyx'),
                         os.path.join(xine_dir, 'xine_impl.c'),],
                     **xine_options)

#### Build the data_files list ####
def listfiles(path):
    return [f for f in glob(os.path.join(path, '*')) if os.path.isfile(f)]
data_files = []
# append the root resource directory.
# filter out app.config.template (which is handled specially)
files = [f for f in listfiles(resource_dir) \
        if os.path.basename(f) != 'app.config.template']
files.extend(listfiles(os.path.join(glade_dir, 'pixmaps')))
files.append(os.path.join(glade_dir, 'miro.glade'))
data_files.append(('/usr/share/miro/resources/', files))
# handle the sub directories.
for dir in ('templates', 'css', 'images', 'html', 'testdata', os.path.join('templates','unittest'), 'searchengines'):
    source_dir = os.path.join(resource_dir, dir)
    dest_dir = os.path.join('/usr/share/miro/resources/', dir)
    data_files.append((dest_dir, listfiles(source_dir)))
# add the desktop file, icons, mime data, and man page.

if not "clean" in sys.argv:
    rv = os.system ("gcc %s -o %s `pkg-config --libs --cflags gdk-pixbuf-2.0 glib-2.0 libxine`" % (os.path.join(platform_dir, "xine/xine_extractor.c"), os.path.join(platform_dir, "xine/xine_extractor")))

    if rv != 0:
        raise RuntimeError("xine_extractor compilation failed.  Possibly missing libxine, gdk-pixbuf-2.0, or glib-2.0.")

data_files += [
    ('/usr/share/pixmaps', 
     glob(os.path.join(platform_dir, 'miro-*.png'))),
    ('/usr/share/applications', 
     [os.path.join(platform_dir, 'miro.desktop')]),
    ('/usr/share/mime/packages', 
     [os.path.join(platform_dir, 'miro.xml')]),
    ('/usr/share/man/man1',
     [os.path.join(platform_dir, 'miro.1.gz')]),
    ('/usr/libexec/',
     [os.path.join(platform_dir, 'xine/xine_extractor')]),
]

os.system ("gzip -9 < " + os.path.join(platform_dir, 'miro.1') + " > " + os.path.join(platform_dir, 'miro.1.gz'))

#### Our specialized install_data command ####
class install_data (distutils.command.install_data.install_data):
    """install_data extends to default implementation so that it automatically
    installs app.config from app.config.template.
    """

    def install_app_config(self):
        source = os.path.join(resource_dir, 'app.config.template')
        dest = '/usr/share/miro/resources/app.config'
        revision = util.queryRevision(root_dir)
        if revision is None:
            revision = "unknown"
            revisionurl = "unknown"
            revisionnum = "unknown"
        else:
            revisionurl = revision[0]
            revisionnum = revision[1]
            revision = "%s - %s" % revision
        if self.root:
            dest = change_root(self.root, dest)
        self.mkpath(os.path.dirname(dest))
        # We don't use the dist utils copy_file() because it only copies
        # the file if the timestamp is newer
        shutil.copyfile(source,dest)
        expand_file_contents(dest, APP_REVISION=revision,
                             APP_REVISION_NUM=revisionnum,
                             APP_REVISION_URL=revisionurl,
                             APP_PLATFORM='gtk-x11',
                             BUILD_MACHINE="%s@%s" % (getlogin(),
                                                      os.uname()[1]),
                             BUILD_TIME=str(time.time()),
                             MOZILLA_LIB_PATH=mozilla_lib_path[0])
        self.outfiles.append(dest)

        locale_dir = os.path.join (resource_dir, "locale")

        for source in glob (os.path.join (locale_dir, "*.mo")):
            lang = os.path.basename(source)[:-3]
            dest = '/usr/share/locale/%s/LC_MESSAGES/miro.mo' % lang
            if self.root:
                dest = change_root(self.root, dest)
            self.mkpath(os.path.dirname(dest))
            self.copy_file(source, dest)
            self.outfiles.append(dest)

    def run(self):
        distutils.command.install_data.install_data.run(self)
        self.install_app_config()

#### Our specialized build_py command ####
class build_py (distutils.command.build_py.build_py):
    """build_py extends the default build_py implementation so that the
    platform and portable directories get merged into the miro
    package.
    """

    def expand_templates(self):
        conf = util.readSimpleConfigFile(app_config)
        for path in [os.path.join(portable_dir,'dl_daemon','daemon.py')]:
            template = Template(read_file(path+".template"))
            expanded = template.substitute(**conf)
            write_file(path, expanded)
        
    def find_miro_modules(self):
        """Returns a list of modules to go in the miro directory.  Each
        item has the form (package, module, path).  The trick here is merging
        the contents of the platform/gtk-x11 and portable directories.
        """
        self.expand_templates()
        files = glob(os.path.join(portable_dir, '*.py'))
        files.extend(glob(os.path.join(platform_dir, '*.py')))
        rv = []
        for f in files:
            if os.path.samefile(f, __file__):
                continue
            module = os.path.splitext(os.path.basename(f))[0]
            rv.append(('miro', module, f))
        return rv

    def find_all_modules (self):
        """Extend build_py's module list to include the miro modules."""
        modules = distutils.command.build_py.build_py.find_all_modules(self)
        modules.extend(self.find_miro_modules())
        return modules

    def run(self):
        """Do the build work.  In addition to the default implementation, we
        also build the miro package from the platform and portable code
        and install the resources as package data.  
        """

        for (package, module, module_file) in self.find_miro_modules():
            assert package == 'miro'
            self.build_module(module, module_file, package)
        return distutils.command.build_py.build_py.run(self)

#### bdist_deb builds the miro debian package ####
class bdist_deb (Command):

    description = "Create a deb package"
    user_options = [ ]

    def initialize_options (self):
        pass

    def finalize_options (self):
        bdist_base = self.get_finalized_command('bdist').bdist_base
        self.bdist_dir = os.path.join(bdist_base, 'deb')
        self.dist_dir = self.get_finalized_command('bdist').dist_dir

    def run (self):
        # buzild all python modules/extensions
        self.run_command('build')
        # copy the built files
        install = self.reinitialize_command('install', reinit_subcommands=1)
        install.root = self.bdist_dir
        install.skip_build = 1
        install.warn_dir = 0
        install.compile = 0
        install.optimize = 0
        log.info("installing to %s" % self.bdist_dir)
        self.run_command('install')
        # strip all extension modules
        extensions = []
        for path, dir, files in os.walk(self.bdist_dir):
            for f in files:
                if f.endswith('.so'):
                    extensions.append(os.path.join(path, f))
        for path in extensions:
            log.info('stripping %s' % path)
            os.system('strip %s' % path)
        # calculate the dependancies for extension modules
        cmd = 'dpkg-shlibdeps -O %s' % ' '.join(extensions)
        extension_deps = getCommandOutput(cmd, warnOnStderr=False).strip()
        extension_deps = extension_deps.replace('shlibs:Depends=', '')
        # copy over the debian package files
        debian_source = os.path.join(debian_package_dir, 'DEBIAN')
        debian_dest = os.path.join(self.bdist_dir, 'DEBIAN')
        self.copy_tree(debian_source, debian_dest)
        # Fill in the version number in the control file
        expand_file_contents(os.path.join(debian_dest, 'control'),
                VERSION=self.distribution.get_version(),
                EXTENSION_DEPS=extension_deps)
        # copy the copyright file
        copyright_source = os.path.join(debian_package_dir, 'copyright')
        copyright_dest = os.path.join(self.bdist_dir, 'usr', 'share', 'doc', 
                    'python-democracy-player')
        self.mkpath(copyright_dest)
        self.copy_file(copyright_source, copyright_dest)
        # ensure the dist directory is around
        self.mkpath(self.dist_dir)
        # create the debian package
        package_basename = "miro_%s_i386.deb" % \
                self.distribution.get_version()
        package_path  = os.path.join(self.dist_dir, package_basename)
        dpkg_command = "fakeroot dpkg --build %s %s" % (self.bdist_dir, 
                package_path)
        log.info("running %s" % dpkg_command)
        os.system(dpkg_command)
        dir_util.remove_tree(self.bdist_dir)

#### install_theme installs a specifified theme .zip
class install_theme(Command):

    description = 'Install a provided theme to /usr/share/miro/themes'
    user_options = [("theme=", None, 'ZIP file containing the theme')]

    def initialize_options(self):
        self.theme = None

    def finalize_options(self):
        if self.theme is None:
            raise DistutilsOptionError, "must supply a theme ZIP file"
        if not os.path.exists(self.theme):
            raise DistutilsOptionError, "theme file does not exist"
        import zipfile
        if not zipfile.is_zipfile(self.theme):
            raise DistutilsOptionError, "theme file is not a ZIP file"
        zf = zipfile.ZipFile(self.theme)
        appConfig = zf.read('app.config')
        themeName = None
        for line in appConfig.split('\n'):
            if '=' in line:
                name, value = line.split('=', 1)
                name = name.strip()
                value = value.lstrip()
                if name == 'themeName':
                    themeName = value
        if themeName is None:
            raise DistutilsOptionError, "invalid theme file"
        self.zipfile = zf
        self.theme_name = themeName
        self.theme_dir = '/usr/share/miro/themes/%s' % themeName

    def run(self):
        if os.path.exists(self.theme_dir):
            shutil.rmtree(self.theme_dir)
        os.makedirs(self.theme_dir)
        for name in self.zipfile.namelist():
            if name.startswith('xul/'):
                # ignore XUL stuff, we don't need it on linux
                continue
            print 'installing', os.path.join(self.theme_dir, name)
            if name[-1] == '/':
                os.makedirs(os.path.join(self.theme_dir, name))
            else:
                f = file(os.path.join(self.theme_dir, name), 'wb')
                f.write(self.zipfile.read(name))
                f.close()
        print """%s theme installed.

To use this theme, run:

    miro --theme="%s"
""" % (self.theme_name, self.theme_name)

#print "IS_FILE: %s" % repr(os.path.isfile(os.path.join(platform_dir, "miro.real")))

#### Run setup ####
setup(name='miro', 
    version=appVersion,
    author='Participatory Culture Foundation',
    author_email='feedback@pculture.org',
    url='http://www.getmiro.com/',
    download_url='http://www.getmiro.com/downloads/',
    scripts = [
        os.path.join(platform_dir, 'miro'), 
        os.path.join(platform_dir, 'miro.real')
    ],
    data_files=data_files,
    ext_modules = [
        fasttypes_ext, mozilla_browser_ext, xine_ext, xlib_ext, libtorrent_ext,
        Extension("miro.database", 
                [os.path.join(portable_dir, 'database.pyx')]),
        Extension("miro.sorts", 
                [os.path.join(portable_dir, 'sorts.pyx')]),
        #Extension("miro.template", 
        #        [os.path.join(portable_dir, 'template.pyx')]),
    ],
    packages = [
        'miro.frontend_implementation',
        'miro.dl_daemon',
        'miro.test',
        'miro.compiled_templates',
        'miro.compiled_templates.unittest',
        'miro.dl_daemon.private',
        'miro.frontends',
        'miro.frontends.html',
        'miro.miroplatform',
        'miro.miroplatform.frontends',
        'miro.miroplatform.frontends.html',
    ],
    package_dir = {
        'miro.frontends': portable_frontend_dir,
        'miro.frontends.html': portable_html_frontend_dir,
        'miro.frontend_implementation' : frontend_implementation_dir,
        'miro.dl_daemon' : dl_daemon_dir,
        'miro.test' : test_dir,
        'miro.compiled_templates' : compiled_templates_dir,
        'miro.compiled_templates.unittest' : compiled_templates_unittest_dir,
        'miro.miroplatform': miroplatform_dir,
    },
    cmdclass = {
        'build_ext': build_ext, 
        'build_py': build_py,
        'bdist_deb': bdist_deb,
        'install_data': install_data,
        'install_theme': install_theme,
    }
)

