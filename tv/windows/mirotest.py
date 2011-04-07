# Miro - an RSS based video player application
# Copyright (C) 2005-2010 Participatory Culture Foundation
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

"""Miro test utility -- console application for running unit tests.
"""

import sys
import logging

from miro.plat import utils
utils.initialize_locale()

from miro import gtcache
gtcache.init()

if "-v" not in sys.argv:
    logging.basicConfig(level=logging.CRITICAL)

if '--pydevd' in sys.argv:
    sys.path.append(r"E:\shi_lab\miro-groups\eclipse\dropins\plugins\org.python.pydev.debug_1.6.5.2011020317\pysrc")
    import pydevd
    pydevd.settrace()
    sys.argv.remove('--pydevd')

from miro import test
from miro.plat import resources

sys.path.append(resources.appRoot())
test.run_tests()
