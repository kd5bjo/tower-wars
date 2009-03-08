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

import gc
gc.disable()

WIDTH = 64
HEIGHT = 48

role = 'Server'

# extern FPS
# extern frameno
# extern log
# extern event_manager

def add_options(option_parser):
    pass

def init(options):
    global role
    pygame.display.set_mode((16*WIDTH, 16*HEIGHT), pygame.DOUBLEBUF)
    if options.ip != '0.0.0.0': role = 'Client'
    H_EVENT_reset()


# Input events: H_PYGAME_%s(**kwargs)
# Semantic events H_EVENT_%s(*args)

class Playfield:
    def __init__(self):
        self.pieces = set()
        self.column_heights = [HEIGHT]*WIDTH
        self.streaks = [(HEIGHT, 0)] * WIDTH
        self.occupancy = [[None]*WIDTH for x in xrange(HEIGHT)]

    def render(self, offset):
        for col, (h, c) in enumerate(self.streaks):
            pygame.display.get_surface().fill((c,c,c),    pygame.Rect(offset[0]+16*col, offset[1], 16, 16*h))
            if c <= 26:
                pygame.display.get_surface().fill((26,26,26), pygame.Rect(offset[0]+16*col, offset[1],  1, 16*h))
        if role == 'Server':
            pygame.display.get_surface().fill((0,255,0), pygame.Rect(offset[0],         offset[1], 8*WIDTH, 5*16))
            pygame.display.get_surface().fill((255,0,0), pygame.Rect(offset[0]+8*WIDTH, offset[1], 8*WIDTH, 5*16))
        elif role == 'Client':
            pygame.display.get_surface().fill((255,0,0), pygame.Rect(offset[0],         offset[1], 8*WIDTH, 5*16))
            pygame.display.get_surface().fill((0,255,0), pygame.Rect(offset[0]+8*WIDTH, offset[1], 8*WIDTH, 5*16))
        pygame.display.get_surface().fill((0,0,255), pygame.Rect(offset[0]+8*WIDTH - 2, offset[1], 3, 16*HEIGHT))
        for p in self.pieces:
            p.render(offset)

    def update_column_heights(self, col, row):
        self.column_heights[col] = row
        self.streaks[col] = (row, 255)

    def tick(self):
        self.streaks = [(h, max(c-10,0)) for h,c in self.streaks]
        queued_pieces = set()
        for y, row in enumerate(self.occupancy):
            for x, val in enumerate(row):
                if not val: continue
                if val.last_physics == frameno: continue
                if val in queued_pieces: continue
                if [v for c, v in val.above() if v.last_physics < frameno]:
                    queued_pieces.add(val)
                    continue
                if val.do_physics():
                    val.destroy()
                    return
            for val in queued_pieces.copy():
                if not [v for c, v in val.above() if v.last_physics < frameno]:
                    queued_pieces.remove(val)
                    print >>sys.stderr, 'Secondary'
                    if val.do_physics():
                        val.destroy()
                        return


class Piece:
    def __init__(self, x, size=10):
        self.last_physics = 0
        self.forces = {}
        self.cells = set([(0,0)])
        while len(self.cells) < size:
            rx, ry = random.choice(list(self.cells))
            candidate_cells = set([(rx, ry+1), (rx, ry-1), (rx+1, ry), (rx-1,ry)]) - self.cells
            if len(candidate_cells) < 2: continue
            self.cells.add(random.choice(list(candidate_cells)))
        self.x = x
        self.y = -min(y for x,y in self.cells)

        self.rotation = 0

        self.rotations = [(lambda (x,y): ( x, y)),
                          (lambda (x,y): ( y,-x)),
                          (lambda (x,y): (-x,-y)),
                          (lambda (x,y): (-y, x))]

        self._color = (0,0,0)
        while self._color == (0,0,0):
            self._color = tuple(random.choice((0,127,255)) for x in range(3))

        self.opacity = 0
        self.dropFrame = None
