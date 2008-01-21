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
import shutil
from miro.platform import resources
import gconf

def upgrade():
    # dot directory
    src = os.path.expanduser('~/.democracy')
    dst = os.path.expanduser('~/.miro')
    if os.path.isdir(src) and not os.path.exists(dst):
        shutil.move(src, dst)
        shutil.rmtree(os.path.join(dst, "icon-cache"), True)

    # autostart file
    config_home = os.environ.get ('XDG_CONFIG_HOME',
                                  '~/.config')
    config_home = os.path.expanduser (config_home)
    autostart_dir = os.path.join (config_home, "autostart")
    old_file = os.path.join (autostart_dir, "democracyplayer.desktop")
    destination = os.path.join (autostart_dir, "miro.desktop")
    if os.path.exists(old_file):
        if not os.path.exists(destination):
            try:
                os.makedirs(autostart_dir)
            except:
                pass
            try:
                shutil.copy (resources.sharePath('applications/miro.desktop'), destination)
            except:
                pass
            try: 
                os.remove (old_file)
            except:
                pass

    # gconf settings

    client = gconf.client_get_default()

    def _copy_gconf(src, dst):
        for entry in client.all_entries(src):
            entry_dst = dst + '/' + entry.key.split('/')[-1]
            client.set(entry_dst, entry.value)
        for subdir in client.all_dirs(src):
            subdir_dst = dst + '/' + subdir.split('/')[-1]
            _copy_gconf (subdir, subdir_dst)

    if client.dir_exists ("/apps/democracy/player") and not client.dir_exists ("/apps/miro"):
        _copy_gconf("/apps/democracy/player", "/apps/miro")
        client.recursive_unset("/apps/democracy", 1)
        if client.get("/apps/miro/MoviesDirectory") is None:
            value = os.path.expanduser('~/Movies/Democracy')
            client.set_string("/apps/miro/MoviesDirectory", value)
            try:
                os.makedirs (value)
            except:
                pass
