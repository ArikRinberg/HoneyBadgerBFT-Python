import unittest
import gevent
import random
from gevent.queue import Queue
from honeybadgerbft.core.commoncoin import shared_coin
from honeybadgerbft.crypto.threshsig.boldyreva import dealer
from mytest.mysockettest.socket_node import Node



def simple_router(N, maxdelay=0.01, seed=None):
    """Builds a set of connected channels, with random delay
    @return (receives, sends)
    """
    rnd = random.Random()

    host = "127.0.0.1"
    port_base = int(rnd.random() * 5 + 1) * 10000
    addresses = [(host, port_base + 200 * i) for i in range(N)]
    queues = [Queue() for _ in range(N)]
    nodes = [Node(port=addresses[i][1], i=i, nodes_list=addresses, queue=queues[i]) for i in range(N)]

    for node in nodes:
        node.start()

    for node in nodes:
        node.connect_all()

    def makeBroadcast(i):
        def _send(j, o):
            gevent.spawn(nodes[i].send(j, o))
        def _bc(o):
            for j in range(N): _send(j, o)
        return _bc

    def makeRecv(j):
        def _recv():
            (i,o) = nodes[j].recv()
            return (i,o)
        return _recv

    return ([makeBroadcast(i) for i in range(N)],
            [makeRecv(j)      for j in range(N)])



### Test
def _test_commoncoin(N=4, f=1, seed=None):
    # Generate keys
    PK, SKs = dealer(N, f+1)
    sid = 'sidA'
    # Test everything when runs are OK
    #if seed is not None: print 'SEED:', seed
    rnd = random.Random(seed)
    router_seed = rnd.random()
    sends, recvs = simple_router(N, seed=seed)
    coins = [shared_coin(sid, i, N, f, PK, SKs[i], sends[i], recvs[i]) for i in range(N)]

    for i in range(10):
        threads = [gevent.spawn(c, i) for c in coins]
        gevent.joinall(threads)
        assert len(set([t.value for t in threads])) == 1
    return True


def test_commoncoin():
    _test_commoncoin()



if __name__ == "__main__":
    test_commoncoin()
