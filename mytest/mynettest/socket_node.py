import gevent
import pickle

from gevent import Greenlet
from gevent import socket, monkey
from gevent.queue import Queue
from honeybadgerbft.crypto.threshsig.boldyreva import serialize as tsig_serialize, deserialize1 as tsig_deserialize
from honeybadgerbft.crypto.threshenc.tpke import serialize as tenc_serialize, deserialize1 as tenc_deserialize
from honeybadgerbft.core.honeybadger import HoneyBadgerBFT

from multiprocessing import Process
import time, os, logging
import traceback



monkey.patch_all()


def set_logger_of_node(id: int):
    logger = logging.getLogger("node-"+str(id))
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        '%(asctime)s %(filename)s [line:%(lineno)d] %(funcName)s %(levelname)s %(message)s ')
    full_path = os.path.realpath(os.getcwd()) + '/log/' + "node-"+str(id) + ".log"
    file_handler = logging.FileHandler(full_path)
    file_handler.setFormatter(formatter)  # 可以通过setFormatter指定输出格式
    logger.addHandler(file_handler)
    return logger


def address_to_id(address: tuple):
    return int(address[1] % 10000 / 200)


# Network node class: deal with socket communications
class Node(Greenlet):

    SEP = '\r\nS\r\nE\r\nP\r\n'

    def __init__(self, port: int, i: int, addresses_list: list, logger=None):
        self.queue = Queue()
        self.port = port
        self.id = i
        self.addresses_list = addresses_list
        self.socks = [None for _ in self.addresses_list]
        if logger is None:
            self.logger = set_logger_of_node(self.id)
        else:
            self.logger = logger
        Greenlet.__init__(self)

    def _run(self):
        self.logger.info("node %d is running..." % self.id)
        print("node %d is running..." % self.id)
        self._serve_forever()

    def _handle_request(self, sock, address):

        def _finish(e: Exception):
            self.logger.error("node %d's server is closing..." % self.id)
            self.logger.error(str(e))
            print(e)
            print("node %d's server is closing..." % self.id)
            pass

        buf = b''
        try:
            while True:
                gevent.sleep(0)
                buf += sock.recv(4096)
                tmp = buf.split(self.SEP.encode('utf-8'), 1)
                while len(tmp) == 2:
                    buf = tmp[1]
                    data = tmp[0]
                    if data != '' and data:
                        if data == 'ping'.encode('utf-8'):
                            sock.sendall('pong'.encode('utf-8'))
                            self.logger.info("node {} is pinging node {}...".format(address_to_id(address), self.id))
                            print("node {} is pinging node {}...".format(address_to_id(address), self.id))
                        else:
                            (j, o) = (address_to_id(address), pickle.loads(data))
                            assert j in range(len(self.addresses_list))
                            try:
                                (a, (h1, r, (h2, b, e))) = o
                                if h1 == 'ACS_COIN' and h2 == 'COIN':
                                    o = (a, (h1, r, (h2, b, tsig_deserialize(e))))
                                    self.logger.info(str((self.id, (j, o))))
                                    print(self.id, (j, o))
                                    gevent.spawn(self.queue.put_nowait((j, o)))
                                else:
                                    raise ValueError
                            except ValueError as e1:
                                try:
                                    h2, b, e = o
                                    if h2 == 'COIN':
                                        o = (h2, b, tsig_deserialize(e))
                                        #print("pickle loads group element", tsig_deserialize(e))
                                        #print("pickle loads group element type", type(tsig_deserialize(e)))
                                        self.logger.info(str((self.id, (j, o))))
                                        print(self.id, (j, o))
                                        gevent.spawn(self.queue.put_nowait((j, o)))
                                    else:
                                        raise ValueError
                                except ValueError as e2:
                                    try:
                                        (a, (h1, b, e)) = o
                                        if h1 == 'TPKE':
                                            #print("resolve problem tpke", o)
                                            e1 = [None] * len(e)
                                            for i in range(len(e)):
                                                e1[i] = tenc_deserialize(e[i])
                                            o = (a, (h1, b, e1))
                                            self.logger.info(str((self.id, (j, o))))
                                            print(self.id, (j, o))
                                            gevent.spawn(self.queue.put_nowait((j, o)))
                                        else:
                                            raise ValueError
                                    except ValueError as e3:
                                        #print("problem objective", o)
                                        try:
                                            self.logger.info(str((self.id, (j, o))))
                                            print(self.id, (j, o))
                                            gevent.spawn(self.queue.put_nowait((j, o)))
                                        except Exception as e4:
                                            self.logger.error(str(("problem objective", o, e1, e2, e3, e4, traceback.print_exc())))
                                            print("problem objective", o)
                                            print(e1)
                                            print(e2)
                                            print(e3)
                                            print(e4)
                                            traceback.print_exc()
                    else:
                        #print(data)
                        self.logger.info('syntax error messages')
                        print('syntax error messages')
                        raise Exception
                    tmp = buf.split(self.SEP.encode('utf-8'), 1)
        except Exception as e:
            self.logger.error(str((e, traceback.print_exc())))
            print(e)
            traceback.print_exc()
            _finish(e)

    def _serve_forever(self):
        self.server_sock = socket.socket()
        self.server_sock.bind(("", self.port))
        self.server_sock.listen(50)
        while True:
            sock, address = self.server_sock.accept()
            gevent.spawn(self._handle_request, sock, address)
            self.logger.info('node id %d accepts a new socket connection from node %d' % (self.id, address_to_id(address)))
            print('node id %d accepts a new socket connection from node %d' % (self.id, address_to_id(address)))
            gevent.sleep(0)
            #self._handle_request(sock, address)

    def _watchdog_deamon(self):
        #self.server_sock.
        pass

    def connect_all(self):
        self.logger.info("node %d is fully meshing the network" % self.id)
        print("node %d is fully meshing the network" % self.id)
        try:
            for j in range(len(self.addresses_list)):
                self._connect(j)
                #if self.socks[j] is None:
                #print('node id %d:' % j)
                #sock = socket.socket()
                #sock.bind(("", self.port + 10 * j + 1))
                #sock.connect(self.addresses_list[j])
                #sock.sendall(('ping' + self.SEP).encode('utf-8'))
                #pong = sock.recv(4096)
                #if pong.decode('utf-8') == 'pong':
                #    self.logger.info("node {} is ponging node {}...".format(j, self.id))
                #    print("node {} is ponging node {}...".format(j, self.id))
                #    self.socks[j] = sock
                #    continue
                #else:
                #    self.logger.info("fails to build connect from {} to {}".format(self.id, j))
                #    raise Exception
        except Exception as e:
            self.logger.info(str((e, traceback.print_exc())))
            print(e)
            traceback.print_exc()

    def _connect(self, j: int):
        # if self.socks[j] is None:
        # print('node id %d:' % j)
        sock = socket.socket()
        sock.bind(("", self.port + 10 * j + 1))
        sock.connect(self.addresses_list[j])
        sock.sendall(('ping' + self.SEP).encode('utf-8'))
        pong = sock.recv(4096)
        if pong.decode('utf-8') == 'pong':
            self.logger.info("node {} is ponging node {}...".format(j, self.id))
            print("node {} is ponging node {}...".format(j, self.id))
            self.socks[j] = sock
        else:
            self.logger.info("fails to build connect from {} to {}".format(self.id, j))
            raise Exception

    def _send(self, j: int, o: bytes):
        msg = b''.join([o, self.SEP.encode('utf-8')])
        #gevent.sleep(0)
        try:
            self.socks[j].sendall(msg)
        except Exception as e1:
            self.logger.error("fail to send msg")
            print("fail to send msg")
            try:
                self._connect(j)
                self.socks[j].connect(self.addresses_list[j])
                self.socks[j].sendall(msg)
            except Exception as e2:
                self.logger.error(str((e1, e2, traceback.print_exc())))
                print(e1)
                print(e2)
                traceback.print_exc()

    def send(self, j: int, o: object):
        try:
            self._send(j, pickle.dumps(o))
        except Exception as e:
            try:
                (a, (h1, r, (h2, b, e))) = o
                if h1 == 'ACS_COIN' and h2 == 'COIN':
                    o = (a, (h1, r, (h2, b, tsig_serialize(e))))
                    assert tsig_deserialize(tsig_serialize(e)) == e
                    self._send(j, pickle.dumps(o))
                else:
                    raise Exception
            except Exception as e1:
                try:
                    (h2, b, e) = o
                    if h2 == 'COIN':
                        o = (h2, b, tsig_serialize(e))
                        assert tsig_deserialize(tsig_serialize(e)) == e
                        self._send(j, pickle.dumps(o))
                    else:
                        raise Exception
                except Exception as e2:
                    try:
                        (a, (h1, b, e)) = o
                        e1 = [None] * len(e)
                        if h1 == 'TPKE':
                            for i in range(len(e)):
                                e1[i] = tenc_serialize(e[i])
                                assert tenc_deserialize(e1[i]) == e[i]
                            o = (a, (h1, b, e1))
                            self._send(j, pickle.dumps(o))
                        else:
                            raise Exception
                    except Exception as e3:
                        self.logger.error(str(("problem objective", o)))
                        print("problem objective", o)
                        print(e)
                        print(e1)
                        print(e2)
                        print(e3)
                        traceback.print_exc()

    def _recv(self):
        #time.sleep(0.001)
        #try:
        (i, o) = self.queue.get()
        #print("node %d is receving: " % self.id, (i, o))
        return (i, o)
        #except Exception as e:
        #   print(e)
        #   pass

    def recv(self):
        return self._recv()


#
#
# Well defined node class to encapsulate almost everything
class HoneyBadgerBFTNode (HoneyBadgerBFT):

    def __init__(self, sid, id, B, N, f, sPK, sSK, ePK, eSK, addresses_list: list, K=3):
        #Process.__init__(self)
        self.logger = set_logger_of_node(id)
        self.server = Node(i=id, port=addresses_list[id][1], addresses_list=addresses_list, logger=self.logger)
        HoneyBadgerBFT.__init__(self, sid, id, B, N, f, sPK, sSK, ePK, eSK, send=None, recv=None, K=K)

    def start_server(self):
        pid = os.getpid()
        print('pid: ', pid)
        self.logger.info('node id %d is running on pid %d' % (self.id, pid))
        self.server.start()

    def connect_servers(self):
        self.server.connect_all()
        self._send = self.server.send
        self._recv = self.server.recv
        for r in range(self.K):
            tx = '<[HBBFT Input %d]>' % (self.id + 10 * r)
            HoneyBadgerBFT.submit_tx(self, tx)

    def hbbft_instance(self):
        hbbft = gevent.spawn(HoneyBadgerBFT.run(self))
        return hbbft



