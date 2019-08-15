import random

import gevent
from gevent import Greenlet
from gevent.queue import Queue
from pytest import mark, raises

from honeybadgerbft.core.reliablebroadcast import reliablebroadcast, encode, decode
from honeybadgerbft.core.reliablebroadcast import hash, merkleTree, getMerkleBranch, merkleVerify

from mytest.mysockettest.socket_node import Node

### Merkle tree
def test_merkletree0():
    mt = merkleTree(["hello"])
    assert mt == [b'', hash("hello")]

def test_merkletree1():
    strList = ["hello","hi","ok"]
    mt = merkleTree(strList)
    roothash = mt[1]
    assert len(mt) == 8
    for i in range(3):
        val = strList[i]
        branch = getMerkleBranch(i, mt)
        assert merkleVerify(3, val, roothash, branch, i)

### Zfec
def test_zfec1():
    K = 3
    N = 10
    m = b"hello this is a test string"
    stripes = encode(K, N, m)
    assert decode(K, N, stripes) == m
    _s = list(stripes)
    # Test by setting some to None
    _s[0] = _s[1] = _s[4] = _s[5] = _s[6] = None
    assert decode(K, N, _s) == m
    _s[3] = _s[7] = None
    assert decode(K, N, _s) == m
    _s[8] = None
    with raises(ValueError) as exc:
        decode(K, N, _s)
    assert exc.value.args[0] == 'Too few to recover'

def simple_router(N, maxdelay=0, seed=None):
    """Builds a set of connected channels, with random delay

    :return: (receives, sends)
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

    def makeRecv(j):
        def _recv():
            (i, o) = nodes[j].recv()
            return (i, o)
        return _recv

    def makeSend(i):
        def _send(j, o):
            gevent.spawn(nodes[i].send(j, o))
        return _send

    return ([makeSend(i) for i in range(N)],
            [makeRecv(j) for j in range(N)])




def _test_rbc1(N=4, f=1, leader=None, seed=None):
    # Test everything when runs are OK
    #if seed is not None: print 'SEED:', seed
    sid = 'sidA'
    rnd = random.Random(seed)
    router_seed = rnd.random()
    if leader is None: leader = rnd.randint(0,N-1)
    sends, recvs = simple_router(N, seed=seed)
    threads = []
    leader_input = Queue(1)
    for i in range(N):
        input = leader_input.get if i == leader else None
        t = Greenlet(reliablebroadcast, sid, i, N, f, leader, input, recvs[i], sends[i])
        t.start()
        threads.append(t)

    m = b"Hello! This is a test message."
    leader_input.put(m)
    gevent.joinall(threads)
    for t in threads:
        print(t.value)
    assert [t.value for t in threads] == [m]*N


def test_rbc1(N, f, seed):
    _test_rbc1(N=N, f=f, seed=seed)


if __name__ == '__main__':
    test_rbc1(4, 1, None)
