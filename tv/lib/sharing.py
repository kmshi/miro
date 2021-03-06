# Miro - an RSS based video player application
# Copyright (C) 2010 Participatory Culture Foundation
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

import errno
import logging
import os
import sys
import socket
import select
import struct
import threading
import time
import traceback
import uuid

from datetime import datetime
from hashlib import md5

from miro.gtcache import gettext as _
from miro import app
from miro import eventloop
from miro import messages
from miro import playlist
from miro import prefs
from miro import signals
from miro import filetypes
from miro import util
from miro import transcode
from miro import metadata
from miro.fileobject import FilenameType
from miro.util import returns_filename

from miro.plat import resources
from miro.plat.utils import thread_body

try:
    import libdaap
except ImportError:
    from miro import libdaap

DAAP_META = ('dmap.itemkind,dmap.itemid,dmap.itemname,' +
             'dmap.containeritemid,dmap.parentcontainerid,' +
             'daap.songtime,daap.songsize,daap.songformat,' +
             'daap.songartist,daap.songalbum,daap.songgenre,' +
             'daap.songyear,daap.songtracknumber,daap.songuserrating,' +
             'org.participatoryculture.miro.itemkind,' +
             'com.apple.itunes.mediakind')

supported_filetypes = filetypes.VIDEO_EXTENSIONS + filetypes.AUDIO_EXTENSIONS

# Conversion factor between our local duration (10th of a second)
# vs daap which is millisecond.
DURATION_SCALE = 1000

MIRO_ITEMKIND_MOVIE = (1 << 0)
MIRO_ITEMKIND_PODCAST = (1 << 1)
MIRO_ITEMKIND_SHOW = (1 << 2)
MIRO_ITEMKIND_CLIP = (1 << 3)

miro_itemkind_mapping = {
    'movie': MIRO_ITEMKIND_MOVIE,
    'show': MIRO_ITEMKIND_SHOW,
    'clip': MIRO_ITEMKIND_CLIP,
    'podcast': MIRO_ITEMKIND_PODCAST
}

miro_itemkind_rmapping = {
    MIRO_ITEMKIND_MOVIE: 'movie',
    MIRO_ITEMKIND_SHOW: 'show',
    MIRO_ITEMKIND_CLIP: 'clip',
    MIRO_ITEMKIND_PODCAST: 'podcast'
}

# XXX The daap mapping from the daap to the attribute is different from the
# reverse mapping, because we use daap_mapping to import items from remote
# side and we use daap_rmapping to create an export list.  But, when
# we import and create SharingItem, the attribut needs to be 'title'.  But
# when we export, we receive ItemInfo(), which uses 'name'.
daap_mapping = {
    'daap.songformat': 'file_format',
    'com.apple.itunes.mediakind': 'file_type',
    'dmap.itemid': 'id',
    'dmap.itemname': 'title',
    'daap.songtime': 'duration',
    'daap.songsize': 'size',
    'daap.songartist': 'artist',
    'daap.songalbumartist': 'album_artist',
    'daap.songalbum': 'album',
    'daap.songyear': 'year',
    'daap.songgenre': 'genre',
    'daap.songtracknumber': 'track',
    'org.participatoryculture.miro.itemkind': 'kind',
    'com.apple.itunes.series-name': 'show',
    'com.apple.itunes.season-num': 'season_number',
    'com.apple.itunes.episode-num-str': 'episode_id',
    'com.apple.itunes.episode-sort': 'episode_number'
}

daap_rmapping = {
    'file_format': 'daap.songformat',
    'file_type': 'com.apple.itunes.mediakind',
    'id': 'dmap.itemid',
    'name': 'dmap.itemname',
    'duration': 'daap.songtime',
    'size': 'daap.songsize',
    'artist': 'daap.songartist',
    'album_artist': 'daap.songalbumartist',
    'album': 'daap.songalbum',
    'year': 'daap.songyear',
    'genre': 'daap.songgenre',
    'track': 'daap.songtracknumber',
    'kind': 'org.participatoryculture.miro.itemkind',
    'show': 'com.apple.itunes.series-name',
    'season_number': 'com.apple.itunes.season-num',
    'episode_id': 'com.apple.itunes.episode-num-str',
    'episode_number': 'com.apple.itunes.episode-sort'
}

# Windows Python does not have inet_ntop().  Sigh.  Fallback to this one,
# which isn't as good, if we do not have access to it.
def inet_ntop(af, ip):
    try:
        return socket.inet_ntop(af, ip)
    except AttributeError:
        if af == socket.AF_INET:
            return socket.inet_ntoa(ip)
        if af == socket.AF_INET6:
            return ':'.join('%x' % bit for bit in struct.unpack('!' + 'H' * 8,
                                                                ip))
        raise ValueError('unknown address family %d' % af)

class SharingItem(metadata.Source):
    """
    An item which lives on a remote share.
    """
    def __init__(self, **kwargs):
        for required in ('video_path', 'id', 'file_type', 'host', 'port'):
            if required not in kwargs:
                raise TypeError('SharingItem must be given a "%s" argument'
                                % required)
        self.file_format = self.size = None
        self.release_date = self.feed_name = self.feed_id = None
        self.keep = True
        self.isContainerItem = False
        self.url = self.payment_link = None
        self.comments_link = self.permalink = self.file_url = None
        self.license = self.downloader = None
        self.duration = self.screenshot = self.thumbnail_url = None
        self.resumeTime = 0
        self.description = u''
        self.subtitle_encoding = self.enclosure_type = None
        self.metadata_version = 0
        self.file_type = None
        self.creation_time = None

        metadata.Source.setup_new(self)

        self.__dict__.update(kwargs)

        self.video_path = FilenameType(self.video_path)
        if self.title is None:
            self.title = _("Unknown")
        # Do we care about file_format?
        if self.file_format is None:
            pass
        if self.size is None:
            self.size = 0
        if self.release_date is None or self.creation_time is None:
            now = time.time()
            if self.release_date is None:
                self.release_date = now
            if self.creation_time is None:
                self.creation_time = now
        if self.duration is None: # -1 is unknown
            self.duration = 0

    @staticmethod
    def id_exists():
        return True

    def get_release_date(self):
        try:
            return datetime.fromtimestamp(self.release_date)
        except ValueError:
            logging.warn('SharingItem: release date time %s invalid' %
                          self.release_date)
            return datetime.now()

    def get_creation_time(self):
        try:
            return datetime.fromtimestamp(self.creation_time)
        except ValueError:
            logging.warn('SharingItem: creation time %s invalid' %
                          self.creation_time)
            return datetime.now()

    @returns_filename
    def get_filename(self):
        # For daap, sent it to be the same as http as it is basically
        # http with a different port.
        def daap_handler(path, host, port):
            return 'http://%s:%s%s' % (host, port, path)
        fn = FilenameType(self.video_path)
        fn.set_urlize_handler(daap_handler, [self.address, self.port])
        return fn

    def get_url(self):
        return self.url or u''

    @returns_filename
    def get_thumbnail(self):
        # What about cover art?
        if self.file_type == 'audio':
            return resources.path("images/thumb-default-audio.png")
        else:
            return resources.path("images/thumb-default-video.png")

    def _migrate_thumbnail(self):
        # This should not ever do anything useful.  We don't have a backing
        # database to safe this stuff.
        pass

    def drm_description(self):
        if self.has_drm:
            return _("Locked")
        else:
            return u""

    def remove(self, save=True):
        # This should never do anything useful, we don't have a backing
        # database. Yet.
        pass

