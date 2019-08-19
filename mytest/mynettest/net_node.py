import gevent
import pickle

from gevent import Greenlet, sleep
from gevent import socket, monkey
from gevent.queue import Queue
from gevent.server import StreamServer
from honeybadgerbft.crypto.threshsig.boldyreva import serialize as tsig_serialize, deserialize1 as tsig_deserialize
from honeybadgerbft.crypto.threshenc.tpke import serialize as tenc_serialize, deserialize1 as tenc_deserialize
from honeybadgerbft.core.honeybadger import HoneyBadgerBFT

from multiprocessing import Process
from threading import Thread
import time, os, logging
import traceback
import socks



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


def address_to_id(address: tuple, addresses_list, self_id):
    for i, add in enumerate(addresses_list):
        if add[0] == address[0]:
            return i
    return self_id


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
        self.serverThread = None

        Greenlet.__init__(self)
    def _run(self):
        self.logger.info("node %d is running..." % self.id)
        print("node %d is running..." % self.id)
        self.serverThread = Greenlet(self._serve_forever)
        self.serverThread.start()
    def _create_handle_request(self):
        def _handle_request(sock, address):
            def _finish(e: Exception):
                self.logger.error("node %d's server is closing..." % self.id)
                self.logger.error(str(e))
                print(e)
                print("node %d's server is closing..." % self.id)

            buf = b''
            try:
                while True:
                    gevent.sleep(0)
                    #buf = fh.read(4096)
                    buf += sock.recv(4096)
                    tmp = buf.split(self.SEP.encode('utf-8'), 1)
                    while len(tmp) == 2:
                        buf = tmp[1]
                        data = tmp[0]
                        if data != '' and data:
                            if data == 'ping'.encode('utf-8'):
                                sock.sendall('pong'.encode('utf-8'))
                                self.logger.info("node {} is ponging node {}...".format(address_to_id(address, self.addresses_list, self.id), self.id))
                                print("node {} is ponging node {}...".format(address_to_id(address, self.addresses_list, self.id), self.id))
                            else:
                                (j, o) = (address_to_id(address, self.addresses_list, self.id), pickle.loads(data))
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
                                            self.logger.info(str((self.id, (j, o))))
                                            print(self.id, (j, o))
                                            gevent.spawn(self.queue.put_nowait((j, o)))
                                        else:
                                            raise ValueError
                                    except ValueError as e2:
                                        try:
                                            (a, (h1, b, e)) = o
                                            if h1 == 'TPKE':
                                                e1 = [None] * len(e)
                                                for i in range(len(e)):
                                                    if e[i] is not None:
                                                        e1[i] = tenc_deserialize(e[i])
                                                o = (a, (h1, b, e1))
                                                self.logger.info(str((self.id, (j, o))))
                                                print(self.id, (j, o))
                                                gevent.spawn(self.queue.put_nowait((j, o)))
                                            else:
                                                raise ValueError
                                        except ValueError as e3:
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
                            self.logger.info('syntax error messages')
                            print('syntax error messages')
                            raise Exception
                        tmp = buf.split(self.SEP.encode('utf-8'), 1)
            except Exception as e:
                self.logger.error(str((e, traceback.print_exc())))
                print(e)
                traceback.print_exc()
                _finish(e)
        return _handle_request

    def _serve_forever(self):
        def _handle(socket, address):
            t = gevent.spawn(self._create_handle_request(), socket, address)
            t.join()
            #thread = Thread(target=self._handle_request, args=(socket,address))
            #thread.daemon = True
            #thread.start()
            #while True:
            #    gevent.sleep(0)
        server = StreamServer((socket.gethostbyname(socket.gethostname()), self.addresses_list[self.id][1]), _handle)
        server.start()
        print("Started server for node", self.id, "on", self.addresses_list[self.id])
        print(server)

    def _watchdog_deamon(self):
        #self.server_sock.
        pass

    def connect_all(self):
        def try_connect(j):
          try:
            self._connect(j)
          except Exception as e:
            self.logger.info(str((e, traceback.print_exc())))
            print(e)
            traceback.print_exc()
            
        self.logger.info("node %d is fully meshing the network" % self.id)
        print("node %d is fully meshing the network" % self.id)
#        threads = [Thread(target=try_connect, args=(j,)) for j in range(len(self.addresses_list))]
#        for t in threads:
#          t.start()
#        for t in threads:
#          t.join()
         
        try:
            for j in range(len(self.addresses_list)):
                self._connect(j)
        except Exception as e:
            self.logger.info(str((e, traceback.print_exc())))
            print(e)
            traceback.print_exc()

    def _connect(self, j: int):
        retry = True
        sock = None
        while retry:
          try:
            sock = socket.socket()
            sock.bind(("", self.port + 10 * j + 1))
                #sock.connect(self.addresses_list[j])
            #sock = socket.socksocket()
            print("node {} attempting {}".format(self.id, self.addresses_list[j]))
            sock.connect(self.addresses_list[j])
            retry = False
          except Exception as e:  # socks.SOCKS5Error:
            print(e)
            retry = True
            sleep(1)
            if sock is not None:
                sock.close()
        print("node",self.id, "is pinging", j)
        sock.sendall(('ping' + self.SEP).encode('utf-8'))
        gevent.sleep(0)
        pong = sock.recv(4096)
        print(sock)
        self.socks[j] = sock
        if pong.decode('utf-8') == 'pong':
            self.logger.info("node {} is ponging node {}...".format(j, self.id))
            print("node {} is ponging node {}...".format(j, self.id))
        else:
            self.logger.info("fails to build connect from {} to {}".format(self.id, j))
            raise Exception

    def _send(self, j: int, o: bytes):
        msg = b''.join([o, self.SEP.encode('utf-8')])
        try:
            print("{} sending msg to {}".format(self.id, j))
            self.socks[j].sendall(msg)
        except Exception as e1:
            self.logger.error("fail to send msg")
            print("fail to send msg")
            try:
                self._connect(j)
                #self.socks[j].connect(self.addresses_list[j])
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
                                if e[i] is not None:
                                  e1[i] = tenc_serialize(e[i])
                                  assert tenc_deserialize(e1[i]) == e[i]
                            o = (a, (h1, b, e1))
                            pickled = pickle.dumps(o)
                            self._send(j, pickle.dumps(o))
                        else:
                            raise Exception
                    except Exception as e3:
                        self.logger.error(str(("problem objective", o)))
                        print("problem objective", o)
                        print("e:",e)
                        print("e1:",e1)
                        print("e2:",e2)
                        print("e3:",e3)
                        traceback.print_exc()

    def _recv(self):
        (i, o) = self.queue.get()
        return (i, o)

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

