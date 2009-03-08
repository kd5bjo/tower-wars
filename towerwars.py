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

import world

FPS = 20
next_frame_time = 0
frameno = 0
fds = set()
event_delay = 5 #frames
world.FPS = FPS
world.frameno = frameno

option_parser = OptionParser()

# Logging Options

option_parser.add_option('-q', '--quiet', action='store_const', const=2, dest='verbosity', default=3, help='Only output warnings and errors')
option_parser.add_option('-v', '--verbose', action='store_const', const=4, dest='verbosity', help='Output debug information about game events')
option_parser.add_option('--trace', action='store_const', const=5, dest='verbosity', help='Output all system events as well as game events (lots of output)')
option_parser.add_option('-l', '--logfile', action='store', type='string', dest='logfile', default='-', help='Destination for log output')

# Networking Options

option_parser.add_option('-s', '--server', action='store_true', dest='server', default=False, help='Run as a server.')
option_parser.add_option('-c', '--client', action='store', dest='ip', type='string', default='0.0.0.0', help='Run as a client, connecting to the server at IP.')
option_parser.add_option('-p', '--port', action='store', dest='port', type='int', default='4242', help='Port number for TCP connections.')

world.add_options(option_parser)

options, args = option_parser.parse_args()

pygame.init()
world.init(options)

class SelectSocket:
    def __init__(self, file):
        self.inbuf  = ''
        self.outbuf = ''
        self.open = True
        self.fileobj = None
        if isinstance(file, int):
            self.fd = file
        elif hasattr(file, 'fileno'):
            self.fd = file.fileno()
            self.fileobj = file
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
        try:
            data = os.read(self.fd, 4096)
            self.inbuf += data
            if not data: self.open = False # EOF
        except OSError:
            self.open = False

    def rts(self):
        return len(self.outbuf)

    def rtr(self):
        return self.open

class Log(SelectSocket):
    def __init__(self):
        if options.logfile == '-':
            SelectSocket.__init__(self, sys.stdout)
        else:
            SelectSocket.__init__(self, os.open(options.logfile, os.O_WRONLY | os.O_APPEND | os.O_CREAT))
        self.verbosity = options.verbosity # Trace execution
        self.desc = {0: 'FATAL', 1: 'ERROR', 2: 'WARN', 3:'INFO', 4:'DEBUG', 5:'TRACE'}
        self.msg(3, 'Logging', 'Log opened')

    def msg(self, level, label, message, **kwargs):
        if level > self.verbosity: return
        self.outbuf += '%8d %5s %17s: %s\t%s\n' % (frameno, self.desc.get(level, level), label, message, kwargs)

log = Log()
world.log = log

fds.add(log)

