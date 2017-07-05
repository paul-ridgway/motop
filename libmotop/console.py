#!/usr/bin/env python
# -*- coding: utf-8 -*-
##
# motop - Unix "top" Clone for MongoDB
#
# Copyright (c) 2012, Tart İnternet Teknolojileri Ticaret AŞ
#
# Permission to use, copy, modify, and/or distribute this software for any purpose with or without fee is hereby
# granted, provided that the above copyright notice and this permission notice appear in all copies.
#
# The software is provided "as is" and the author disclaims all warranties with regard to the software including all
# implied warranties of merchantability and fitness. In no event shall the author be liable for any special, direct,
# indirect, or consequential damages or any damages whatsoever resulting from loss of use, data or profits, whether
# in an action of contract, negligence or other tortious action, arising out of or in connection with the use or
# performance of this software.
##

"""Imports for Python 3 compatibility"""
from __future__ import print_function

import re

try:
    import __builtin__
    __builtin__.input = __builtin__.raw_input
except ImportError: pass

"""Library imports"""
import sys
import os
import tty
import termios
import struct
import fcntl
import select
import signal
import time
import numbers
from datetime import datetime

class ColorStr:
    BLACK = '\033[0;30m'
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[0;33m'
    BLUE = '\033[0;34m'
    PURPLE = '\033[0;35m'
    CYAN = '\033[0;36m'
    WHITE = '\033[0;37m'
    BRIGHT_BLACK = '\033[1;30m'
    BRIGHT_RED = '\033[1;31m'
    BRIGHT_GREEN = '\033[1;32m'
    BRIGHT_YELLOW = '\033[1;33m'
    BRIGHT_BLUE = '\033[1;34m'
    BRIGHT_PURPLE = '\033[1;35m'
    BRIGHT_CYAN = '\033[1;36m'
    BRIGHT_WHITE = '\033[1;37m'
    RESET = '\033[0m'

    def __init__(self, str, color = None):
        self._str = str
        self._color = color

    def hasColor(self):
        return self._color is not None

    def color(self):
        return self._color

    def __len__(self):
        return len(self._str)

    def ljust(self, width):
        return self._str.ljust(width)

class Console:
    """Main class for input and output. Used with "with" statement to hide pressed buttons on the console."""
    def __init__(self):
        self.__deactiveConsole = DeactiveConsole(self)
        self.__saveSize()
        signal.signal(signal.SIGWINCH, self.__saveSize)
        self.__lastCheckTime = None

    def __enter__(self):
        """Hide pressed buttons on the console."""
        try:
            self.__settings = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())
        except termios.error:
            self.__settings = None
        return self

    def __exit__(self, *ignored):
        if self.__settings:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.__settings)

    def __saveSize(self, *ignored):
        try:
            self.__height, self.__width = struct.unpack('hhhh', fcntl.ioctl(0, termios.TIOCGWINSZ , '\000' * 8))[:2]
        except IOError:
            self.__height, self.__width = 20, 80

    def waitButton(self):
        while True:
            try:
                return sys.stdin.read(1)
            except IOError: pass

    def checkButton(self, waitTime):
        """Check one character input. Waits for approximately waitTime parameter as seconds."""
        if self.__lastCheckTime:
            timedelta = datetime.now() - self.__lastCheckTime
            waitTime -= timedelta.seconds + (timedelta.microseconds / 1000000.0)
        while waitTime > 0 and not select.select([sys.stdin], [], [], 0)[0]:
            time.sleep(0.1)
            waitTime -= 0.1
        self.__lastCheckTime = datetime.now()

        if select.select([sys.stdin], [], [], 0)[0]:
            return sys.stdin.read(1)

    def refresh(self, blocks):
        """Print the blocks with height and width left on the screen."""
        os.system('clear')
        leftHeight = self.__height
        for block in blocks:
            if not len(block):
                """Do not show the block if there are no lines."""
                continue
            if leftHeight <= 2:
                """Do not show the block if there are not enough lines left for header and a row."""
                break
            height = len(block) + 2 if len(block) + 2 < leftHeight else leftHeight

            try:
                block.print(height, self.__width)
                leftHeight -= height
                if leftHeight >= 2:
                    print()
                    leftHeight -= 1
            except IOError: pass

    def askForInput(self, *attributes):
        """Ask for input for given attributes in given order."""
        with self.__deactiveConsole:
            print()
            values = []
            for attribute in attributes:
                value = input(attribute + ': ')
                if not value:
                    break
                values.append(value)
            return values

class DeactiveConsole:
    """Class to use with "with" statement as "wihout" statement for Console class defined below."""
    def __init__(self, console):
        self.__console = console

    def __enter__(self):
        self.__console.__exit__()

    def __exit__(self, *ignored):
        self.__console.__enter__()

class Block:
    """Class to print blocks of ordered printables."""
    def __init__(self, columnHeaders):
        self.__columnHeaders = columnHeaders
        self.__columnWidths = [6] * len(self.__columnHeaders)

    def reset(self, lines):
        self.__lines = lines

    def __len__(self):
        return len(self.__lines)

    fixes = 'k', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y'

    def __cell(self, value):
        if isinstance(value, list):
            return ' / '.join(self.__cell(v) for v in value)

        if isinstance(value, numbers.Integral):
            """Extents int to show big numbers human readable."""
            for fix in ('',) + self.fixes:
                if value < 10000:
                    return '%.0f' % (value) + fix
                value = value / 1000

        elif isinstance(value, numbers.Number):
            """Extents int to show big numbers human readable."""
            for fix in ('',) + self.fixes:
                if value < 10000:
                    return '%.02f' % (value) + fix
                value = float(value) / 1000

        elif isinstance(value, ColorStr):
            return value

        if value is not None:
            try:
                return str(value)
            except:
                print("Unexpected error:", sys.exc_info()[0])
                print("Value:")
                print(value)
                raise

        return ''

    def __printLine(self, line, leftWidth, bold=False):
        """Print the cells separated by 2 spaces, cut the part after the width."""
        for index, value in enumerate(line):
            cell = self.__cell(value)
            if leftWidth < len(self.__columnHeaders[index]):
                """Do not show the column if there is not enough space for the header."""
                break
            if index + 1 < len(line):
                """Check the cell lenght if it is not the cell in the column. Set the column width to the cell length
                plus 2 for space if it is longer than the exisent column width."""
                self.__columnWidths[index] = max(len(cell) + 2, self.__columnWidths[index])

            if bold and sys.stdout.isatty():
                print('\x1b[1m', end='')
            if isinstance(cell, ColorStr) and cell.hasColor() and sys.stdout.isatty():
                print(cell.color(), end='')
            print(cell.ljust(self.__columnWidths[index])[:leftWidth], end = '')
            if ((isinstance(cell, ColorStr) and cell.hasColor()) or bold) and sys.stdout.isatty():
                print(ColorStr.RESET, end='')
            leftWidth -= self.__columnWidths[index]

        """Finally, the new line."""
        print()

    def print(self, height, width):
        """Print the lines, cut the ones after the height."""
        assert height > 1
        self.__printLine(self.__columnHeaders, width, True)
        height -= 1
        for line in self.__lines:
            if height <= 1:
                break
            assert len(line) <= len(self.__columnHeaders)
            height -= 1
            self.__printLine(line, width)

