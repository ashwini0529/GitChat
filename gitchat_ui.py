#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2016 Shubhodeep Mukherjee
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import urwid
from collections import deque
from threading import Thread
import threading

import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(('go-myvit.eastasia.cloudapp.azure.com',1025))


class FocusMixin(object):
    def mouse_event(self, size, event, button, x, y, focus):
        if focus and hasattr(self, '_got_focus') and self._got_focus:
            self._got_focus()
        return super(FocusMixin,self).mouse_event(size, event, button, x, y, focus)

class ListView(FocusMixin, urwid.ListBox):
    def __init__(self, model, got_focus, max_size=None):
        urwid.ListBox.__init__(self,model)
        self._got_focus=got_focus
        self.max_size=max_size
        self._lock=threading.Lock()

    def add(self,line):
        with self._lock:
            was_on_end=self.get_focus()[1] == len(self.body)-1
            if self.max_size and len(self.body)>self.max_size:
                del self.body[0]
            self.body.append(urwid.Text(line))
            last=len(self.body)-1
            if was_on_end:
                self.set_focus(last,'above')



class Input(FocusMixin, urwid.Edit):
    signals=['line_entered']
    def __init__(self, got_focus=None):
        urwid.Edit.__init__(self)
        self.history=deque(maxlen=1000)
        self._history_index=-1
        self._got_focus=got_focus

    def keypress(self, size, key):
        if key=='enter':
            line=self.edit_text.strip()
            if line:
                urwid.emit_signal(self,'line_entered', line)
                self.history.append(line)
            self._history_index=len(self.history)
            self.edit_text=u''
        if key=='up':

            self._history_index-=1
            if self._history_index< 0:
                self._history_index= 0
            else:
                self.edit_text=self.history[self._history_index]
        if key=='down':
            self._history_index+=1
            if self._history_index>=len(self.history):
                self._history_index=len(self.history)
                self.edit_text=u''
            else:
                self.edit_text=self.history[self._history_index]
        else:
            urwid.Edit.keypress(self, size, key)



class Commander(urwid.Frame):
    """ Simple terminal UI with command input on bottom line and display frame above
similar to chat client etc.
Initialize with your Command instance to execute commands
and the start main loop Commander.loop().
You can also asynchronously output messages with Commander.output('message') """

    class Exit(object):
        pass

    PALLETE=[('reversed', urwid.BLACK, urwid.LIGHT_GRAY),
              ('normal', urwid.LIGHT_GRAY, urwid.BLACK),
              ('error', urwid.LIGHT_RED, urwid.BLACK),
              ('green', urwid.DARK_GREEN, urwid.BLACK),
              ('blue', urwid.LIGHT_BLUE, urwid.BLACK),
              ('magenta', urwid.DARK_MAGENTA, urwid.BLACK), ]


    def __init__(self, title,login, command_caption='Command: (Tab to switch focus to upper frame, where you can scroll text)\nType exit or quit to close', max_size=1000):
        self.header=urwid.Text(title)
        self.model=urwid.SimpleListWalker([])
        self.body=ListView(self.model, lambda: self._update_focus(False), max_size=max_size )
        self.input=Input(lambda: self._update_focus(True))
        foot=urwid.Pile([urwid.AttrMap(urwid.Text(command_caption), 'reversed'),
                        urwid.AttrMap(self.input,'normal')])
        urwid.Frame.__init__(self,
                             urwid.AttrWrap(self.body, 'normal'),
                             urwid.AttrWrap(self.header, 'reversed'),
                             foot)
        self.set_focus_path(['footer',1])
        self._focus=True
        urwid.connect_signal(self.input,'line_entered',self.on_line_entered)
        self._output_styles=[s[0] for s in self.PALLETE]
        self.eloop=None
        self.login = login

    def loop(self, handle_mouse=False):
        self.eloop=urwid.MainLoop(self, self.PALLETE, handle_mouse=handle_mouse)
        self._eloop_thread=threading.current_thread()
        self.eloop.run()

    def on_line_entered(self,line):
        if line in ['exit','quit']:
            s.send('exit '+self.login.USERNAME+' '+self.login.REPO_URI)
            s.close()
            raise urwid.ExitMainLoop()
        s.send('['+self.login.USERNAME+']: '+line+' '+self.login.REPO_URI)

    def output(self, line, style=None):
        if style and style in self._output_styles:
                line=(style,line)
        self.body.add(line)
        #since output could be called asynchronously form other threads we need to refresh screen in these cases
        if self.eloop and self._eloop_thread != threading.current_thread():
            self.eloop.draw_screen()


    def _update_focus(self, focus):
        self._focus=focus

    def switch_focus(self):
        if self._focus:
            self.set_focus('body')
            self._focus=False
        else:
            self.set_focus_path(['footer',1])
            self._focus=True

    def keypress(self, size, key):
        if key=='tab':
            self.switch_focus()
        return urwid.Frame.keypress(self, size, key)



class Execute(Commander):
    def __init__(self,login):
        s.send("first "+login.REPO_URI+" "+login.USERNAME)
        c=Commander('['+login.USERNAME+'] GitChat @'+login.REPO_URI, login)

        def run():
            try:
                stored_chat = open('.git/.gitchat_store','rw')
                read = stored_chat.read()
                for i in read.split('\n'):
                    if login.USERNAME in i.split(' ')[0]:
                        c.output(i, 'green')
                    else:
                        c.output(i, 'blue')
            except:
                pass
            while True:
                msg = s.recv(4096)
                store_chat = open('.git/.gitchat_store','a')
                msg = msg.replace(login.REPO_URI,'')
                li = msg.split('\n')
                for i in li:
                    store_chat.write(i+"\n")
                    if login.USERNAME in i.split(' ')[0]:
                        c.output(i, 'green')
                    else:
                        c.output(i, 'blue')


        t=Thread(target=run)
        t.daemon=True
        t.start()

        #start main loop
        c.loop()