class EventManager:
    def __init__(self):
        self.cache = {}
        self.state = 'Standalone'
        self.remote_frame = 0
        self.remote_frame_offset = None
        self.rtts = []
        self.handlers = {}

        if options.server:
            self.state = 'Listening'
            self.socket = socket.socket()
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.socket.bind(('0.0.0.0', options.port))
            self.socket.listen(-1)
            log.msg(3, 'Network', 'Listening', port=options.port)
            class ListenSocket:
                def fileno(skt):
                    return self.socket.fileno()
                def rts(skt):
                    return False
                def rtr(skt):
                    return True
                def recv(skt):
                    newSocket, remoteAddr = self.socket.accept()
                    self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    self.state = 'Connected'
                    log.msg(3, 'Network', 'Connected', ip=remoteAddr[0], port=remoteAddr[1])
                    fds.remove(skt)
                    self.socket = SelectSocket(newSocket)
                    fds.add(self.socket)
            fds.add(ListenSocket())
        elif options.ip != '0.0.0.0':
            try:
                self.socket = socket.socket()
                self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self.socket.connect((options.ip, options.port))
                log.msg(3, 'Network', 'Connected', ip=self.socket.getpeername()[0], port=self.socket.getpeername()[1])
                self.state = 'Connected'
            except:
               sys.exit(1)
            self.socket = SelectSocket(self.socket)
            fds.add(self.socket)
                
    def run_events(self):
        if (frameno - 1) in self.cache:
            del self.cache[frameno - 1]
        if self.state in ('Connected', 'Synchronized'):
            remote_events = self.socket.inbuf.splitlines(True)
            if remote_events and remote_events[-1][-1] not in '\r\n':
                self.socket.inbuf = remote_events[-1]
                remote_events = remote_events[:-1]
            else:
                self.socket.inbuf = ''
            for ev in remote_events:
                timestamp, args = ev.split(None, 1)
                args = args.split()
                timestamp = int(timestamp)
                log.msg(5, 'RemoteEvent', args[0], remote=timestamp, args=args[1:])
                if self.state == 'Synchronized':
                    if args[0] not in ('ping', 'synchronize'):
                        self.add_remote_event(args, timestamp)
                elif self.state == 'Connected':
                    assert args[0] in ('ping', 'synchronize')
                    if args[0] == 'ping':
                        self.remote_frame = timestamp
                        if int(args[1]) != 0:
                            self.rtts.append(frameno - int(args[1]))
                            log.msg(5, 'Clock', 'AddedRTT', start=int(args[1]), value=self.rtts[-1], remote=timestamp)
                            if options.server and len(self.rtts) >= 30:
                                self.state = 'Synchronized'
                                rtt = sum(self.rtts)/(2*len(self.rtts))
                                self.remote_frame_offset = frameno - timestamp + rtt
                                log.msg(3, 'Clock', 'Synchronized', rtt=rtt, frame_offset=self.remote_frame_offset)
                                self.socket.outbuf += '%d synchronize %d\n' % \
                                    (frameno, frameno-self.remote_frame_offset)
                                self.add_event('randomize', random.getrandbits(32))
                                self.add_event('reset')
                    if args[0] == 'synchronize':
                        rtt = sum(self.rtts)/(2*len(self.rtts))
                        self.state = 'Synchronized'
                        self.remote_frame_offset = int(args[1]) - timestamp
                        log.msg(3, 'Clock', 'Synchronized', rtt=rtt, frame_offset=self.remote_frame_offset)
            if self.state == 'Connected':
                self.socket.outbuf += '%d ping %d\n' % (frameno, self.remote_frame)
        for ev in pygame.event.get():
            log.msg(5, 'PygameEvent', pygame.event.event_name(ev.type), **ev.dict)
            func_name = 'H_PYGAME_%s' % pygame.event.event_name(ev.type)
            if hasattr(world, func_name):
                getattr(world, func_name)(**ev.dict)
    
        precedence = ['remote', 'local']
        if options.server: precedence = ['local', 'remote']

        world.frameno = frameno

        for p in precedence:
            for ev in (e for e in self.cache.get(frameno, []) if e[0] == p):
                log.msg(4, 'Event', ev[1], args=ev[2:])
                func_name = 'H_EVENT_%s' % ev[1]
                if hasattr(world, func_name):
                    getattr(world, func_name)(*ev[2:])
                else:
                    log.msg(2, 'Event', 'UndefinedHandler', func=func_name, args=ev[2:])
        world.tick()

    def add_event(self, *event):
        self.add_delayed_event(event_delay, *event)

    def add_delayed_event(self, delay, *event):
        delay = max(delay, event_delay)
        if (frameno + delay) not in self.cache:
            self.cache[frameno + delay] = []
        event = [str(e) for e in event]
        self.cache[frameno + delay].append(['local']+event)
        if self.state == 'Synchronized':
            self.socket.outbuf += '%d %s\n' % (frameno + delay, ' '.join(event))

    def add_remote_event(self, event, time):
        time += self.remote_frame_offset
        assert time >= frameno
        if time not in self.cache:
            self.cache[time] = []
        self.cache[time].append(['remote']+event)

event_manager = EventManager()
world.event_manager = event_manager

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
            try: world.render_frame()
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
        try: event_manager.run_events()
        except Exception, e:
            log.msg(1, 'RunEvents', traceback.format_exception_only(type(e),e)[-1].strip())
            traceback.print_exc()
except BaseException, e:
    log.flush()