class SharingTracker(object):
    """The sharing tracker is responsible for listening for available music
    shares and the main client connection code.  For each connected share,
    there is a separate SharingItemTrackerImpl() instance which is basically
    a backend for messagehandler.SharingItemTracker().
    """
    type = u'sharing'
    # These need to be the same size.
    CMD_QUIT = 'quit'
    CMD_PAUSE = 'paus'
    CMD_RESUME = 'resm'

    def __init__(self):
        self.name_to_id_map = dict()
        self.trackers = dict()
        self.available_shares = dict()
        self.r, self.w = util.make_dummy_socket_pair()
        self.paused = True
        self.event = threading.Event()
        libdaap.register_meta('org.participatoryculture.miro.itemkind', 'miKD',
                              libdaap.DMAP_TYPE_UBYTE)

    def mdns_callback(self, added, fullname, host, port):
        eventloop.add_urgent_call(self.mdns_callback_backend, "mdns callback",
                                  args=[added, fullname, host, port])

    def try_to_add(self, share_id, fullname, host, port, uuid):
        def success(unused):
            if self.available_shares.has_key(share_id):
                info = self.available_shares[share_id]
            else:
                info = None
            # It's been deleted or worse, deleted and recreated!
            if not info or info.connect_uuid != uuid:
                return
            info.connect_uuid = None
            info.share_available = True
            messages.TabsChanged('connect', [info], [], []).send_to_frontend()

        def failure(unused):
            if self.available_shares.has_key(share_id):
                info = self.available_shares[share_id]
            else:
                info = None
            if not info or info.connect_uuid != uuid:
                return
            info.connect_uuid = None

        def testconnect():
            client = libdaap.make_daap_client(host, port)
            if not client.connect() or client.databases() is None:
                raise IOError('test connect failed')
            client.disconnect()

        eventloop.call_in_thread(success,
                                 failure,
                                 testconnect,
                                 'DAAP test connect')

    def mdns_callback_backend(self, added, fullname, host, port):
        if fullname == app.sharing_manager.name:
            return
        # Need to come up with a unique ID for the share.  We want to use the 
        # name only since that's supposed to be unique, but can't because
        # the name may change, and the id is used throughout to identify
        # the item tracker, and we don't want to change the id mid-way.
        # We can't use the hostname or port directly also because
        # on removal avahi can't do a name query so we have no hostname,
        # or port information!  So, we have a name to id map.
        if added:
            share_id = (host, port)
            self.name_to_id_map[fullname] = share_id
        else:
            try:
                share_id = self.name_to_id_map[fullname]
                del self.name_to_id_map[fullname]
                if share_id in self.name_to_id_map.values():
                    logging.debug('sharing: out of order add/remove during '
                                  'rename?')
                    return
            except KeyError:
                # If it doesn't exist then it's been taken care of so return.
                logging.debug('KeyError: name %s', fullname)
                return

        logging.debug(('gotten mdns callback share_id, added = %s '
                       ' fullname = %s host = %s port = %s'),
                      added, fullname, host, port)

        if added:
            # This added message could be just because the share name got
            # changed.  And if that's the case, see if the share's connected.
            # If it is not connected, it must have been removed from the
            # sidebar so we can add as normal.  If it was connected, make
            # sure we change the name of it, and just skip over adding the 
            # tab..  We don't do this if the share's not a connected one
            # because the remove/add sequence, there's no way to tell if the
            # share's just going away or not.
            #
            # Else, create the SharingInfo eagerly, so that duplicate messages
            # can use it to filter out.  We also create a unique stamp on it,
            # in case of errant implementations that try to register, delete,
            # and re-register the share.  The try_to_add() success/failure
            # callback can check whether info is still valid and if so, if it
            # is this particular info (if not, the uuid will be different and
            # and so should ignore).
            has_key = False
            for info in self.available_shares.values():
                if info.mount and info.host == host and info.port == port:
                    has_key = True
                    break
            if has_key:
                if info.stale_callback:
                    info.stale_callback.cancel()
                    info.stale_callback = None
                info.name = fullname
                message = messages.TabsChanged('connect', [], [info], [])
                message.send_to_frontend()
            else:
                # If the share has already been previously added, update the
                # fullname, and ensure it is not stale.  Furthermore, if
                # this share is actually displayed, then change the tab.
                if share_id in self.available_shares.keys():
                    info = self.available_shares[share_id]
                    info.name = fullname
                    if info.share_available:
                        logging.debug('Share already registered and '
                                      'available, sending TabsChanged only')
                        if info.stale_callback:
                            info.stale_callback.cancel()
                            info.stale_callback = None
                        message = messages.TabsChanged('connect', [],
                                                       [info], [])
                        message.send_to_frontend()
                    return
                info = messages.SharingInfo(share_id, fullname, host, port)
                info.connect_uuid = uuid.uuid4()
                self.available_shares[share_id] = info
                self.try_to_add(share_id, fullname, host, port,
                                    info.connect_uuid)
        else:
            # The mDNS publish is going away.  Are we connected?  If we
            # are connected, keep it around.  If not, make it disappear.
            # SharingDisappeared() kicks off the necessary bits in the 
            # frontend for us.
            if not share_id in self.trackers.keys():
                victim = self.available_shares[share_id]
                del self.available_shares[share_id]
                # Only tell the frontend if the share's been tested because
                # otherwise the TabsChanged() message wouldn't have arrived.
                if victim.connect_uuid is None:
                    messages.SharingDisappeared(victim).send_to_frontend()
            else:
                # We don't know if the share's alive or not... what to do
                # here?  Let's add a timeout of 2 secs, if no added message
                # comes in, assume it's gone bye...
                share_info = self.available_shares[share_id]
                share = self.trackers[share_id]
                if share.share != share_info:
                    logging.error('Share disconn error: share info != share')
                dc = eventloop.add_timeout(2, self.remove_timeout_callback,
                                      "share tab removal timeout callback",
                                      args=(share_id, share_info))
                # Cancel pending callback is there is one.
                if share.share.stale_callback:
                    share.share.stale_callback.cancel()
                share.share.stale_callback = dc

    def remove_timeout_callback(self, share_id, share_info):
        del self.available_shares[share_id]
        messages.SharingDisappeared(share_info).send_to_frontend()

    def server_thread(self):
        # Wait for the resume message from the sharing manager as 
        # startup protocol of this thread.
        while True:
            try:
                r, w, x = select.select([self.r], [], [])
                if self.r in r:
                    cmd = self.r.recv(4)
                    if cmd == SharingTracker.CMD_RESUME:
                        self.paused = False
                        break
                    # User quit very quickly.
                    elif cmd == SharingTracker.CMD_QUIT:
                        return
                    raise ValueError('bad startup message received')
            except select.error, (err, errstring):
                if err == errno.EINTR:
                    continue
            except StandardError, err:
                raise ValueError('unknown error during select %s' % str(err))

        if app.sharing_manager.mdns_present:
            callback = libdaap.mdns_browse(self.mdns_callback)
        else:
            callback = None
        while True:
            refs = []
            if callback is not None and not self.paused:
                refs = callback.get_refs()
            try:
                # Once we get a shutdown signal (from self.r/self.w socketpair)
                # we return immediately.  I think this is okay since we are 
                # passive listener and we only stop tracking on shutdown,
                #  OS will help us close all outstanding sockets including that
                # for this listener when this process terminates.
                r, w, x = select.select(refs + [self.r], [], [])
                if self.r in r:
                    cmd = self.r.recv(4)
                    if cmd == SharingTracker.CMD_QUIT:
                        return
                    if cmd == SharingTracker.CMD_PAUSE:
                        self.paused = True
                        self.event.set()
                        continue
                    if cmd == SharingTracker.CMD_RESUME:
                        self.paused = False
                        continue
                    raise
                for i in r:
                    if i in refs:
                        callback(i)
            # XXX what to do in case of error?  How to pass back to user?
            except select.error, (err, errstring):
                if err == errno.EINTR:
                    continue
                else:
                    pass
            except StandardError:
                pass

    def start_tracking(self):
        # sigh.  New thread.  Unfortunately it's kind of hard to integrate
        # it into the application runloop at this moment ...
        self.thread = threading.Thread(target=thread_body,
                                       args=[self.server_thread],
                                       name='mDNS Browser Thread')
        self.thread.start()

    def eject(self, share_id):
        tracker = self.trackers[share_id]
        del self.trackers[share_id]
        tracker.client_disconnect()

    def get_tracker(self, share_id):
        try:
            return self.trackers[share_id]
        except KeyError:
            logging.debug('sharing: creating new tracker')
            share = self.available_shares[share_id]
            self.trackers[share_id] = SharingItemTrackerImpl(share)
            return self.trackers[share_id]

    def stop_tracking(self):
        # What to do in case of socket error here?
        self.w.send(SharingTracker.CMD_QUIT)

    # pause/resume is only meant to be used by the sharing manager.
    # Pause needs to be synchronous because we want to make sure this module
    # is in a quiescent state.
    def pause(self):
        # What to do in case of socket error here?
        self.w.send(SharingTracker.CMD_PAUSE)
        self.event.wait()
        self.event.clear()

    def resume(self):
        # What to do in case of socket error here?
        self.w.send(SharingTracker.CMD_RESUME)

