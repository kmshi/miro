/*
# Miro - an RSS based video player application
# Copyright (C) 2005-2008 Participatory Culture Foundation
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

/* moviedata_util.c -- little wrapper C file that catches exceptions in
 * moviedata_util.py and prevents them from causing crash dialogs.
 */

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>


#include <Python.h>

int main(int argc, char *argv[])
{
  _try {
    Py_Initialize();
    /* NOTE: We should change the value of argv[0] to be moviedata_util.py,
     * but it doesn't matter in this case.
     */
    PySys_SetArgv(argc, argv);
    PyRun_SimpleString("execfile('moviedata_util.py')");
    Py_Finalize();
  } _except( EXCEPTION_EXECUTE_HANDLER ) {
      printf("Miro-Movie-Data-Length: -1\n");
      printf("Miro-Movie-Data-Thumbnail: Failure\n");
  }
  return 0;
}
