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
import random

pygame.init()
pygame.display.set_mode((512, 768), pygame.DOUBLEBUF)

FPS = 30
next_frame_time = 0
frameno = 0
fds = []
event_delay = 5 #frames
remote_frame_offset = 0

class EventManager:
    def __init__(self):
        self.cache = {}

    def getevents(self):
        if (frameno - 1) in self.cache:
            del self.cache[frameno - 1]
        return self.cache.get(frameno, [])
    
    def add_local_event(self, event):
        if (frameno + event_delay) not in self.cache:
            self.cache[frameno + event_delay] = []
        self.cache[frameno + event_delay].append(event)

    def add_remote_event(self, event, time):
        if (time + remote_frame_offset) not in self.cache:
            self.cache[time + remote_frame_offset] = []
        self.cache[time + remote_frame_offset].append(event)

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

# Game State
class Playfield:
    def __init__(self):
       self.occupancy = [[0]*32 for x in range(48)]

    def render(self, (offy, offx)):
        for y, row in enumerate(self.occupancy):
            for x, val in enumerate(row):
                cell = pygame.Rect(16*x+offx, 16*y+offy, 16, 16)
                pygame.display.get_surface().fill((val,val,val), cell)

    def mutate(self):
        for y, row in enumerate(self.occupancy):
            for x, val in enumerate(row):
                if val: row[x] = val - 1

        x = random.randint(0,31)
        y = random.randint(0,47)
        val = random.randint(0,255)
        self.occupancy[y][x] = val

    def clear(self, (x, y)):
        self.occupancy[y/16][x/16] = 0

playfield = Playfield()

# Game Display
def render_frame():
    pygame.display.get_surface().fill((0,0,0))
    playfield.render((0,0))
    pygame.display.flip()

# Game Logic, called for every frame, even dropped ones
def process_updates():
    for ev in pygame.event.get():
        log.msg(5, 'PygameEvent', ev)
        if ev.type == MOUSEMOTION: playfield.clear(ev.pos)
        if ev.type == KEYDOWN and ev.key == pygame.K_q: sys.exit(0)
    playfield.mutate()
    
# Event Loop
next_frame_time = pygame.time.get_ticks()
try:
    while True:
        next_frame_time += 1000/FPS
        wait_interval = next_frame_time - pygame.time.get_ticks()
        frameno += 1
        if wait_interval<0:
            log.msg(2, 'EventLoop', 'Dropping Frame', interval=wait_interval)
        else:
            try: render_frame()
            except Exception, e:
                log.msg(1, 'RenderFrame', traceback.format_exception_only(type(e),e)[-1].strip())
                traceback.print_exc()
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
        try: process_updates()
        except Exception, e:
            log.msg(1, 'ProcessUpdates', traceback.format_exception_only(type(e),e)[-1].strip())
            traceback.print_exc()
except BaseException, e:
    log.flush()
