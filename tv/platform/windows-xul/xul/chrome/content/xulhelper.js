/*
# Miro - an RSS based video player application
# Copyright (C) 2008 Participatory Culture Foundation
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
*/

// These are direct JavaScript translations of xulhelper.py
//
// Unfortunately, I don't see a way around having a Python version, a chome JS
// version, and a XUL JS version.
//
// See also jsbridge.js.

var proxyManager = Components.classes["@mozilla.org/xpcomproxy;1"].createInstance(Components.interfaces.nsIProxyObjectManager);

try {
    // XULRunner 1.8 version
    var eventQueueService = Components.classes["@mozilla.org/event-queue-service;1"].getService(Components.interfaces.nsIEventQueueService);
    var xulEventQueue = eventQueueService.getSpecialEventQueue(Components.interfaces.nsIEventQueueService.UI_THREAD_EVENT_QUEUE);
} catch (e) {
    // XULRunner 1.9 version
    var threadMan = Components.classes["@mozilla.org/thread-manager;1"].getService(Components.interfaces.nsIThreadManager);
    var xulEventQueue = threadMan.mainThread;
}

function proxify(obj, iid, sync) {
    if (sync === false) {
        var flags = Components.interfaces.nsIProxyObjectManager.INVOKE_ASYNC | Components.interfaces.nsIProxyObjectManager.FORCE_PROXY_CREATION;
    } else {
        var flags = Components.interfaces.nsIProxyObjectManager.INVOKE_SYNC | Components.interfaces.nsIProxyObjectManager.FORCE_PROXY_CREATION;
    }
    return proxyManager.getProxyForObject(xulEventQueue, iid, obj, flags);
}

function makeComp(clsid, iid, makeProxy, sync) {
    if (makeProxy === null) {
      throw("makeComp() requires three arguments. Only two set");
    }
    var obj = Components.classes[clsid].createInstance(iid);
    if (makeProxy) obj = proxify(obj, iid, sync);
    return obj;
}

function makeService(clsid, iid, makeProxy, sync) {
    if (makeProxy === null) {
      throw("makeService() requires three arguments. Only two set");
    }
    var obj = Components.classes[clsid].getService(iid);
    if (makeProxy) obj = proxify(obj, iid, sync);
    return obj;
}
