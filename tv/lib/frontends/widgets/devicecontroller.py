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

"""Controller for Devices tab.
"""
import datetime

from miro import app
from miro import displaytext
from miro import messages
from miro import util

from miro.frontends.widgets import imagepool
from miro.frontends.widgets import itemlist
from miro.frontends.widgets import itemlistcontroller
from miro.frontends.widgets import itemlistwidgets
from miro.frontends.widgets import segmented
from miro.frontends.widgets import widgetutil

from miro.plat import resources
from miro.plat.frontends.widgets import widgetset

class DeviceTitlebar(itemlistwidgets.ItemListTitlebar):
    def _build_titlebar_extra(self):
        pass

class DeviceTabButtonSegment(segmented.TextButtonSegment):

    MARGIN = 20
    COLOR = (1, 1, 1)
    TEXT_COLOR = {True: COLOR, False: COLOR}

class SizeWidget(widgetset.HBox):
    def __init__(self, size=None, remaining=None):
        widgetset.HBox.__init__(self)
        self.progress = widgetset.ProgressBar()
        self.progress.set_size_request(500, -1)
        self.text = widgetset.Label()
        self.pack_start(self.progress, padding=20)
        self.pack_start(self.text)
        self.set_size(size, remaining)

    def set_size(self, size, remaining):
        self.size = size
        self.remaining = remaining
        if size and remaining:
            self.progress.set_progress(1 - float(remaining) / size)
            self.text.set_text('%s free' % displaytext.size_string(
                    remaining))
        else:
            self.progress.set_progress(0)
            self.text.set_text('not mounted')

class DeviceMountedView(widgetset.VBox):
    def __init__(self):
        widgetset.VBox.__init__(self)

        self.button_row = segmented.SegmentedButtonsRow()
        for name in ('Main', 'Video', 'Audio', 'Playlists'):
            button = DeviceTabButtonSegment(name.lower(), name,
                                            self._tab_clicked)
            self.button_row.add_button(name.lower(), button)

        self.button_row.set_active('main')
        self.pack_start(widgetutil.align_center(self.button_row.make_widget()))

        self.tabs = {}
        self.tab_container = widgetset.SolidBackground((1, 1, 1))
        self.pack_start(self.tab_container, expand=True)

        vbox = widgetset.VBox()
        label = widgetset.Label("To copy media onto the device, drag it onto \
the sidebar.")
        label.set_size(1.5)
        vbox.pack_start(widgetutil.align_center(label, top_pad=50))
        self.device_size = SizeWidget()
        alignment = widgetset.Alignment(0.5, 1, 0, 0, bottom_pad=15,
                                        right_pad=20)
        alignment.add(self.device_size)
        vbox.pack_end(alignment)

        self.add_tab('main', vbox)

    def add_tab(self, key, widget):
        if not self.tabs:
            self.tab_container.set_child(widget)
        self.tabs[key] = widget

    def set_device(self, device):
        self.device_size.set_size(device.size, device.remaining)

    def _tab_clicked(self, button):
        self.button_row.set_active(button.key)

class DeviceItemList(itemlist.ItemList):

    def filter(self, item_info):
        return True

class DeviceItemInfo(object):
    is_playable = True
    video_watched = True
    expiration_date = None
    item_viewed = True
    downloaded = True
    downloader = download_info = None
    is_container_item = False
    pending_auto_dl = pending_manual_dl = False
    state = "downloaded"
    stripper = util.HTMLStripper()

    def __init__(self, d):
        self.__dict__.update(d)
        for field in ('release_date',):
            val = getattr(self, field)
            if val is not None:
                setattr(self, field, datetime.datetime.fromtimestamp(val))
        self.video_path = self.video_path.encode('utf8')
        self.description_text, self.description_links = self.stripper.strip(
            self.description)
        image_path = resources.path('images/thumb-default-video.png')
        self.icon = imagepool.get_surface(image_path)

