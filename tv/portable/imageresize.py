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

"""Code to handle resizing images.  """

import logging
import os
import traceback

from miro.platformutils import resizeImage

def _resizedKey(width, height):
    return u'%sx%s' % (width, height)

def _makeResizedPath(filename, width, height):
    path, ext = os.path.splitext(filename)
    path += '.%sx%s' % (width, height)
    return path + ext

def multiResizeImage(source_filename, sizes):
    """Resize an image to several sizes.

    Arguments:
        source_filename -- image to resize
        sizes -- list of (width, height) tuples to resize to.
    
    Returns a dict storing the images successfully resized.  The keys are
    "<width>x<height>" and the values are the paths to the image.
    """

    results = {}
    for width, height in sizes:
        resizedPath = _makeResizedPath(source_filename, width, height)
        try:
            resizeImage(source_filename, resizedPath, width, height)
        except:
            logging.warn("Error resizing %s to %sx%s:\n%s", source_filename,
                    width, height, traceback.format_exc())
        else:
            results[_resizedKey(width, height)] = resizedPath
    return results

def getImage(resized_filenames, width, height):
    """Fetch a image from the results of multiResizeImage().  If (width,
    height) wasn't one of the combinations passed to multiResizeImage(), or
    the image wasn't successfully resized, a KeyError will be thrown.
    """
    return resized_filenames[_resizedKey(width, height)]

def removeResizedFiles(resized_filenames):
    """Delete the files returned by multiResizeImage()."""

    for filename in resized_filenames.values():
        try:
            if (os.path.exists(filename)):
                os.remove (filename)
        except:
            logging.warn("Error deleted resized image: %s\n%s", filename,
                    traceback.format_exc())
