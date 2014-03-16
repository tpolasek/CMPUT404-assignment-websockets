#!/usr/bin/env python
# coding: utf-8
# Copyright (c) 2013-2014 Abram Hindle
# Modified by (2014) Benson Trinh
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import flask
from flask import Flask, request, redirect, url_for, make_response
from flask_sockets import Sockets
import gevent
from gevent import queue
import time
import json
import os

app = Flask(__name__)
sockets = Sockets(app)
app.debug = True

clients = list()

class World:
    def __init__(self):
        self.clear()
        # we've got listeners now!
        self.listeners = list()

    def add_set_listener(self, listener):
        self.listeners.append( listener )

    def update(self, entity, key, value):
        entry = self.space.get(entity,dict())
        entry[key] = value
        self.space[entity] = entry
        self.update_listeners( entity )

    def set(self, entity, data):
        self.space[entity] = data
        self.update_listeners( entity )

    def update_listeners(self, entity):
        '''update the set listeners'''
        for listener in self.listeners:
            listener(entity, self.get(entity))

    def clear(self):
        self.space = dict()

    def get(self, entity):
        return self.space.get(entity,dict())

    def world(self):
        return self.space

myWorld = World()

class Client:
    def __init__(self):
        self.queue = queue.Queue()

    def put(self, v):
        self.queue.put_nowait(v)

    def get(self):
        return self.queue.get()

def set_listener( entity, data ):
    r = dict()
    r[entity] = data

    send_all_json( r )

def send_all( data ):
    for client in clients:
        client.put( data )

def send_all_json( data ):
    send_all( json.dumps( data ))

myWorld.add_set_listener( set_listener )


@app.route('/')
def hello():
    return redirect(url_for('static',filename='index.html'))

def read_ws(ws,client):
    '''A greenlet function that reads from the websocket and updates the world'''
    try:
        while True:
            msg = ws.receive()
            #print "WS RECV %s" % msg
            if msg is not None:
                packet = json.loads(msg)
                #print packet
                # Receive each key and packet as they are updated and update 
                # the current world with it. 
                # The set function has the set listener to send the data to all clients
                for k, data in packet.iteritems():
                    #print "(k, data) is (%s,%s)" % (k,data)
                    myWorld.set(k,data)
            else:
                break
    except:
        pass

@sockets.route('/subscribe')
def subscribe_socket(ws):
    '''Fufill the websocket URL of /subscribe, every update notify the
       websocket and read updates from the websocket '''
    client = Client()
    clients.append(client)
    g = gevent.spawn( read_ws, ws, client )

    try:
        while True:
            msg = client.get()
            ws.send(msg)

    except Exception as e:

        print "WS Error %s" % e

    finally:
        clients.remove(client)
        gevent.kill(g)

if __name__ == "__main__":
    ''' This doesn't work well anymore:
        pip install gunicorn
        and run
        gunicorn -k flask_sockets.worker sockets:app
    '''
    app.run()