class UnknownDeviceView(widgetset.VBox):
    def __init__(self):
        widgetset.VBox.__init__(self)
        label = widgetset.Label()
        label.set_text("We're not exactly sure what kind of phone this is.")
        label.set_bold(True)
        label.set_size(1.5)
        self.pack_start(widgetutil.align_center(label, left_pad=20, top_pad=50,
                                              bottom_pad=20))

        self.device_choices = widgetset.VBox()
        self.pack_start(widgetutil.align_center(self.device_choices,
                                                left_pad=20, top_pad=50,
                                                bottom_pad=20))

    def set_device(self, device):
        for child in self.device_choices.children:
            self.device_choices.remove(child)

        self.device = device
        possible_devices = sorted(device.info.devices)
        rbg = widgetset.RadioButtonGroup()

        buttons_to_device_name = {}
        for device_name in possible_devices:
            button = widgetset.RadioButton(device_name, rbg)
            self.device_choices.pack_start(button)
            buttons_to_device_name[button] = device_name

        def _clicked(*args):
            messages.SetDeviceType(
                self.device,
                buttons_to_device_name[rbg.get_selected()]).send_to_backend()

        select = widgetset.Button('This is my device')
        select.connect('clicked', _clicked)
        self.device_choices.pack_start(widgetutil.pad(select, top=40))

class DeviceUnmountedView(widgetset.VBox):
    def __init__(self):
        widgetset.VBox.__init__(self)
        label = widgetset.Label()
        label.set_text('This phone is not yet mounted.')
        label.set_bold(True)
        label.set_size(1.5)
        self.pack_start(widgetutil.align_center(label, left_pad=20, top_pad=50,
                                              bottom_pad=20))
        self.device_text = widgetset.Label()
        self.device_text.set_size(1.5)
        self.device_text.set_wrap(True)
        self.pack_start(widgetutil.align_center(self.device_text, left_pad=20))


    def set_device(self, device):
        self.device_text.set_text(
            device.info.mount_instructions.replace('\n', '\n\n'))

class DeviceWidget(widgetset.VBox):
    def __init__(self, device):
        widgetset.VBox.__init__(self)
        self.titlebar_view = widgetset.Background()
        self.device_view = widgetset.Background()
        self.pack_start(self.titlebar_view)
        self.pack_start(self.device_view, expand=True)
        self.set_device(device)

    def set_device(self, device):
        self.titlebar_view.remove()
        self.titlebar_view.set_child(self.make_titlebar(device))
        self.device_view.remove()
        if not device.mount:
            view = DeviceUnmountedView()
        elif not device.info.has_multiple_devices:
            view = DeviceMountedView()
        else:
            view = UnknownDeviceView()
        view.set_device(device)
        self.device_view.set_child(view)

    @staticmethod
    def make_titlebar(device):
        image_path = resources.path("images/phone-large.png")
        icon = imagepool.get(image_path)
        return DeviceTitlebar(device.name, icon)

class DeviceController(object):
    def __init__(self, device):
        self.device = device
        self.widget = DeviceWidget(device)

    def handle_device_changed(self, device):
        self.device = device
        self.widget.set_device(device)

    def start_tracking(self):
        pass

    def stop_tracking(self):
        pass

class DeviceItemController(itemlistcontroller.AudioVideoItemsController):
    type = 'device'
    id = None
    unwatched_label = u'' # everything is marked as played

    def __init__(self, device):
        self.device = device
        self.image_filename = 'icon-%s_large.png' % device.tab_type
        self.title = u'%s on %s' % (device.name, device.info.name)
        itemlistcontroller.AudioVideoItemsController.__init__(self)

    def build_header_toolbar(self):
        return itemlistwidgets.HeaderToolbar()

    def start_tracking(self):
        app.info_updater.item_list_callbacks.add('device', self.device.id,
                self.handle_item_list)
        app.info_updater.item_changed_callbacks.add('device', self.device.id,
                self.handle_items_changed)
        messages.TrackItems('device', self.device).send_to_backend()

    def stop_tracking(self):
        app.info_updater.item_list_callbacks.remove('device', self.device.id,
                self.handle_item_list)
        app.info_updater.item_changed_callbacks.remove(
            'device',self.device.id, self.handle_items_changed)
        messages.StopTrackingItems('device', self.device).send_to_backend()

    def on_sort_changed(self, obj, sort_key, ascending):
        sorter = itemlist.SORT_KEY_MAP[sort_key](ascending)
        self.item_list_group.set_sort(sorter)
        self.list_item_view.model_changed()
        self.widget.toolbar.change_sort_indicator(sort_key, ascending)
        self.list_item_view.change_sort_indicator(sort_key, ascending)
        self.device.database['%s_sort_state' % self.type] = (sort_key,
                                                             ascending)