# Synchronization issues: this code is a bit sneaky, so here is an explanation
# of how it works.  When you click on a share tab in the frontend, the 
# display (the item list controller) starts tracking the items.  It does
# so by sending a message to the backend.  If it was previously unconnected
# a new SharingItemTrackerImpl() will be created, and connect() is called,
# which may take an indeterminate period of time, so this is farmed off
# to an external thread.  When the connection is successful, a callback will
# be called which is run on the backend (eventloop) thread which adds the
# items and playlists to the SharingItemTrackerImpl tracker object. 
# At the same time, handle_item_list() is called after the tracker is created
# which will be empty at this time, because the items have not yet been added.
# (recall that the callback runs in the eventloop, we are already in the 
# eventloop so this could not have happened prior to handle_item_list()
# being called).
#
# The SharingItemTrackerImpl() object is designed to be persistent until
# disconnection happens.  If you click on a tab that's already connected,
# it finds the appropriate tracker and calls handle_item_list.  Either it is
# already populated, or if connection is still in process will return empty
# list until the connection success callback is called.
class SharingItemTrackerImpl(signals.SignalEmitter):
    """This is the backend for the SharingItemTracker the messagehandler file.
    This backend class allows the item tracker to be persistent even as the
    user switches across different tabs in the sidebar, until the disconnect
    button is clicked.
    """
    type = u'sharing'
    def __init__(self, share):
        self.client = None
        self.share = share
        self.items = dict()
        self.info_cache = dict()
        self.playlists = []
        self.base_playlist = None    # Temporary
        self.share.is_updating = True
        message = messages.TabsChanged('connect', [], [self.share], [])
        message.send_to_frontend()
        eventloop.call_in_thread(self.client_connect_callback,
                                 self.client_connect_error_callback,
                                 self.client_connect,
                                 'DAAP client connect')
        signals.SignalEmitter.__init__(self)
        for sig in 'added', 'changed', 'removed':
            self.create_signal(sig)

    def sharing_item(self, rawitem):
        kwargs = dict()
        for k in rawitem.keys():
            try:
                key = daap_mapping[k]
            except KeyError:
                # Got something back we don't really care about.
                continue
            kwargs[key] = rawitem[k]
            if isinstance(rawitem[k], str):
                kwargs[key] = kwargs[key].decode('utf-8')

        try:
            kwargs['kind'] = miro_itemkind_rmapping[kwargs['kind']]
        except KeyError:
            pass

        # Fix this up.
        file_type = u'audio'    # fallback
        try:
            if kwargs['file_type'] == libdaap.DAAP_MEDIAKIND_AUDIO:
                file_type = u'audio'
            if kwargs['file_type'] in [libdaap.DAAP_MEDIAKIND_TV,
                                       libdaap.DAAP_MEDIAKIND_MOVIE,
                                       libdaap.DAAP_MEDIAKIND_VIDEO
                                      ]:
                file_type = u'video'
        except KeyError:
           # Whoups.  Server didn't send one over?  Assume default.
           pass

        kwargs['file_type'] = file_type
        kwargs['video_path'] = self.client.daap_get_file_request(
                                   kwargs['id'],
                                   kwargs['file_format'])
        kwargs['host'] = self.client.host
        kwargs['port'] = self.client.port
        kwargs['address'] = self.address
        kwargs['file_type'] = file_type

        # Duration: daap uses millisecond, so we need to scale it.
        if kwargs['duration'] is not None:
            kwargs['duration'] /= DURATION_SCALE

        sharing_item = SharingItem(**kwargs)
        return sharing_item

    def client_disconnect(self):
        client = self.client
        self.client = None
        playlist_ids = [playlist_.id for playlist_ in self.playlists]
        message = messages.TabsChanged('connect', [], [], playlist_ids)
        message.send_to_frontend()
        eventloop.call_in_thread(self.client_disconnect_callback,
                                 self.client_disconnect_error_callback,
                                 client.disconnect,
                                 'DAAP client connect')

    def client_disconnect_error_callback(self, unused):
        pass

    def client_disconnect_callback(self, unused):
        pass

    def client_connect(self):
        name = self.share.name
        host = self.share.host
        port = self.share.port
        self.client = libdaap.make_daap_client(host, port)
        if not self.client.connect():
            # XXX API does not allow us to send more detailed results
            # back to the poor user.
            raise IOError('Cannot connect')
        # XXX Dodgy: Windows name resolution sucks so we get a free ride
        # off the main connection with getpeername(), so we can use the IP
        # value to connect subsequently.   But we have to poke into the 
        # semi private data structure to get the socket structure.  
        # Lousy Windows and Python API.
        address, port = self.client.conn.sock.getpeername()
        self.address = address
        if not self.client.databases():
            raise IOError('Cannot get database')
        playlists = self.client.playlists()
        if playlists is None:
            raise IOError('Cannot get playlist')
        returned_playlists = []
        for k in playlists.keys():
            # Clean the playlist: remove NUL characters.
            for k_ in playlists[k]:
                if isinstance(playlists[k][k_], str):
                    tmp = playlists[k][k_]
                    playlists[k][k_] = tmp.replace('\x00', '')

            is_base_playlist = None
            if playlists[k].has_key('daap.baseplaylist'):
                is_base_playlist = playlists[k]['daap.baseplaylist']
            if is_base_playlist:
                if self.base_playlist:
                    logging.debug('WARNING: more than one base playlist found')
                self.base_playlist = k
            # This isn't the playlist id of the remote share, this is the
            # playlist id we use internally.
            # XXX is there anything better we can do than repr()?
            if not is_base_playlist:
                # XXX only add playlist if it not base playlist.  We don't
                # explicitly show base playlist.
                playlist_id = unicode(md5(repr((name,
                                                host,
                                                port, k))).hexdigest())
                info = messages.SharingInfo(playlist_id,
                                            playlists[k]['dmap.itemname'],
                                            host,
                                            port,
                                            parent_id=self.share.id,
                                            playlist_id=k)
                returned_playlists.append(info)
        video_playlist_id = unicode(md5(repr((name,
                                              host,
                                              port, u'video'))).hexdigest())
        audio_playlist_id = unicode(md5(repr((name,
                                              host,
                                              port, u'audio'))).hexdigest())
        video_info = messages.SharingInfo(video_playlist_id,
                                          u'video',
                                          host,
                                          port,
                                          parent_id=self.share.id,
                                          playlist_id=u'video')
        audio_info = messages.SharingInfo(audio_playlist_id,
                                          u'audio',
                                          host,
                                          port,
                                          parent_id=self.share.id,
                                          playlist_id=u'audio')
        # Place this stuff at the front
        returned_playlists.insert(0, audio_info)
        returned_playlists.insert(0, video_info)

        # Maybe we have looped through here without a base playlist.  Then
        # the server is broken?
        if not self.base_playlist:
            raise ValueError('Cannot find base playlist')

        items = self.client.items(playlist_id=self.base_playlist,
                                  meta=DAAP_META)
        if items is None:
            raise ValueError('Cannot find items in base playlist')

        itemdict = dict()
        returned_playlist_items = dict()
        returned_items = []
        video_items = []
        audio_items = []
        sharing_item_meth = self.sharing_item
        returned_items_meth = returned_items.append
        audio_items_meth = audio_items.append
        video_items_meth = video_items.append
        for itemkey in items.keys():
            # Clean it of NUL
            for k in items[itemkey]:
                if isinstance(items[itemkey][k], str):
                    tmp = items[itemkey][k]
                    items[itemkey][k] = tmp.replace('\x00', '')
            item = sharing_item_meth(items[itemkey])
            itemdict[itemkey] = item
            returned_items_meth(item)
            if item.file_type == u'video':
                video_items_meth(item)
            elif item.file_type == u'audio':
                audio_items_meth(item)
            else:
                logging.warn('item file type unrecognized %s', item.file_type)
        returned_playlist_items[u'video'] = video_items
        returned_playlist_items[u'audio'] = audio_items
        returned_playlist_items[self.base_playlist] = returned_items

        # Have to save the items from the base playlist first, because
        # Rhythmbox will get lazy and only send the ids around (expecting
        # us to already to have the data, I guess). 
        for k in playlists.keys():
            if k == self.base_playlist:
                continue
            returned_items = []
            returned_items_meth = returned_items.append
            items = self.client.items(playlist_id=k, meta=DAAP_META)
            if items is None:
                raise ValueError('Cannot find items for playlist %d' % k)
            for itemkey in items.keys():
                item = itemdict[itemkey]
                returned_items_meth(item)
            returned_playlist_items[k] = returned_items

        # We don't append these items directly to the object and let
        # the success callback to do it to prevent race.
        return (returned_playlist_items, returned_playlists)

    # NB: this runs in the eventloop (backend) thread.
    def client_connect_callback(self, args):
        returned_items, returned_playlists = args
        self.items = returned_items
        self.playlists = returned_playlists
        # Send a list of all the items to the main sharing tab.  Only add
        # those that are part of the base playlist.
        for item in self.items[self.base_playlist]:
            self.emit('added', item)
        # Once all the items are added then send display mounted and remove
        # the progress indicator.
        self.share.mount = True
        self.share.is_updating = False
        message = messages.TabsChanged('connect', self.playlists,
                                       [self.share], [])
        message.send_to_frontend()

    def client_connect_error_callback(self, unused):
        # If it didn't work, immediately disconnect ourselves.
        self.share.is_updating = False
        message = messages.TabsChanged('connect', [], [self.share], [])
        message.send_to_frontend()
        app.sharing_tracker.eject(self.share.id)
        messages.SharingConnectFailed(self.share).send_to_frontend()

    def get_items(self, playlist_id=None):
        # NB: keep this in a try/except construct because this could be
        # called before the connection actually has succeeded.
        try:
            if playlist_id is None:
                return self.items[self.base_playlist]
            else:
                return self.items[playlist_id]
        except KeyError:
            logging.error('Cannot get playlist, was looking for %s',
                          playlist_id)
            return []

