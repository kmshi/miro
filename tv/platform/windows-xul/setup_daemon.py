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
import sys
import shutil
import setup as core_setup
from distutils.core import setup
from distutils.extension import Extension
import py2exe
from Pyrex.Distutils import build_ext

# when we install the portable modules, they will be in the miro package, but
# at this point, they are in a package named "portable", so let's hack it
#import portable
#sys.modules['miro'] = portable

root = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), '..', '..')
root = os.path.normpath(root)

from miro import util

ext_modules=[
        core_setup.libtorrent_ext,
]

templateVars = util.readSimpleConfigFile(os.path.join(root, 'resources', 'app.config'))

setup(
    console=[{"dest_base":("%s_Downloader"%templateVars['shortAppName']),"script":os.path.join(root, 'portable', 'dl_daemon', 'Democracy_Downloader.py')}],
    ext_modules=ext_modules,
    packages = [
        'miro',
        'miro.dl_daemon',
        'miro.dl_daemon.private',
        'miro.platform',
    ],
    package_dir = {
        'miro': core_setup.portable_dir,
        'miro.platform': os.path.join(core_setup.platform_dir, 'platform'),
    },
    cmdclass = {
	'build_ext': build_ext,
    },
)
