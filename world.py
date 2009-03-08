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
from optparse import OptionParser
import random, socket

# extern FPS
# extern frameno

def add_options(option_parser):
    pass

def init(options):
    pygame.display.set_mode((512, 768), pygame.DOUBLEBUF)
    H_EVENT_reset()

# extern log

# Input events: H_PYGAME_%s(**kwargs)
# Semantic events H_EVENT_%s(*args)

def tick():
    playfield.mutate()

# extern event_manager

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
        log.msg(4, 'Playfield', 'Mutate', cell=(y,x), value=val)

    def clear(self, (x, y)):
        if self.occupancy[y/16][x/16]:
            self.occupancy[y/16][x/16] = 0
            log.msg(4, 'Playfield', 'Clear', cell=(y,x))

def H_EVENT_reset():
    global playfield
    playfield = Playfield()

def H_EVENT_randomize(x):
    random.seed(int(x))

# Game Display
def render_frame():
    pygame.display.get_surface().fill((0,0,0))
    playfield.render((0,0))
    pygame.display.flip()

# Input Handlers
def H_PYGAME_MouseButtonDown(pos, **kwargs):
    event_manager.add_event('clear', pos[0], pos[1])

def H_PYGAME_KeyDown(key, **kwargs):
    if key == pygame.K_q:
        event_manager.add_event('quit')

def H_EVENT_clear(x, y):
    playfield.clear((int(x), int(y)))

def H_EVENT_quit():
    sys.exit(0)
