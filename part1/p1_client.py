#!/usr/bin/env python3

"""
Part 1 Client: Reliable UDP File Transfer Client
Implements: ACK sending, in-order delivery, packet reassembly
Protocol: Selective Repeat (SR)
"""

import socket
import sys
import struct
import time

# Constants
PACKET_SIZE = 1200
HEADER_SIZE = 20
DATA_SIZE = PACKET_SIZE - HEADER_SIZE

REQUEST_TIMEOUT = 2.0
MAX_RETRIES = 5
EOF_MARKER = b"EOF"

class ReliableUDPClient:
    def __init__(self, server_host, server_port):
        self.server_host = server_host
        self.server_port = int(server_port)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.settimeout(5.0)

        self.recv_base = 0
        self.received_packets = {}
        self.acked_packets = set()
        self.output_file = "received_data.txt"

        #print(f"[CLIENT] Connecting to server {server_host}:{server_port}")

    def parse_packet(self, packet):
        """Parse received packet to extract sequence number and data"""
        if len(packet) < HEADER_SIZE:
            return None, None

        seq_num = struct.unpack('!I', packet[:4])[0]
        data = packet[HEADER_SIZE:]

        return seq_num, data

    def create_sr_ack(self, packet_seq_num):
        """Create SR ACK for THIS specific packet"""
        return struct.pack('!I', packet_seq_num) + b'\x00' * 16

    def send_request(self):
        """Send file request to server with retries"""
        request = b'\x01'

        for attempt in range(MAX_RETRIES):
            try:
                #print(f"[CLIENT] Sending request (attempt {attempt + 1}/{MAX_RETRIES})")
                self.socket.sendto(request, (self.server_host, self.server_port))

                self.socket.settimeout(REQUEST_TIMEOUT)
                data, _ = self.socket.recvfrom(PACKET_SIZE)

                if data:
                    #print("[CLIENT] Request successful, got first packet!")
                    return data

            except socket.timeout:
                pass
                #print(f"[CLIENT] Request timeout on attempt {attempt + 1}")
                continue

        #print("[CLIENT] Failed to connect to server")
        return None

    def receive_file(self):
        """Receive file from server using Selective Repeat protocol"""
        
        # Send request and get first packet
        first_packet = self.send_request()
        if not first_packet:
            return False

        # Process first packet
        seq_num, data = self.parse_packet(first_packet)
        if seq_num is not None:
            #print(f"[CLIENT] Processing first packet: seq={seq_num}, data_len={len(data)}")
            self.received_packets[seq_num] = data
            self.acked_packets.add(seq_num)

            ack = self.create_sr_ack(seq_num)
            self.socket.sendto(ack, (self.server_host, self.server_port))
            #print(f"[CLIENT] Sent ACK for seq={seq_num}")

        # Receive remaining packets
        consecutive_timeouts = 0
        max_consecutive_timeouts = 10  # Increased from 5
        eof_received = False  # FIXED: Track EOF properly
        last_packet_time = time.time()

        #print("[CLIENT] Entering receive loop...")

        while not eof_received:  # FIXED: Changed from while True to while not eof_received
            try:
                self.socket.settimeout(5.0)
                packet, _ = self.socket.recvfrom(PACKET_SIZE)

                consecutive_timeouts = 0  # Reset on successful receive
                last_packet_time = time.time()

                seq_num, data = self.parse_packet(packet)
                if seq_num is None:
                    #print("[CLIENT] Got malformed packet, skipping...")
                    continue

                # Check for EOF marker
                if data == EOF_MARKER:
                    #print(f"[CLIENT] ✓ Received EOF marker!")
                    ack = self.create_sr_ack(seq_num)
                    for _ in range(3):
                        self.socket.sendto(ack, (self.server_host, self.server_port))
                    eof_received = True  # FIXED: Set this to True to exit loop
                    break  # FIXED: Explicitly break to exit

                # SR Duplicate check
                if seq_num in self.acked_packets:
                    ack = self.create_sr_ack(seq_num)
                    self.socket.sendto(ack, (self.server_host, self.server_port))
                    #print(f"[CLIENT] Duplicate packet seq={seq_num}, resent ACK")
                    continue

                # SR Store this specific packet
                #print(f"[CLIENT] ✓ Received packet: seq={seq_num}, data_len={len(data)}")
                self.received_packets[seq_num] = data
                self.acked_packets.add(seq_num)

                # SR Send INDIVIDUAL ACK
                ack = self.create_sr_ack(seq_num)
                self.socket.sendto(ack, (self.server_host, self.server_port))
                
                if len(self.received_packets) % 5 == 0:
                    pass
                    #print(f"[CLIENT] Total packets received: {len(self.received_packets)}")

            except socket.timeout:
                consecutive_timeouts += 1
                elapsed_since_packet = time.time() - last_packet_time
                
                #print(f"[CLIENT] Timeout {consecutive_timeouts}/{max_consecutive_timeouts} (elapsed: {elapsed_since_packet:.1f}s, packets: {len(self.received_packets)})")

                # Check if we should give up
                if consecutive_timeouts >= max_consecutive_timeouts:
                    #print(f"[CLIENT] Max timeouts reached. Exiting receive loop.")
                    #print(f"[CLIENT] Total packets received: {len(self.received_packets)}")
                    # FIXED: Exit gracefully even without EOF
                    break

                if elapsed_since_packet > 30:
                    #print(f"[CLIENT] No packets for {elapsed_since_packet:.1f}s. Exiting.")
                    break

            except Exception as e:
                #print(f"[CLIENT] Error: {e}")
                break

        #print(f"[CLIENT] Receive loop complete. Total packets: {len(self.received_packets)}")
        #print(f"[CLIENT] EOF received: {eof_received}")  # FIXED: Show EOF status
        return True

    def write_file(self):
        """Write received packets to file in order"""
        try:
            if not self.received_packets:
                #print("[CLIENT] ERROR: No packets received!")
                return False
                
            sorted_seqs = sorted(self.received_packets.keys())
            #print(f"[CLIENT] Writing {len(sorted_seqs)} packets to {self.output_file}...")

            total_size = 0
            with open(self.output_file, 'wb') as f:
                for seq in sorted_seqs:
                    f.write(self.received_packets[seq])
                    total_size += len(self.received_packets[seq])

            #print(f"[CLIENT] ✓ File saved! Total size: {total_size} bytes")
            return True

        except Exception as e:
            #print(f"[CLIENT] Error writing file: {e}")
            import traceback
            traceback.print_exc()
            return False

    def run(self):
        """Main client routine"""
        try:
            if self.receive_file():
                if self.write_file():
                    pass
                    #print("[CLIENT] ✓✓✓ Transfer completed successfully! ✓✓✓")
                else:
                    pass
                    #print("[CLIENT] Write failed")
            else:
                pass
                #print("[CLIENT] Receive failed")
        finally:
            self.socket.close()
            #print("[CLIENT] Socket closed")

def main():
    if len(sys.argv) != 3:
        #print("Usage: python3 p1_client.py <SERVER_IP> <SERVER_PORT>")
        sys.exit(1)

    server_host = sys.argv[1]
    server_port = sys.argv[2]

    client = ReliableUDPClient(server_host, server_port)
    client.run()

if __name__ == "__main__":
    main()
