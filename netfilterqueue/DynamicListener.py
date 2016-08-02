from netfilterqueue import *
from scapy.all import *
import subprocess

FIN = 0x01
SYN = 0x02
RST = 0x04
PSH = 0x08
ACK = 0x10
URG = 0x20
ECE = 0x40
CWR = 0x80
counter = 0

'''
setup_converter uses the Netfilter Queue in order to sniff TCP-SYN packets and responds
1. by starting an instance of the converter with the following parameters:
    listening port - a free port to listen on from 1000-2^16
    the opposite converter ip - a fixed address
    destination port - the same as listening port
2. by adding NAT rules to translate incoming packets to the listening port (rule 1)
3. by adding NAT rules to translate outgoing packets back to the original (rule 2)

rule 1:
(A:a -> B:b) --NAT--> (A:a -> C:f)
rule 2:
(C:f -> A:a) --NAT--> (A:a -> B:b)

Where
    A:a is the original source ip and source port
    B:b is the original destination ip and destination port
    C is the IP address of this server
    f is the free port of this connection. Also the ID of the connection

'''
def setup_converter(pkt):
    global counter
    converter_path = '/home/osboxes/projects/SshTelnetProxy/async/Ssh2Http.py'
    payload = pkt.get_payload()
    scapy_pkt = IP(payload)
    if scapy_pkt['TCP'].flags & SYN:
        print 'popening'
        if counter > 0:
            pkt.accept()
            return
        counter += 1
        sport = scapy_pkt.getlayer(TCP).sport
        subprocess.Popen(['python', converter_path, str(sport),
                          '192.168.198.133','5080'])
        os.system('iptables -t nat -A PREROUTING -p tcp -d 192.168.198.133 --dport 5001 '
                  '-j DNAT --to 192.168.198.133:%d' % sport)
    pkt.accept()

def get_free_port():


nfqueue = NetfilterQueue()
nfqueue.bind(1, setup_converter)
try:
    nfqueue.run()
except KeyboardInterrupt:
    print
