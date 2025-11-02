#!/usr/bin/env python3
"""
Part 1 Server: Reliable UDP File Transfer with Sliding Window Protocol
Implements: Sequence numbers, ACKs, Timeouts, Fast Retransmit
"""

import socket
import sys
import time
import struct
import select

# Constants
PACKET_SIZE = 1200
HEADER_SIZE = 20
DATA_SIZE = PACKET_SIZE - HEADER_SIZE  # 1180 bytes
TIMEOUT = 0.5  # Initial RTO in seconds
ALPHA = 0.125  # For RTT estimation
BETA = 0.25    # For RTT deviation
EOF_MARKER = b"EOF"

class ReliableUDPServer:
    def __init__(self, host, port, sws):
        self.host = host
        self.port = port
        self.sws = sws  # Sender window size in bytes
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((host, port))
        
        # RTT estimation
        self.estimated_rtt = TIMEOUT
        self.dev_rtt = 0
        self.timeout = TIMEOUT
        
        # Window management
        self.base = 0  # First unacknowledged byte
        self.next_seq = 0  # Next sequence number to send
        self.packets = {}  # seq_num -> (data, send_time)
        self.dup_ack_count = {}  # Track duplicate ACKs
        
        print(f"[SERVER] Started on {host}:{port} with SWS={sws} bytes")
    
    def create_packet(self, seq_num, data):
        """Create a packet with sequence number and data"""
        # First 4 bytes: sequence number
        # Next 16 bytes: reserved (zeros)
        # Remaining: data
        header = struct.pack('!I', seq_num) + b'\x00' * 16
        return header + data
    
    def parse_ack(self, packet):
        """Parse ACK packet to get the acknowledged sequence number"""
        if len(packet) >= 4:
            ack_num = struct.unpack('!I', packet[:4])[0]
            return ack_num
        return None
    
    def update_rtt(self, sample_rtt):
        """Update RTT estimates using TCP-like algorithm"""
        if self.estimated_rtt == TIMEOUT:  # First measurement
            self.estimated_rtt = sample_rtt
            self.dev_rtt = sample_rtt / 2
        else:
            self.dev_rtt = (1 - BETA) * self.dev_rtt + BETA * abs(sample_rtt - self.estimated_rtt)
            self.estimated_rtt = (1 - ALPHA) * self.estimated_rtt + ALPHA * sample_rtt
        
        self.timeout = max(self.estimated_rtt + 4 * self.dev_rtt, 0.1)
    
    def send_file(self, client_addr, filename):
        """Send file to client using reliable UDP with sliding window"""
        try:
            with open(filename, 'rb') as f:
                file_data = f.read()
        except FileNotFoundError:
            print(f"[SERVER] Error: {filename} not found")
            return
        
        print(f"[SERVER] Sending file {filename} ({len(file_data)} bytes) to {client_addr}")
        
        # Split file into chunks
        chunks = []
        for i in range(0, len(file_data), DATA_SIZE):
            chunks.append(file_data[i:i+DATA_SIZE])
        
        total_packets = len(chunks)
        self.base = 0
        self.next_seq = 0
        self.packets = {}
        self.dup_ack_count = {}
        last_ack = -1
        
        start_time = time.time()
        
        while self.base < len(file_data):
            # Send packets within window
            while self.next_seq < len(file_data) and (self.next_seq - self.base) < self.sws:
                chunk_idx = self.next_seq // DATA_SIZE
                if chunk_idx < len(chunks):
                    packet = self.create_packet(self.next_seq, chunks[chunk_idx])
                    self.socket.sendto(packet, client_addr)
                    self.packets[self.next_seq] = (packet, time.time())
                    self.next_seq += len(chunks[chunk_idx])
            
            # Wait for ACKs with timeout
            ready = select.select([self.socket], [], [], self.timeout)
            
            if ready[0]:
                # Receive ACK
                try:
                    ack_packet, _ = self.socket.recvfrom(PACKET_SIZE)
                    ack_num = self.parse_ack(ack_packet)
                    
                    if ack_num is not None:
                        # Calculate RTT for packets being acknowledged
                        if ack_num > self.base and self.base in self.packets:
                            _, send_time = self.packets[self.base]
                            sample_rtt = time.time() - send_time
                            self.update_rtt(sample_rtt)
                        
                        if ack_num > self.base:
                            # New ACK - slide window
                            self.base = ack_num
                            last_ack = ack_num
                            self.dup_ack_count = {}  # Reset duplicate ACK counter
                            
                            # Remove acknowledged packets
                            to_remove = [seq for seq in self.packets if seq < self.base]
                            for seq in to_remove:
                                del self.packets[seq]
                        
                        elif ack_num == last_ack and ack_num == self.base:
                            # Duplicate ACK
                            self.dup_ack_count[ack_num] = self.dup_ack_count.get(ack_num, 0) + 1
                            
                            # Fast retransmit after 3 duplicate ACKs
                            if self.dup_ack_count[ack_num] == 3:
                                print(f"[SERVER] Fast retransmit at seq {self.base}")
                                if self.base in self.packets:
                                    packet, _ = self.packets[self.base]
                                    self.socket.sendto(packet, client_addr)
                                    self.packets[self.base] = (packet, time.time())
                
                except Exception as e:
                    print(f"[SERVER] Error receiving ACK: {e}")
            
            else:
                # Timeout - retransmit base packet
                if self.base in self.packets:
                    print(f"[SERVER] Timeout, retransmitting seq {self.base}")
                    packet, _ = self.packets[self.base]
                    self.socket.sendto(packet, client_addr)
                    self.packets[self.base] = (packet, time.time())
                    self.timeout = min(self.timeout * 2, 2.0)  # Exponential backoff
        
        # Send EOF marker
        eof_packet = self.create_packet(self.next_seq, EOF_MARKER)
        for _ in range(5):  # Send EOF multiple times for reliability
            self.socket.sendto(eof_packet, client_addr)
            time.sleep(0.05)
        
        elapsed = time.time() - start_time
        print(f"[SERVER] File transfer complete in {elapsed:.2f}s")
    
    def run(self):
        """Main server loop"""
        print("[SERVER] Waiting for client request...")
        
        # Wait for initial client request (with retry support)
        while True:
            try:
                data, client_addr = self.socket.recvfrom(PACKET_SIZE)
                if data:  # Any data means file request
                    print(f"[SERVER] Received request from {client_addr}")
                    self.send_file(client_addr, "data.txt")
                    break
            except Exception as e:
                print(f"[SERVER] Error: {e}")
        
        self.socket.close()
        print("[SERVER] Server terminated")

def main():
    if len(sys.argv) != 4:
        print("Usage: python3 p1_server.py <SERVER_IP> <SERVER_PORT> <SWS>")
        sys.exit(1)
    
    host = sys.argv[1]
    port = int(sys.argv[2])
    sws = int(sys.argv[3])
    
    server = ReliableUDPServer(host, port, sws)
    server.run()

if __name__ == "__main__":
    main()