#        for x,y in self.cells:
#            playfield.occupancy[y+self.y][x+self.x] = self

    def render(self, (gridy, gridx)):
        surf = pygame.display.get_surface()
        white = (255,255,255)
        if self.rotation != 0:
            xformed_cells = set(self.rotations[self.rotation](coord) for coord in self.cells)
        else:
            xformed_cells = self.cells
        for x,y in xformed_cells:
            cell = pygame.Rect(16*(x+self.x)+gridx, 16*(y+self.y)+gridy, 16, 16)
            surf.fill(tuple((c*self.opacity) / 5 for c in self._color), cell)
            if (x+1,y) not in xformed_cells:
                surf.fill(white, pygame.Rect(16*(x+self.x)+gridx+15, 16*(y+self.y)+gridy,     1, 16))
            if (x-1,y) not in xformed_cells:
                surf.fill(white, pygame.Rect(16*(x+self.x)+gridx,    16*(y+self.y)+gridy,     1, 16))
            if (x,y-1) not in xformed_cells:
                surf.fill(white, pygame.Rect(16*(x+self.x)+gridx,    16*(y+self.y)+gridy,    16,  1))
            if (x,y+1) not in xformed_cells:
                surf.fill(white, pygame.Rect(16*(x+self.x)+gridx,    16*(y+self.y)+gridy+15, 16,  1))
            if (x+1,y+1) not in xformed_cells:
                surf.fill(white, pygame.Rect(16*(x+self.x)+gridx+15, 16*(y+self.y)+gridy+15,  1,  1))
            if (x-1,y-1) not in xformed_cells:
                surf.fill(white, pygame.Rect(16*(x+self.x)+gridx,    16*(y+self.y)+gridy,     1,  1))
            if (x+1,y-1) not in xformed_cells:
                surf.fill(white, pygame.Rect(16*(x+self.x)+gridx+15, 16*(y+self.y)+gridy,     1,  1))
            if (x-1,y+1) not in xformed_cells:
                surf.fill(white, pygame.Rect(16*(x+self.x)+gridx,    16*(y+self.y)+gridy+15,  1,  1))

    def render_guides(self, (gridx, gridy)):
        surf = pygame.display.get_surface()
        if self.rotation != 0:
            xformed_cells = set(self.rotations[self.rotation](coord) for coord in self.cells)
        else:
            xformed_cells = self.cells
        left = min(x for x,y in xformed_cells)
        right = max(x for x,y in xformed_cells)
        surf.fill((0,255,0), pygame.Rect(gridx+16*(left+self.x)    , gridy, 1, 16*HEIGHT))
        surf.fill((0,255,0), pygame.Rect(gridx+16*(right+self.x)+15, gridy, 1, 16*HEIGHT))

    def move(self, offx):
        if self.dropFrame: return
        new_x = self.x+offx
        new_x = max(new_x, -min(       self.rotations[self.rotation](coord)[0] for coord in self.cells))
        new_x = min(new_x, WIDTH-1-max(self.rotations[self.rotation](coord)[0] for coord in self.cells))
        self.x = new_x

    def rotate(self):
        if self.dropFrame: return
        self.rotation += 1
        if self.rotation >= len(self.rotations): self.rotation=0
        self.y = -min(self.rotations[self.rotation](coord)[1] for coord in self.cells)
        self.x = max(self.x, -min(       self.rotations[self.rotation](coord)[0] for coord in self.cells))
        self.x = min(self.x, WIDTH-1-max(self.rotations[self.rotation](coord)[0] for coord in self.cells))

    def drop(self, column, rotation):
        self.cells = set(self.rotations[rotation](c) for c in self.cells)
        self.rotation = 0
        self.x = column
        self.opacity = 5
        self.y = min( playfield.column_heights[x] - max([y for x2,y in self.cells if x2+self.x==x]+[-1000])
                      for x in xrange(WIDTH)) - 1

        for x,y in self.cells:
            if y+self.y < playfield.column_heights[x+self.x]:
                playfield.update_column_heights(x+self.x, y+self.y)
            playfield.occupancy[y+self.y][x+self.x] = self
        playfield.pieces.add(self)

    def destroy(self):
        playfield.pieces.remove(self)
        for x,y in self.cells:
            playfield.occupancy[y+self.y][x+self.x] = None
            if y+self.y == playfield.column_heights[x+self.x]:
                try:
                    playfield.column_heights[x+self.x] = min(idx for idx, row in enumerate(playfield.occupancy)
                                                                 if row[x+self.x])
                except ValueError:
                    playfield.column_heights[x+self.x] = HEIGHT
                playfield.streaks[x+self.x] = (playfield.column_heights[x+self.x],0)

    def above(self):
        rtn = []
        for x,y in self.cells:
            x += self.x
            y += self.y-1
            val = playfield.occupancy[y][x]
            if val and val != self:
                rtn.append((x,val))
        return rtn

    def below(self):
        rtn = []
        for x,y in self.cells:
            x += self.x
            y += self.y+1
            if y == HEIGHT:
                val = True
            else:
                val = playfield.occupancy[y][x]
            if val and val != self:
                rtn.append((x,val))
        return rtn

    def do_physics(self):
        forces = dict((c, v.forces.get(c,0)) for c, v in self.above())
        cg = sum(x for x,y in self.cells)/10 + self.x
        forces[cg] = forces.get(cg,0) + 100   # Each block is 10 ?N
        force  = sum(forces.values())
        below = [k for k,v in self.below()]

        ecg = sum([c*f for c,f in forces.iteritems()]) / force
        if ecg in below:
            self.forces = {}
            self.forces[ecg] = force
        elif not len(below) or ecg > max(below) or ecg < min(below):
            return True
        else:
            self.forces = {}
            self.forces[max(k for k in below if k < ecg)] = force/2
            self.forces[min(k for k in below if k > ecg)] = force/2

        self.last_physics = frameno
        return False

