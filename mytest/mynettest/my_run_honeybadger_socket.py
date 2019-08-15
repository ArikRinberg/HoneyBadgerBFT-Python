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


monkey.patch_all()


### Test asynchronous common subset
def _test_honeybadger_1(N=4, f=1, seed=None):

    def socket_router(N, maxdelay=0, seed=None):
        """Builds a set of connected channels, with random delay

        :return: (receives, sends)
        """
        rnd = random.Random()

        host = "127.0.0.1"
        port_base = int(rnd.random() * 5 + 1) * 10000
        addresses = [(host, port_base + 200 * i) for i in range(N)]
        # queues = [Queue() for _ in range(N)]
        # nodes = [Node(port=addresses[i][1], i=i, nodes_list=addresses, queue=queues[i]) for i in range(N)]
        nodes = [Node(port=addresses[i][1], i=i, addresses_list=addresses) for i in range(N)]

        for node in nodes:
            node.start()

        for node in nodes:
            node.connect_all()

        def makeRecv(j):
            def _recv():
                (i, o) = nodes[j].recv()
                return (i, o)

            return _recv

        def makeSend(i):
            def _send(j, o):
                nodes[i].send(j, o)

            return _send

        return ([makeSend(i) for i in range(N)],
                [makeRecv(j) for j in range(N)])

    sid = 'sidA'
    # Generate threshold sig keys
    sPK, sSKs = dealer(N, f+1, seed=seed)

    # Generate threshold enc keys
    ePK, eSKs = tpke.dealer(N, f+1)

    rnd = random.Random(seed)
    #print 'SEED:', seed
    router_seed = rnd.random()
    sends, recvs = socket_router(N, seed=router_seed)

    badgers = [None] * N
    threads = [None] * N
    
    # This is an experiment parameter to specify the maximum round number 
    K = 2

    for i in range(N):
        badgers[i] = HoneyBadgerBFT(sid, i, 1, N, f,
                                    sPK, sSKs[i], ePK, eSKs[i],
                                    sends[i], recvs[i], K)

    for r in range(K):
        for i in range(N):
            badgers[i].submit_tx('<[HBBFT Input %d]>' % (i+10*r))

    print('start the test...')
    time_start=time.time()

    # threads
    for i in range(N):
        threads[i] = gevent.spawn(badgers[i].run)
    try:
        outs = [threads[i].get() for i in range(N)]
        print(outs)
        # Consistency check
        assert len(set(outs)) == 1
    except KeyboardInterrupt:
        gevent.killall(threads)
        raise

    time_end = time.time()
    print('complete the test...')
    print('time cost: ', time_end-time_start, 's')




def _test_honeybadger_2(N=4, f=1, seed=None):

    def run_hbbft_instance(badger: HoneyBadgerBFTNode):

        # lock.acquire()
        # print(pid, "gets lock to start server")
        badger.start_server()
        # lock.release()
        # print(pid, "releases lock after starting server")

        time.sleep(2)
        gevent.sleep(2)

        # lock.acquire()
        # print(pid, "gets lock to fully connect")
        badger.connect_servers()
        # lock.release()
        # print(pid, "releases lock after fully connecting")

        gevent.spawn(badger.run())
        #return thread

    rnd = random.Random(seed)
    sid = 'sidA'

    # Generate threshold sig keys
    sPK, sSKs = dealer(N, f+1, seed=seed)

    # Generate threshold enc keys
    ePK, eSKs = tpke.dealer(N, f+1)

    # Nodes list
    host = "127.0.0.1"
    port_base = int(rnd.random() * 5 + 1) * 10000
    addresses = [(host, port_base + 200 * i) for i in range(N)]

    K = 2
    badgers = [None] * N
    processes = [None] * N
    threads = [None] * N

    for i in range(N):
        badgers[i] = HoneyBadgerBFTNode(sid, i, 1, N, f,
                            sPK, sSKs[i], ePK, eSKs[i],
                            addresses_list=addresses, K=K)

    for i in range(N):
        processes[i] = Process(target=run_hbbft_instance, args=(badgers[i], ))
        processes[i].start()
        processes[i].join()

    while True:
        time.sleep(5)
        print("parent is waiting...")


# Test by threads
def test_honeybadger_thread():
    _test_honeybadger_1()

# Test by processes
def test_honeybadger_proc():
    _test_honeybadger_2()

if __name__ == '__main__':
    #test_honeybadger_thread()
    test_honeybadger_proc()
    #_test_honeybadger_0()
