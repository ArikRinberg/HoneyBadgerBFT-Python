import sys
sys.path.insert(0, "/home/ubuntu/HoneyBadgerBFT-Python")

import random
from collections import defaultdict

import gevent
from gevent import monkey
from gevent.event import Event
from gevent.queue import Queue

import honeybadgerbft.core.honeybadger
#reload(honeybadgerbft.core.honeybadger)
from honeybadgerbft.core.honeybadger import HoneyBadgerBFT
from honeybadgerbft.crypto.threshsig.boldyreva import dealer
from honeybadgerbft.crypto.threshenc import tpke
from honeybadgerbft.core.honeybadger import BroadcastTag

from misc.encodeDecode import deepEncode, deepDecode

from gevent.queue import *
from gevent import Greenlet, sleep
from gevent.server import StreamServer
import threading
from socket import error as SocketError

import time
import socks
import socket
import struct
import math
import pickle

from multiprocessing import Process

monkey.patch_all()

def int_to_bytes(x: int) -> bytes:
    return x.to_bytes((x.bit_length() + 7) // 8, 'big')

def int_from_bytes(xbytes: bytes) -> int:
    return int.from_bytes(xbytes, 'big')

msgTypeCounter = [[0, 0] for _ in range(8)]

def goodread(f, length):
    ltmp = length
    buf = []
    while ltmp > 0:
        buf.append(f.read(ltmp))
        ltmp -= len(buf[-1])
    return ''.join(buf)

def listen_to_channel(port):
    q = Queue()
    def _handle(socket, address):
        #f = socket.makefile(mode='rb')
        f = socket.makefile()
        while True:
            msglength, = struct.unpack('<I', goodread(f, 4))
            line = goodread(f, msglength)
            obj = decode(line)
            q.put(obj[1:])
    server = StreamServer(('127.0.0.1', port), _handle)
    server.start()
    return q

msgCounter = [0] * 4

def connect_to_channel(hostname, port, party):
    global msgCounter
    retry = True
    s = None
    while retry:
      try:
        s = socks.socksocket()
        s.connect((hostname, port))
        retry = False
      except Exception:  # socks.SOCKS5Error:
        retry = True
        sleep(1)
        if s is not None:
            s.close()
    q = Queue()
    def _handle():
        while True:
            msgCounter[party] += 1
            obj = q.get()
            content = deepEncode(msgCounter[party], obj)
            try:
                s.sendall(struct.pack('<I', len(content)) + content)
            except SocketError:
                print("Error sending")
    gtemp = Greenlet(_handle)
    gtemp.parent_args = (hostname, port, party)
    gtemp.name = 'connect_to_channel._handle'
    gtemp.start()
    return q

def simple_router(N, maxdelay=0, seed=None):
    """Builds a set of connected channels, with random delay

    :return: (receives, sends)
    """
    
    BASE_SOCKET = 50000
    #rnd = random.Random(seed)
    #sendSockets = [socket.socket(socket.AF_INET, socket.SOCK_STREAM) for _ in range(N)]
    #recvSockets = [socket.socket(socket.AF_INET, socket.SOCK_STREAM) for _ in range(N)]
    #queues = [Queue() for _ in range(N)]
    #_threads = []
        
    def makeSend(i):
        connQueues = [connect_to_channel('127.0.0.1', BASE_SOCKET+p, p) for p in range(N)]
        def _send(j, o):
            connQueues[j].put((j, i, o))
        return _send

    def makeRecv(j):
        q = listen_to_channel(BASE_SOCKET + j)
        def _recv():
            (i,o) = q.get()
            print(j, "got (i,o):", (i,o))
            return (i,o)
        return _recv

    #return ([makeSend(i) for i in range(N)],
    #        [makeRecv(j) for j in range(N)])
    return ([makeRecv(i) for i in range(N)],
            [makeSend(j) for j in range(N)])

### Test asynchronous common subset
def _test_honeybadger(N=4, f=1, seed=None):
    sid = 'sidA'
    # Generate threshold sig keys
    sPK, sSKs = dealer(N, f+1, seed=seed)

    # Generate threshold enc keys
    ePK, eSKs = tpke.dealer(N, f+1)

    rnd = random.Random(seed)
    #print 'SEED:', seed
    router_seed = rnd.random()
    recvs, sends = simple_router(N, seed=router_seed)

    badgers = [None] * N
    threads = [None] * N
    
    # This is an experiment parameter to specify the maximum round number 
    K = 2




    for i in range(N):
        badgers[i] = HoneyBadgerBFT(sid, i, 1, N, f,
                                    sPK, sSKs[i], ePK, eSKs[i],
                                    sends[i], recvs[i], K)
        #print(sPK, sSKs[i], ePK, eSKs[i])



    for r in range(K):
        for i in range(N):
            #if i == 1: continue
            badgers[i].submit_tx('<[HBBFT Input %d]>' % (i+10*r))

    for i in range(N):
        threads[i] = gevent.spawn(badgers[i].run)



    print('start the test...')
    time_start=time.time()

    #gevent.killall(threads[N-f:])
    #gevent.sleep(3)
    #for i in range(N-f, N):
    #    inputs[i].put(0)
    gevent.sleep(5)
    print("Starting")
    try:
        outs = [threads[i].get() for i in range(N)]
        print("Outs") 
        print(outs)
        # Consistency check
        assert len(set(outs)) == 1
    except KeyboardInterrupt:
        print("Exception")
        gevent.killall(threads)
        raise

    time_end=time.time()
    print('complete the test...')
    print('time cost: ', time_end-time_start, 's')


def test_honeybadger():
    try:
      _test_honeybadger()
    finally:
      print("Cleaning up")


if __name__ == '__main__':
    test_honeybadger()
