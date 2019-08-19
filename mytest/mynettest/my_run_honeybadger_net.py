import sys
sys.path.append('/home/ubuntu/HoneyBadgerBFT-Python')


import random
import gevent
from gevent import monkey
from gevent.queue import Queue

import honeybadgerbft.core.honeybadger
#reload(honeybadgerbft.core.honeybadger)
from honeybadgerbft.core.honeybadger import HoneyBadgerBFT
from honeybadgerbft.crypto.threshsig.boldyreva import dealer
from honeybadgerbft.crypto.threshenc import tpke
from honeybadgerbft.core.honeybadger import BroadcastTag

import time, logging, os
import multiprocessing
from multiprocessing import Process, Pool, Lock, Manager
from mytest.mynettest.net_node import Node, HoneyBadgerBFTNode

import pickle


monkey.patch_all()

def loadAddresses(fileName = "addresses.config"):
    addresses = []
    with open(fileName, 'r') as fh:
        line = fh.readline().strip()
        while line:
            if ":" in line:
                [add, port] = line.split(":")
                addresses += [(add, int(port))]
            line = fh.readline().strip()
    return addresses

def loadKeys():
    (sPK, sSKs, ePK, eSKs) = (None, None, None, None) 
    sid = 'sidA'
    with open("sPK.p", "rb") as fh:
        sPK = pickle.load(fh)
    with open("sSKs.p", "rb") as fh:
        sSKs = pickle.load(fh)
    with open("ePK.p", "rb") as fh:
        ePK = pickle.load(fh)
    with open("eSKs.p", "rb") as fh:
        eSKs = pickle.load(fh)
    return (sPK, sSKs, ePK, eSKs)


def _test_honeybadger(i: int, K=2, N=4, f=1, seed=None):
    def run_hbbft_instance(badger: HoneyBadgerBFTNode):
            badger.start_server()

            time.sleep(2)
            gevent.sleep(2)

            badger.connect_servers()

            gevent.spawn(badger.run())
   
    rnd = random.Random(seed)
    sid = 'sidA'

    #load keys
    (sPK, sSKs, ePK, eSKs) = loadKeys()

    # Nodes list
    #host = "127.0.0.1"
    #port_base = int(rnd.random() * 5 + 1) * 10000
    #port_base = 10000
    #addresses = [(host, port_base + 200 * i) for i in range(N)]
    addresses = loadAddresses()
        
    badger = HoneyBadgerBFTNode(sid, i, 1, N, f,
                                sPK, sSKs[i], ePK, eSKs[i],
                                addresses_list=addresses, K=K)

    badger.start_server()
    time.sleep(2)
    gevent.sleep(2)

    badger.connect_servers()
    start_time = time.time()
    badger.run()
    end_time = time.time()
    print("Elapsed time in seconds:", end_time-start_time)

    #process = Process(target=run_hbbft_instance, args=(badger, ))
    #process.start()
    #process.join()
    
    #while True:
     #   time.sleep(5)
     #   print("parent is waiting...")
        #if badger.transaction_buffer == []:
        #  break
    print("Done")


# Test by threads
def test_honeybadger_thread():
    _test_honeybadger_1()

# Test by processes
def test_honeybadger_proc():
    _test_honeybadger_2()

if __name__ == '__main__':
    node = int(sys.argv[1])
    K = 2
    if len(sys.argv) > 2
        K = int(sys.argv[2])
    #test_honeybadger_thread()
    #test_honeybadger_proc()
    _test_honeybadger(node, K)
