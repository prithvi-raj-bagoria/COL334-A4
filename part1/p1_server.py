#!/usr/bin/env python3

"""
Part 1 Server: Reliable UDP File Transfer with Sliding Window Protocol
Implements: Sequence numbers, ACKs, Timeouts, Selective Repeat
FIXED: Track ACKs by sequence number, NOT chunk index!
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
        
        # Window management - SR
        self.send_base = 0  # First unacknowledged byte
        self.next_seq = 0  # Next sequence number to send
        self.packets = {}  # seq_num -> (data, send_time)
        self.individually_acked = set()  # Track individually acked SEQ NUMBERS!
        
        #print(f"[SERVER] Started on {host}:{port} with SWS={sws} bytes")

    def create_packet(self, seq_num, data):
        """Create a packet with sequence number and data"""
        header = struct.pack('!I', seq_num) + b'\x00' * 16
        return header + data

    def parse_sr_ack(self, packet):
        """Parse SR ACK packet to get the INDIVIDUAL sequence number"""
        if len(packet) >= 4:
            ack_seq = struct.unpack('!I', packet[:4])[0]
            return ack_seq
        return None

    def update_rtt(self, sample_rtt):
        """Update RTT estimates using TCP-like algorithm"""
        if self.estimated_rtt == TIMEOUT:
            self.estimated_rtt = sample_rtt
            self.dev_rtt = sample_rtt / 2
        else:
            self.dev_rtt = (1 - BETA) * self.dev_rtt + BETA * abs(sample_rtt - self.estimated_rtt)
            self.estimated_rtt = (1 - ALPHA) * self.estimated_rtt + ALPHA * sample_rtt
        
        self.timeout = max(self.estimated_rtt + 4 * self.dev_rtt, 0.1)

    def send_file(self, client_addr, filename):
        """Send file to client using Selective Repeat protocol"""
        try:
            with open(filename, 'rb') as f:
                file_data = f.read()
        except FileNotFoundError:
            #print(f"[SERVER] Error: {filename} not found")
            return

        #print(f"[SERVER] Sending file {filename} ({len(file_data)} bytes) to {client_addr}")
        
        # Split file into chunks
        chunks = []
        seq_numbers = []  # Track sequence numbers for each chunk!
        
        current_seq = 0
        for i in range(0, len(file_data), DATA_SIZE):
            chunk = file_data[i:i+DATA_SIZE]
            chunks.append(chunk)
            seq_numbers.append(current_seq)
            current_seq += len(chunk)

        total_packets = len(chunks)
        #print(f"[SERVER] Total chunks: {total_packets}")
        
        self.send_base = 0
        self.next_seq = 0
        self.packets = {}
        self.individually_acked = set()
        
        start_time = time.time()

        # SR keeps sending until all packets individually acked
        while len(self.individually_acked) < total_packets:
            # Send packets within window
            while self.next_seq < len(file_data) and (self.next_seq - self.send_base) < self.sws:
                chunk_idx = self.next_seq // DATA_SIZE
                if chunk_idx < len(chunks):
                    # FIX: Check if THIS SEQUENCE NUMBER is acked, not chunk index!
                    if self.next_seq not in self.individually_acked:
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
                    ack_seq = self.parse_sr_ack(ack_packet)

                    if ack_seq is not None:
                        # FIX: Track by SEQUENCE NUMBER, not chunk index!
                        if ack_seq not in self.individually_acked:
                            # First time seeing this ACK
                            if ack_seq in self.packets:
                                _, send_time = self.packets[ack_seq]
                                sample_rtt = time.time() - send_time
                                self.update_rtt(sample_rtt)
                            
                            self.individually_acked.add(ack_seq)
                            #print(f"[SERVER] ✓ ACK seq={ack_seq} received ({len(self.individually_acked)}/{total_packets})")
                        
                        # SR slides window only when base packet is acked
                        while self.send_base in self.individually_acked:
                            chunk_idx = self.send_base // DATA_SIZE
                            if chunk_idx < len(chunks):
                                advance_by = len(chunks[chunk_idx])
                            else:
                                advance_by = DATA_SIZE
                            
                            if self.send_base in self.packets:
                                del self.packets[self.send_base]
                            
                            self.send_base += advance_by

                except Exception as e:
                    pass
                    #print(f"[SERVER] Error receiving ACK: {e}")

            else:
                # SR retransmit - send ALL unacked packets in window
                #print(f"[SERVER] Timeout! Retransmitting...")
                for seq_num in sorted(self.packets.keys()):
                    if (seq_num >= self.send_base and 
                        seq_num < self.send_base + self.sws and
                        seq_num not in self.individually_acked):
                        
                        packet, _ = self.packets[seq_num]
                        self.socket.sendto(packet, client_addr)
                        self.packets[seq_num] = (packet, time.time())
                
                # Exponential backoff
                self.timeout = min(self.timeout * 2, 2.0)

        # NOW ALL packets are acked, send EOF
        #print("[SERVER] ✓ All packets acked! Sending EOF...")
        eof_packet = self.create_packet(self.next_seq, EOF_MARKER)
        for i in range(10):
            self.socket.sendto(eof_packet, client_addr)
            time.sleep(0.05)

        elapsed = time.time() - start_time
        print(f"[SERVER] ✓✓✓ Transfer complete in {elapsed:.2f}s ✓✓✓")

    def run(self):
        """Main server loop"""
        #print("[SERVER] Waiting for client request...")
        
        while True:
            try:
                data, client_addr = self.socket.recvfrom(PACKET_SIZE)
                if data:
                    #print(f"[SERVER] Received request from {client_addr}")
                    self.send_file(client_addr, "data.txt")
                    break
            except Exception as e:
                pass
                #print(f"[SERVER] Error: {e}")

        self.socket.close()
        #print("[SERVER] Server terminated")

def main():
    if len(sys.argv) != 4:
        #print("Usage: python3 p1_server.py <SERVER_IP> <SERVER_PORT> <SWS>")
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2])
    sws = int(sys.argv[3])

    server = ReliableUDPServer(host, port, sws)
    server.run()

if __name__ == "__main__":
    main()
