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


buffsize = 4096
tcplist = {}

class PortMap(object):
    """docstring for PortMap"""
    def __init__(self, tcp_addr, tcp_port):
        super(PortMap, self).__init__()
        self.tcp_addr = tcp_addr
        self.tcp_port = int(tcp_port)
        self.udp_clnt = None
        self.udp_host = None
        self.udp_port = None

    def tcp_client(self):
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        client.connect((self.tcp_addr, self.tcp_port))
        return client

    def udp_client(self, rhost, rport):
        client = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        return client, rhost, rport

    def start_tcpthread(self, tcp_id):
        logging.info( '[+] connectting %s:%s' % (self.tcp_addr, self.tcp_port) )
        tcp_recvd_thread = threading.Thread(target=self.tcp_recvd, args=(tcp_id,))
        tcp_recvd_thread.daemon = True
        tcp_recvd_thread.start()

    def udp_forward(self, udp_sock):
        bridge_signal = False
        self.udp_clnt, self.udp_host, self.udp_port = udp_sock

        try:
            self.udp_clnt.settimeout(5)
            self.udp_clnt.sendto('client',(self.udp_host, self.udp_port))
            while not bridge_signal:
                udp_data,udp_addr = self.udp_clnt.recvfrom(buffsize)
                if udp_data == 'client_ack_success':
                    bridge_signal = True
            logging.info('Client Bridge Recieved Signal...')
            self.udp_clnt.settimeout(None)

            udp_recvd_thread = threading.Thread(target=self.udp_recvd, args=())
            udp_recvd_thread.daemon = True
            udp_recvd_thread.start()

            while True:
                sleep(5)
                logging.info( 'thread now active: '+str(threading.activeCount()) )
                logging.info( 'len(tcplist) = %d' % len(tcplist) )

        except socket.timeout:
            logging.error( '[-]timeout, retry')
            return self.udp_forward(udp_sock)
        except socket.error as msg:
            logging.error(msg)
        except Exception, e:
            raise e
            logging.info(e)
        finally:
            self.udp_clnt.close()
            logging.info('connection destory success...')

    def tcp_recvd(self, tcp_id):
        logging.debug( 'start tcp_recvd thread with tcp_id %s' % tcp_id )
        while tcp_id in tcplist:
            try:
                tcp_data = tcplist[tcp_id].recv(buffsize - 5)
            except Exception,e:
                logging.error(e)
                tcplist.pop(tcp_id)
                break
            fre = struct.pack("i?",tcp_id,tcp_data)
            logging.debug( '[%s] send len(%s) in tcp_recv' % (tcp_id, len(tcp_data)) )
            self.udp_clnt.sendto(fre + tcp_data,(self.udp_host,self.udp_port))
            if not tcp_data:
                try:
                    tcplist[tcp_id].shutdown(socket.SHUT_RD)
                except:
                    pass
                finally:
                    logging.debug( '[%s] send end flag in tcp_recv' % tcp_id )
                    tcplist.pop(tcp_id)

    def udp_recvd(self):
        while True:
            udp_data,udp_addr = self.udp_clnt.recvfrom(buffsize)
            tcp_id, connect = struct.unpack("i?",udp_data[:5])
            udp_data = udp_data[5:]
            logging.debug( '[%s] recv len(%s) in udp_recv' % (tcp_id, len(udp_data)) )
            if connect:
                if tcp_id not in tcplist:
                    tcplist[tcp_id] = self.tcp_client()
                    self.start_tcpthread(tcp_id)
                tcplist[tcp_id].sendall(udp_data)
            else:
                if tcp_id in tcplist:
                    tcplist[tcp_id].shutdown(socket.SHUT_WR)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="rtcp2udp v 1.0 ( Reverse TCP Port to UDP Forwarding Tools )")
    parser.add_argument("-t","--tcp",metavar="",required=True,help="forwarding tcp ipaddress : tcp_port")
    parser.add_argument("-u","--udp",metavar="",required=True,help="connect udp server ipaddress : udp_port")
    parser.add_argument("-d","--debug",help='debug mode',action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if not args.debug else logging.DEBUG,
        format='[%(levelname)s] %(message)s',
    )

    if ":" not in args.tcp or ":" not in args.udp:
        logging.info('args is error')
        logging.info('usage: python rtcp2udp -t 172.168.1.10:80 -u 119.29.29.29:53')
        sys.exit(1)

    tcp_addr,tcp_port = args.tcp.split(':')
    udp_addr,udp_port = args.udp.split(':')

    portmap = PortMap(tcp_addr, tcp_port)
    udp_conn = portmap.udp_client(udp_addr,int(udp_port))

    try:
        portmap.udp_forward(udp_conn)
    except KeyboardInterrupt:
        print "Ctrl C - Stopping Client"
        sys.exit(1)