moveDirection = 0
moveStart = 0

def H_EVENT_reset():
    global playfield, next_piece
    playfield = Playfield()
    next_piece = {'Server': Piece(WIDTH/4), 'Client': Piece(3*WIDTH/4)}
    global moveDirection
    moveDirection = 0

def H_EVENT_randomize(x):
    random.seed(int(x))

def H_EVENT_drop(role, col, rot):
    global next_piece
    next_piece[role].drop(int(col), int(rot))
    next_piece[role] = Piece({'Server': WIDTH/4, 'Client': 3*WIDTH/4}[role])

def tick():
    playfield.tick()
    if next_piece[role].dropFrame:
        next_piece[role].opacity += 1
        next_piece[role].opacity = min(5,next_piece[role].opacity)
    if moveDirection:
        next_piece[role].move(moveDirection)
    gc.collect()

# Game Display
def render_frame():
    pygame.display.get_surface().fill((0,0,0))
    playfield.render((0,0))
    next_piece[role].render_guides((0,0))
    next_piece[role].render((0,0))
    pygame.display.flip()

# Input Handlers
#def H_PYGAME_MouseButtonDown(pos, **kwargs):
#    event_manager.add_event('clear', pos[0], pos[1])

def H_PYGAME_KeyDown(key, **kwargs):
    global moveDirection, moveStart
    if key in (pygame.K_q, pygame.K_ESCAPE):
        event_manager.add_event('quit')
    if key == pygame.K_r:
        event_manager.add_event('reset')
    elif key == pygame.K_LEFT:
        moveStart = frameno
        moveDirection = -1
    elif key == pygame.K_RIGHT:
        moveStart = frameno
        moveDirection =  1
    elif key == pygame.K_DOWN:
        next_piece[role].dropFrame = frameno+5
        event_manager.add_event('drop', role, next_piece[role].x, next_piece[role].rotation)
    elif key == pygame.K_UP:
        next_piece[role].rotate()

def H_PYGAME_KeyUp(key, **kwargs):
    global moveDirection
    if key == pygame.K_RIGHT:
        moveDirection = 0
    if key == pygame.K_LEFT:
        moveDirection = 0

def H_EVENT_quit():
    sys.exit(0)
