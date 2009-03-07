#!/usr/bin/env python

# Tower Wars, a game
# Copyright 2009 Eric Sumner

# This file is part of Tower Wars.
# 
# Tower Wars is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# Tower Wars is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with Tower Wars.  If not, see <http://www.gnu.org/licenses/>.

import pygame, sys, os, traceback
from pygame.locals import *
from select import select

pygame.init()
pygame.display.set_mode((512, 768))

FPS = 30
next_frame_time = 0
frameno = 0
fds = []

class SelectSocket:
    def __init__(self, file):
        self.inbuf  = ''
        self.outbuf = ''
        self.open = True
        if isinstance(file, int):
            self.fd = file
        if hasattr(file, 'fileno'):
            self.fd = file.fileno()
        else:
            self.fd = os.open(file, os.O_WRONLY | os.O_APPEND)

    def fileno(self):
        return self.fd

    def send(self):
        self.outbuf = self.outbuf[os.write(self.fd, self.outbuf):]

    def flush(self):
        while self.outbuf:
            self.send()

    def recv(self):
        data = os.read(self.fd, 4096)
        self.inbuf += data
        if not data: self.open = False # EOF

    def rts(self):
        return len(self.outbuf)

    def rtr(self):
        return self.open

class Log(SelectSocket):
    def __init__(self):
        SelectSocket.__init__(self, sys.stdout)
        self.verbosity = 5 # Trace execution
        self.desc = {0: 'FATAL', 1: 'ERROR', 2: 'WARN', 3:'INFO', 4:'DEBUG', 5:'TRACE'}
        self.msg(3, 'Logging', 'Log opened')

    def msg(self, level, label, message, **kwargs):
        if level > self.verbosity: return
        self.outbuf += '%8d %5s %17s: %s\t%s\n' % (frameno, self.desc.get(level, level), label, message, kwargs)
    
log = Log()

fds.append(log)

color = 0

next_frame_time = pygame.time.get_ticks()
while True:
    next_frame_time += 1000/FPS
    wait_interval = next_frame_time - pygame.time.get_ticks()
    frameno += 1
    if wait_interval<0:
        log.msg(0, 'EventLoop', 'Late Frame', interval=wait_interval)
        log.flush()
        print >>sys.stderr, 'FATAL: Late Frame\n'
        sys.exit(1)
    log.msg(5, 'EventLoop', 'Waiting', interval=wait_interval)
    while wait_interval > 0:
        try:
            if [f.rtr() or f.rts() for f in fds]:
                rd,wr,ex = select( [f for f in fds if f.rtr()],
                                   [f for f in fds if f.rts()],
                                   [], wait_interval/1000.)
                for s in wr:
                    s.send()
                for s in rd:
                    s.recv()
            else:
                pygame.time.wait(wait_interval)
        except Exception, e:
            log.msg(1, 'EventLoop', traceback.format_exception_only(type(e),e)[-1].strip())
            traceback.print_exc()
        wait_interval = next_frame_time - pygame.time.get_ticks()

    #Game Logic
    color += 1
    if color > 255: color = 0
    pygame.display.get_surface().fill((color, color, color))
    pygame.display.update()