class SharingManagerBackend(object):
    """SharingManagerBackend is the bridge between pydaap and Miro.  It
    pushes Miro media items to pydaap so pydaap can serve them to the outside
    world."""
    type = u'sharing-backend'
    id = u'sharing-backend'

    def __init__(self):
        self.share_types = []
        if app.config.get(prefs.SHARE_AUDIO):
            self.share_types += [libdaap.DAAP_MEDIAKIND_AUDIO]
        if app.config.get(prefs.SHARE_VIDEO):
            self.share_types += [libdaap.DAAP_MEDIAKIND_VIDEO]
        self.item_lock = threading.Lock()
        self.transcode_lock = threading.Lock()
        self.transcode = dict()
        # XXX daapplaylist should be hidden from view. 
        self.daapitems = dict()         # DAAP format XXX - index via the items
        self.daap_playlists = dict()    # Playlist, in daap format
        self.playlist_item_map = dict() # Playlist -> item mapping
        self.in_shutdown = False
        self.config_handle = app.backend_config_watcher.connect('changed',
                             self.on_config_changed)

    # Reserved for future use: you can register new sharing protocols here.
    def register_protos(self, proto):
        pass

    def handle_item_list(self, message):
        self.make_item_dict(message.items)

    def handle_items_changed(self, message):
        # If items are changed, overwrite with a recreated entry.  This
        # might not be necessary, as currently this change can be due to an 
        # item being moved out of, and then into, a playlist.  Also, based on 
        # message.id, change the playlists accordingly.
        with self.item_lock:
            for itemid in message.removed:
                try:
                    if message.id is not None:
                        self.playlist_item_map[message.id].remove(itemid)
                except KeyError:
                    pass
                try:
                    del self.daapitems[itemid]
                except KeyError:
                    pass
            if message.id is not None:
                item_ids = [item.id for item in message.added]
                self.playlist_item_map[message.id] += item_ids
            self.make_item_dict(message.added)
            self.make_item_dict(message.changed)

    def make_daap_playlists(self, items):
        for item in items:
            itemprop = dict()
            for attr in daap_rmapping.keys():
               daap_string = daap_rmapping[attr]
               itemprop[daap_string] = getattr(item, attr, None)
               # XXX Pants.
               if (daap_string == 'dmap.itemname' and
                 itemprop[daap_string] == None):
                   itemprop[daap_string] = getattr(item, 'title', None)
               if isinstance(itemprop[daap_string], unicode):
                   itemprop[daap_string] = (
                     itemprop[daap_string].encode('utf-8'))
            daap_string = 'dmap.itemcount'
            if daap_string == 'dmap.itemcount':
                # At this point, the item list has not been fully populated 
                # yet.  Therefore, it may not be possible to run 
                # get_items() and getting the count attribute.  Instead we 
                # use the playlist_item_map.
                tmp = [y for y in 
                       playlist.PlaylistItemMap.playlist_view(item.id)]
                count = len(tmp)
                itemprop[daap_string] = count
            daap_string = 'dmap.parentcontainerid'
            if daap_string == 'dmap.parentcontainerid':
                itemprop[daap_string] = 0
                #attributes.append(('mpco', 0)) # Parent container ID
                #attributes.append(('mimc', count))    # Item count
                #self.daap_playlists[x.id] = attributes
            daap_string = 'dmap.persistentid'
            if daap_string == 'dmap.persistentid':
                itemprop[daap_string] = item.id
            self.daap_playlists[item.id] = itemprop

    def handle_playlist_added(self, obj, added):
        playlists = [x for x in added if not x.is_folder]

        def _handle_playlist_added():
            with self.item_lock:
                self.make_daap_playlists(playlists)

        eventloop.add_urgent_call(lambda: _handle_playlist_added(),
                                  "SharingManagerBackend: playlist added")

    def handle_playlist_changed(self, obj, changed):
        def _handle_playlist_changed():
            with self.item_lock:
                # We could just overwrite everything without actually deleting
                # the object.  A missing key means it's a folder, and we skip
                # over it.
                for x in changed:
                    if self.daap_playlists.has_key(x.id):
                        del self.daap_playlists[x.id]
                playlist = [x for x in changed if not x.is_folder]
                self.make_daap_playlists(playlist)

        eventloop.add_urgent_call(lambda: _handle_playlist_changed(),
                                  "SharingManagerBackend: playlist changed")


    def handle_playlist_removed(self, obj, removed):
        def _handle_playlist_removed():
            with self.item_lock:
                for x in removed:
                    # Missing key means it's a folder and we skip over it.
                    if self.daap_playlists.has_key(x):
                        del self.daap_playlists[x]

        eventloop.add_urgent_call(lambda: _handle_playlist_removed(),
                                  "SharingManagerBackend: playlist removed")

    def populate_playlists(self):
        with self.item_lock:
            self.make_daap_playlists(playlist.SavedPlaylist.make_view())
            for playlist_id in self.daap_playlists.keys():
                self.playlist_item_map[playlist_id] = [x.item_id
                  for x in playlist.PlaylistItemMap.playlist_view(playlist_id)]

    def start_tracking(self):
        self.populate_playlists()
        for playlist_id in self.daap_playlists:
            app.info_updater.item_list_callbacks.add(self.type, playlist_id,
                                                 self.handle_item_list)
            app.info_updater.item_changed_callbacks.add(self.type, playlist_id,
                                                 self.handle_items_changed)
            messages.TrackItems(self.type, playlist_id).send_to_backend()
        # Track items that do not belong in any playlist.
        app.info_updater.item_list_callbacks.add(self.type, None,
                                                 self.handle_item_list)
        app.info_updater.item_changed_callbacks.add(self.type, None,
                                                 self.handle_items_changed)

        messages.TrackItems(self.type, None).send_to_backend()

        app.info_updater.connect('playlists-added',
                                 self.handle_playlist_added)
        app.info_updater.connect('playlists-changed',
                                 self.handle_playlist_changed)
        app.info_updater.connect('playlists-removed',
                                 self.handle_playlist_removed)

    def stop_tracking(self):
        for playlist_id in self.daap_playlists:
            messages.StopTrackingItems(self.type,
                                       playlist_id).send_to_backend()
            app.info_updater.item_list_callbacks.remove(self.type, playlist_id,
                                                    self.handle_item_list)
            app.info_updater.item_changed_callbacks.remove(self.type,
                                                    playlist_id,
                                                    self.handle_items_changed)
        messages.StopTrackingItems(self.type, self.id).send_to_backend()
        app.info_updater.item_list_callbacks.remove(self.type, None,
                                                    self.handle_item_list)
        app.info_updater.item_changed_callbacks.remove(self.type, None,
                                                    self.handle_items_changed)

        app.info_updater.disconnect(self.handle_playlist_added)
        app.info_updater.disconnect(self.handle_playlist_changed)
        app.info_updater.disconnect(self.handle_playlist_removed)

    def get_file(self, itemid, generation, ext, session, request_path_func,
                 offset=0, chunk=None):
        file_obj = None
        # Get a copy of the item under the lock ... if the underlying item
        # is going away then we'll deal with it later on.  only care about
        # the reference being valid (?)
        with self.item_lock:
            try:
                daapitem = self.daapitems[itemid]
            except KeyError:
                return None
        path = daapitem['path']
        if ext in ('ts', 'm3u8'):
            # If we are requesting a playlist, this basically means that
            # transcode is required.
            old_transcode_obj = None
            need_create = False
            with self.transcode_lock:
                if self.in_shutdown:
                    return None
                try:
                    transcode_obj = self.transcode[session]
                    if transcode_obj.itemid != itemid:
                        need_create = True
                        old_transcode_obj = transcode_obj
                    else:
                        # This request has already been satisfied by a more
                        # recent request.  Bye ...
                        if generation < transcode_obj.generation:
                            logging.debug('item %s transcode out of order',
                                          itemid)
                            return None
                        if chunk is not None and transcode_obj.isseek(chunk):
                            need_create = True
                            old_transcode_obj = transcode_obj
                except KeyError:
                    need_create = True
                if need_create:
                    yes, info = transcode.needs_transcode(path)
                    transcode_obj = transcode.TranscodeObject(
                                                          path,
                                                          itemid,
                                                          generation,
                                                          chunk,
                                                          info,
                                                          request_path_func)
                self.transcode[session] = transcode_obj

            # If there was an old object, shut it down.  Do it outside the
            # loop so that we don't hold onto the transcode lock for excessive
            # time
            if old_transcode_obj:
                old_transcode_obj.shutdown()
            if need_create:
                transcode_obj.transcode()

            if ext == 'm3u8':
                file_obj = transcode_obj.get_playlist()
                file_obj.seek(offset, os.SEEK_SET)
            elif ext == 'ts':
                file_obj = transcode_obj.get_chunk()
            else:
                # Should this be a ValueError instead?  But returning -1
                # will make the caller return 404.
                logging.warning('error: transcode should be one of ts or m3u8')
        elif ext == 'coverart':
            try:
                cover_art = daapitem['cover_art']
                if cover_art:
                    file_obj = open(cover_art, 'rb')
                    file_obj.seek(offset, os.SEEK_SET)
            except OSError:
                if file_obj:
                    file_obj.close()
        else:
            # If there is an outstanding job delete it first.
            try:
                del self.transcode[session]
            except KeyError:
                pass
            try:
                file_obj = open(path, 'rb')
                file_obj.seek(offset, os.SEEK_SET)
            except OSError:
                if file_obj:
                    file_obj.close()
        return file_obj

    def get_playlists(self):
        return self.daap_playlists

    def on_config_changed(self, obj, key, value):
        keys = [prefs.SHARE_AUDIO.key, prefs.SHARE_VIDEO.key]
        if key in keys:
            with self.item_lock:
                self.share_types = []
                if app.config.get(prefs.SHARE_AUDIO):
                    self.share_types += [libdaap.DAAP_MEDIAKIND_AUDIO]
                if app.config.get(prefs.SHARE_VIDEO):
                    self.share_types += [libdaap.DAAP_MEDIAKIND_VIDEO]

    def get_items(self, playlist_id=None):
        # Easy: just return
        with self.item_lock:
            items = dict()
            if not playlist_id:
                for k in self.daapitems.keys():
                    if (self.daapitems[k]['com.apple.itunes.mediakind'] in
                      self.share_types):
                        items[k] = self.daapitems[k]
                return items
            # XXX Somehow cache this?
            playlist = dict()
            for x in self.daapitems.keys():
                if (x in self.playlist_item_map[playlist_id] and
                  self.daapitems[x]['com.apple.itunes.mediakind'] in
                  self.share_types):
                    playlist[x] = self.daapitems[x]
            return playlist

    def make_item_dict(self, items):
        # See the daap_rmapping/daap_mapping for a list of mappings that
        # we do.
        for item in items:
            itemprop = dict()
            for attr in daap_rmapping.keys():
                daap_string = daap_rmapping[attr]
                itemprop[daap_string] = getattr(item, attr, None)
                if isinstance(itemprop[daap_string], unicode):
                    itemprop[daap_string] = (
                      itemprop[daap_string].encode('utf-8'))
                # Fixup the year, etc being -1.  XXX should read the daap
                # type then determine what to do.
                if itemprop[daap_string] == -1:
                    itemprop[daap_string] = 0
                # Fixup: these are stored as string?
                if daap_string in ('daap.songtracknumber',
                                   'daap.songyear'):
                    if itemprop[daap_string] is not None:
                        itemprop[daap_string] = int(itemprop[daap_string])
                # Fixup the duration: need to convert to millisecond.
                if daap_string == 'daap.songtime':
                    if itemprop[daap_string]:
                        itemprop[daap_string] *= DURATION_SCALE
                    else:
                        itemprop[daap_string] = 0
            # Fixup the enclosure format.  This is hardcoded to mp4, 
            # as iTunes requires this.  Other clients seem to be able to sniff
            # out the container.  We can change it if that's no longer true.
            # Fixup the media kind: XXX what about u'other'?
            enclosure = item.file_format
            if enclosure not in supported_filetypes:
                nam, ext = os.path.splitext(item.video_path)
                if ext in supported_filetypes:
                    enclosure = ext

            try:
                key = itemprop['org.participatoryculture.miro.itemkind']
                itemprop['org.participatoryculture.miro.itemkind'] = (
                    miro_itemkind_mapping[key])
            except KeyError:
                pass

            if itemprop['com.apple.itunes.mediakind'] == u'video':
                itemprop['com.apple.itunes.mediakind'] = (
                  libdaap.DAAP_MEDIAKIND_VIDEO)
                if not enclosure:
                    enclosure = '.mp4'
                enclosure = enclosure[1:]
                itemprop['daap.songformat'] = enclosure
            else:
                itemprop['com.apple.itunes.mediakind'] = (
                  libdaap.DAAP_MEDIAKIND_AUDIO)
                if not enclosure:
                    enclosure = '.mp3'
                enclosure = enclosure[1:]
                itemprop['daap.songformat'] = enclosure
            # Normally our strings are fixed up above, but then we re-pull
            # this out of the input data structure, so have to re-convert.
            if isinstance(itemprop['daap.songformat'], unicode):
                tmp = itemprop['daap.songformat'].encode('utf-8')
                itemprop['daap.songformat'] = tmp

            # don't forget to set the path..
            # ok: it is ignored since this is not valid dmap/daap const.
            itemprop['path'] = item.video_path
            itemprop['cover_art'] = item.thumbnail
            self.daapitems[item.id] = itemprop

    def finished_callback(self, session):
        # Like shutdown but only shuts down one of the sessions.  No need to
        # set shutdown.   XXX - could race - if we terminate control connection
        # and and reach here, before a transcode job arrives.  Then the
        # transcode job gets created anyway.
        with self.transcode_lock:
            try:
                self.transcode[session].shutdown()
            except KeyError:
                pass

    def shutdown(self):
        # Set the in_shutdown flag inside the transcode lock to ensure that
        # the transcode object synchronization gate in get_file() does not
        # waste time creating any more objects after this flag is set.
        with self.transcode_lock:
            self.in_shutdown = True
            for key in self.transcode.keys():
                self.transcode[key].shutdown()

