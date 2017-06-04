#!/usr/bin/env python
# encoding: utf-8
# bug fix, plz contact ringzero@0x557.org

import sys
import socket
import threading
import argparse
import logging
from time import sleep
import struct

logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s',
)

buffsize = 4096
pool = range(30)
tcplist={}

class PortMap(object):
    """docstring for PortMap"""
    def __init__(self, ltcp_addr, ltcp_port, ludp_addr, ludp_port):
        super(PortMap, self).__init__()
        self.udp_clnt = None
        self.udp_host = None
        self.udp_port = None
        self.tcp_sock = None
        self.ltcp_addr = ltcp_addr
        self.ltcp_port = ltcp_port
        self.ludp_addr = ludp_addr
        self.ludp_port = ludp_port

        self.client_signal = {
            'addr' : None,
            '_cnt' : 0,
            '_msg' : 'client'}

        self.server_signal = {
            'addr' : None,
            '_cnt' : 0,
            '_msg' : 'server'}

    def udp_client(self, rhost, rport):
        client = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        return client, rhost, rport

    def udp_server(self, host, port):
        server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return server, host, port

    def udp_proxy(self):
        try:
            udpsock = self.udp_server(self.ludp_addr, self.ludp_port)
            udp_clnt,udp_host,udp_port = udpsock
            udp_clnt.bind((udp_host,udp_port))
            logging.info("UDPServer {0}:{1} Listening Success...".format(udp_host,udp_port))

            while True:
                udp_data,udp_addr = udp_clnt.recvfrom(buffsize)

                if udp_data == self.server_signal.get('_msg'):
                    self.server_signal['addr'] = udp_addr
                    self.server_signal['_cnt'] += 1
                    # udp_clnt.sendto('server_ack_success',udp_addr)
                    logging.info('Server Initialization : {0}'.format(udp_addr))
                    continue

                if udp_data == self.client_signal.get('_msg'):
                    self.client_signal['addr'] = udp_addr
                    self.client_signal['_cnt'] += 1
                    udp_clnt.sendto('client_ack_success',udp_addr)
                    logging.info('Client Initialization : {0}'.format(udp_addr))
                    continue

                if self.server_signal['addr'] and self.client_signal['addr']:
                    if self.server_signal['addr'] == udp_addr:
                        udp_clnt.sendto(udp_data, self.client_signal['addr'])

                    if self.client_signal['addr'] == udp_addr:
                        udp_clnt.sendto(udp_data, self.server_signal['addr'])

        except socket.error as msg:
            logging.error(msg)
        except Exception, e:
            logging.error(e)
        finally:
            udp_clnt.close()

    def start_bridge_server(self):
        try:
            sleep(0.1)
            self.udp_clnt, self.udp_host, self.udp_port = self.udp_client(self.ludp_addr, self.ludp_port)
            self.udp_clnt.sendto('server',(self.udp_host, self.udp_port))   #get server udp sock

            udp_recvd_thread = threading.Thread(target=self.udp_recvd, args=())
            udp_recvd_thread.daemon = True
            udp_recvd_thread.start()

            tcp_server_thread = threading.Thread(target=self.tcp_server, args=(self.ltcp_addr,self.ltcp_port))
            tcp_server_thread.daemon = True
            tcp_server_thread.start()

            while True:
                sleep(5)
                logging.info('thread now active: '+str(threading.activeCount()))
                logging.info('len(tcplist) = %d' % len(tcplist))


        except socket.error as msg:
            logging.error(msg)
        except Exception, e:
            logging.info(e)
        finally:
            self.udp_clnt.close()
            logging.info('connection destory success...')

    def tcp_recvd(self, tcp_id):

        tcp_data = ' '
        while tcp_data:
            tcp_data = tcplist[tcp_id].recv(buffsize - 5)
            fre = struct.pack("i?",tcp_id,tcp_data)
            logging.debug( 'tcp send',tcp_id, bool(tcp_data), len(tcp_data) )
            self.udp_clnt.sendto(fre + tcp_data,(self.udp_host,self.udp_port))
            if not tcp_data:
                try:
                    tcplist[tcp_id].shutdown(socket.SHUT_RD)
                except:
                    pass
                finally:
                    logging.debug( 'tcp send over '+str(tcp_id) )
                    tcplist.pop(tcp_id)
                    pool.append(tcp_id)


    def udp_recvd(self):

        while True:
            udp_data,udp_addr = self.udp_clnt.recvfrom(buffsize)
            tcp_id, connect = struct.unpack("i?",udp_data[:5])
            udp_data = udp_data[5:]
            logging.debug( 'udp recv', tcp_id, connect, len(udp_data) )
            if connect:
                if tcp_id not in tcplist:
                    logging.error( 'tcp_id error !' )
                    continue
                tcplist[tcp_id].sendall(udp_data)
            else:
                if tcp_id in tcplist:
                    tcplist[tcp_id].shutdown(socket.SHUT_WR)


    def tcp_server(self, lhost, lport):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        #server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind((lhost,lport))
            server.listen(5)
            while True:
                tcp_clnt, tcp_addr = server.accept()
                logging.info( '[+] %s connected' % str(tcp_addr) )
                tcp_id = pool.pop()
                tcplist[tcp_id] = tcp_clnt
                tcp_recvd_thread = threading.Thread(target=self.tcp_recvd, args=(tcp_id,))
                tcp_recvd_thread.daemon = True
                tcp_recvd_thread.start()

        except socket.error as msg:
            logging.error(msg)
        except Exception, e:
            logging.error(e)
        finally:
            self.tcp_server(lhost, lport)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="tcp2udp v 1.0 ( Bridge TCP to UDP Forwarding Tools )")
    parser.add_argument("-t","--tcp",metavar="",required=True,help="tcp_server listen ipaddress : tcp_port")
    parser.add_argument("-u","--udp",metavar="",required=True,help="udp_server listen ipaddress : udp_port")
    args = parser.parse_args()

    if ":" not in args.tcp or ":" not in args.udp:
        logging.info('args is error')
        logging.info('usage: python tcp2udp -t 0.0.0.0:80 -u 0.0.0.0:53')
        sys.exit(1)

    tcp_addr,tcp_port = args.tcp.split(':')
    udp_addr,udp_port = args.udp.split(':')

    portmap = PortMap(ltcp_addr=tcp_addr,ltcp_port=int(tcp_port),ludp_addr=udp_addr,ludp_port=int(udp_port))

    try:
        # start udp_server in backgroud
        udp_proxy_thread = threading.Thread(target=portmap.udp_proxy, args=())
        udp_proxy_thread.daemon = True
        udp_proxy_thread.start()

        # bridge connection
        portmap.start_bridge_server()
    except KeyboardInterrupt:
        print "Ctrl C - Stopping Server"
        sys.exit(1)