class SharingManager(object):
    """SharingManager is the sharing server.  It publishes Miro media items
    to the outside world.  One part is the server instance and the other
    part is the service publishing, both are handled here.

    Important note: mdns_present only indicates the ability to interact with
    the mdns libraries, does not mean that mdns functionality is present
    on the system (e.g. server may be disabled).
    """
    # These commands should all be of the same size.
    CMD_QUIT = 'quit'
    CMD_NOP  = 'noop'
    def __init__(self):
        self.r, self.w = util.make_dummy_socket_pair()
        self.sharing = False
        self.discoverable = False
        self.name = ''
        self.mdns_present = libdaap.mdns_init()
        self.reload_done_event = threading.Event()
        self.mdns_callback = None
        self.callback_handle = app.backend_config_watcher.connect('changed',
                               self.on_config_changed)
        # Create the sharing server backend that keeps track of all the list
        # of items available.  Don't know whether we can just query it on the
        # fly, maybe that's a better idea.
        self.backend = SharingManagerBackend()
        # We can turn it on dynamically but if it's not too much work we'd
        # like to get these before so that turning it on and off is not too
        # onerous?
        self.backend.start_tracking()
        # Enable sharing if necessary.
        self.twiddle_sharing()
        # Normally, if mDNS discovery is enabled, we call resume() in the
        # in the registration callback, we need to do this because the
        # sharing tracker needs to know what name we actually got registered
        # with (instead of what we requested).   But alas, it won't be 
        # called if sharing's off.  So we have to do it manually here.
        if not self.mdns_present or not self.discoverable:
            app.sharing_tracker.resume()

    def session_count(self):
        if self.sharing:
            return self.server.session_count()
        else:
            return 0

    def on_config_changed(self, obj, key, value):
        listen_keys = [prefs.SHARE_MEDIA.key,
                       prefs.SHARE_DISCOVERABLE.key,
                       prefs.SHARE_NAME.key]
        if not key in listen_keys:
            return
        logging.debug('twiddle_sharing: invoked due to configuration change.')
        self.twiddle_sharing()

    def twiddle_sharing(self):
        sharing = app.config.get(prefs.SHARE_MEDIA)
        discoverable = app.config.get(prefs.SHARE_DISCOVERABLE)
        name = app.config.get(prefs.SHARE_NAME).encode('utf-8')
        name_changed = name != self.name
        if sharing != self.sharing:
            if sharing:
                # TODO: if this didn't work, should we set a timer to retry
                # at some point in the future?
                if not self.enable_sharing():
                    # if it didn't work then it must be false regardless.
                    self.discoverable = False
                    return
            else:
                if self.discoverable:
                    self.disable_discover()
                self.disable_sharing()

        # Short-circuit: if we have just disabled the share, then we don't
        # need to check the discoverable bits since it is not relevant, and
        # would already have been disabled anyway.
        if not self.sharing:
            return

        # Did we change the name?  If we have, then disable the share publish
        # first, and update what's kept in the server.
        if name_changed and self.discoverable:
            self.disable_discover()
            app.sharing_tracker.pause()
            self.server.set_name(name)
            self.server.set_finished_callback(self.finished_callback)

        if discoverable != self.discoverable:
            if discoverable:
                self.enable_discover()
            else:
                self.disable_discover()

    def finished_callback(self, session):
        eventloop.add_idle(lambda: self.backend.finished_callback(session),
                           'daap logout notification')

    def get_address(self):
        server_address = (None, None)
        try:
            server_address = self.server.server_address
        except AttributeError:
            pass
        return server_address

    def mdns_register_callback(self, name):
        self.name = name
        app.sharing_tracker.resume()

    def enable_discover(self):
        name = app.config.get(prefs.SHARE_NAME).encode('utf-8')
        # At this point the server must be available, because we'd otherwise
        # have no clue what port to register for with Bonjour.
        address, port = self.server.server_address
        self.mdns_callback = libdaap.mdns_register_service(name,
                                                  self.mdns_register_callback,
                                                  port=port)
        # not exactly but close enough: it's not actually until the
        # processing function gets called.
        self.discoverable = True
        # Reload the server thread: if we are only toggling between it
        # being advertised, then the server loop is already running in
        # the select() loop and won't know that we need to process the
        # registration.
        logging.debug('enabling discover ...')
        self.w.send(SharingManager.CMD_NOP)
        # Wait for the reload to finish.
        self.reload_done_event.wait()
        self.reload_done_event.clear()
        logging.debug('discover enabled.')

    def disable_discover(self):
        self.discoverable = False
        # Wait for the mdns unregistration to finish.
        logging.debug('disabling discover ...')
        self.w.send(SharingManager.CMD_NOP)
        self.reload_done_event.wait()
        self.reload_done_event.clear()
        # If we were trying to register a name change but disabled mdns
        # discovery in between make sure we do not wedge the sharing tracker.
        app.sharing_tracker.resume()
        logging.debug('discover disabled.')

    def server_thread(self):
        # Let caller know that we have started.
        self.reload_done_event.set()
        server_fileno = self.server.fileno()
        while True:
            try:
                rset = [server_fileno, self.r]
                refs = []
                if self.discoverable and self.mdns_callback:
                    refs += self.mdns_callback.get_refs()
                rset += refs
                r, w, x = select.select(rset, [], [])
                for i in r:
                    if i in refs:
                        # Possible that mdns_callback is not valid at this
                        # point, because the this wakeup was a result of
                        # closing of the socket (e.g. during name change
                        # when we unpublish and republish our name).
                        if self.mdns_callback:
                            self.mdns_callback(i)
                        continue
                    if server_fileno == i:
                        self.server.handle_request()
                        continue
                    if self.r == i:
                        cmd = self.r.recv(4)
                        logging.debug('sharing: CMD %s' % cmd)
                        if cmd == SharingManager.CMD_QUIT:
                            del self.thread
                            del self.server
                            self.reload_done_event.set()
                            return
                        elif cmd == SharingManager.CMD_NOP:
                            logging.debug('sharing: reload')
                            if not self.discoverable and self.mdns_callback:
                                old_callback = self.mdns_callback
                                self.mdns_callback = None
                                libdaap.mdns_unregister_service(old_callback)
                            self.reload_done_event.set()
                            continue
                        else:
                            raise 
            except select.error, (err, errstring):
                if err == errno.EINTR:
                    continue 
                # If we end up here, it could mean that the mdns has
                # been closed.  Alternatively the server fileno has been 
                # closed or the command pipe has been closed (not likely).
                if err == errno.EBADF:
                    continue
                typ, value, tb = sys.exc_info()
                logging.error('sharing:server_thread: err %d reason = %s',
                              err, errstring)
                for line in traceback.format_tb(tb):
                    logging.error('%s', line) 
            # XXX How to pass error, send message to the backend/frontend?
            except StandardError:
                typ, value, tb = sys.exc_info()
                logging.error('sharing:server_thread: type %s exception %s',
                       typ, value)
                for line in traceback.format_tb(tb):
                    logging.error('%s', line) 

    def enable_sharing(self):
        # Can we actually enable sharing.  The Bonjour client-side libraries
        # might not be installed.  This could happen if the user previously
        # have the libraries installed and has it enabled, but then uninstalled
        # it in the meantime, so handle this case as fail-safe.
        if not self.mdns_present:
            self.sharing = False
            return

        name = app.config.get(prefs.SHARE_NAME).encode('utf-8')
        self.server = libdaap.make_daap_server(self.backend, debug=True,
                                               name=name)
        if not self.server:
            self.sharing = False
            return

        self.server.set_log_message_callback(
            lambda format, *args: logging.info(format, *args))

        self.thread = threading.Thread(target=thread_body,
                                       args=[self.server_thread],
                                       name='DAAP Server Thread')
        self.thread.daemon = True
        self.thread.start()
        logging.debug('waiting for server to start ...')
        self.reload_done_event.wait()
        self.reload_done_event.clear()
        logging.debug('server started.')
        self.sharing = True

        return self.sharing

    def disable_sharing(self):
        self.sharing = False
        # What to do in case of socket error here?
        logging.debug('waiting for server to stop ...')
        self.w.send(SharingManager.CMD_QUIT)
        self.reload_done_event.wait()
        self.reload_done_event.clear()
        logging.debug('server stopped.')

    def shutdown(self):
        eventloop.add_urgent_call(self.shutdown_callback,
                                  'sharing shutdown backend call')

    def shutdown_callback(self):
        if self.sharing:
            if self.discoverable:
                self.disable_discover()
            # XXX: need to break off existing connections
            self.disable_sharing()
        self.backend.shutdown()
