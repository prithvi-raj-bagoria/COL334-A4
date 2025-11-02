#!/usr/bin/env python3
"""
Part 1 Client: Reliable UDP File Transfer Client
Implements: ACK sending, in-order delivery, packet reassembly
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
        self.socket.settimeout(5.0)  # Socket timeout for receiving
        
        self.expected_seq = 0
        self.received_data = {}
        self.output_file = "received_data.txt"
        
        print(f"[CLIENT] Connecting to server {server_host}:{server_port}")
    
    def parse_packet(self, packet):
        """Parse received packet to extract sequence number and data"""
        if len(packet) < HEADER_SIZE:
            return None, None
        
        # Extract sequence number (first 4 bytes)
        seq_num = struct.unpack('!I', packet[:4])[0]
        # Extract data (skip 20-byte header)
        data = packet[HEADER_SIZE:]
        
        return seq_num, data
    
    def create_ack(self, ack_num):
        """Create ACK packet with acknowledgment number"""
        # ACK packet: 4 bytes for ACK number, rest zeros
        return struct.pack('!I', ack_num) + b'\x00' * 16
    
    def send_request(self):
        """Send file request to server with retries"""
        request = b'\x01'  # Single byte request
        
        for attempt in range(MAX_RETRIES):
            try:
                print(f"[CLIENT] Sending request (attempt {attempt + 1}/{MAX_RETRIES})")
                self.socket.sendto(request, (self.server_host, self.server_port))
                
                # Wait for first packet as confirmation
                self.socket.settimeout(REQUEST_TIMEOUT)
                data, _ = self.socket.recvfrom(PACKET_SIZE)
                
                if data:
                    print("[CLIENT] Request successful, receiving file...")
                    return data  # Return first packet
                
            except socket.timeout:
                print(f"[CLIENT] Request timeout on attempt {attempt + 1}")
                continue
            except Exception as e:
                print(f"[CLIENT] Error sending request: {e}")
                continue
        
        print("[CLIENT] Failed to connect to server after max retries")
        return None
    
    def receive_file(self):
        """Receive file from server using reliable UDP"""
        # Send initial request and get first packet
        first_packet = self.send_request()
        if not first_packet:
            return False
        
        # Process first packet
        seq_num, data = self.parse_packet(first_packet)
        if seq_num is not None:
            self.received_data[seq_num] = data
            if seq_num == self.expected_seq:
                self.expected_seq += len(data)
        
        # Send ACK for first packet
        ack = self.create_ack(self.expected_seq)
        self.socket.sendto(ack, (self.server_host, self.server_port))
        
        # Receive remaining packets
        consecutive_timeouts = 0
        max_consecutive_timeouts = 10
        
        while True:
            try:
                self.socket.settimeout(5.0)
                packet, _ = self.socket.recvfrom(PACKET_SIZE)
                consecutive_timeouts = 0  # Reset on successful receive
                
                seq_num, data = self.parse_packet(packet)
                
                if seq_num is None:
                    continue
                
                # Check for EOF
                if data == EOF_MARKER:
                    print("[CLIENT] Received EOF marker")
                    # Send final ACK
                    ack = self.create_ack(self.expected_seq)
                    self.socket.sendto(ack, (self.server_host, self.server_port))
                    break
                
                # Store packet if not duplicate
                if seq_num not in self.received_data:
                    self.received_data[seq_num] = data
                
                # Update expected sequence if in order
                while self.expected_seq in self.received_data:
                    self.expected_seq += len(self.received_data[self.expected_seq])
                
                # Send cumulative ACK
                ack = self.create_ack(self.expected_seq)
                self.socket.sendto(ack, (self.server_host, self.server_port))
            
            except socket.timeout:
                consecutive_timeouts += 1
                if consecutive_timeouts >= max_consecutive_timeouts:
                    print("[CLIENT] Too many consecutive timeouts, assuming transfer complete")
                    break
                print(f"[CLIENT] Timeout waiting for packet (consecutive: {consecutive_timeouts})")
                # Send ACK again in case it was lost
                ack = self.create_ack(self.expected_seq)
                self.socket.sendto(ack, (self.server_host, self.server_port))
            
            except Exception as e:
                print(f"[CLIENT] Error receiving packet: {e}")
                break
        
        return True
    
    def write_file(self):
        """Write received data to file in order"""
        try:
            with open(self.output_file, 'wb') as f:
                # Write packets in sequence order
                seq_nums = sorted(self.received_data.keys())
                for seq in seq_nums:
                    f.write(self.received_data[seq])
            
            print(f"[CLIENT] File saved to {self.output_file}")
            return True
        
        except Exception as e:
            print(f"[CLIENT] Error writing file: {e}")
            return False
    
    def run(self):
        """Main client routine"""
        try:
            if self.receive_file():
                self.write_file()
                print("[CLIENT] Transfer completed successfully")
            else:
                print("[CLIENT] Transfer failed")
        finally:
            self.socket.close()

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 p1_client.py <SERVER_IP> <SERVER_PORT>")
        sys.exit(1)
    
    server_host = sys.argv[1]
    server_port = sys.argv[2]
    
    client = ReliableUDPClient(server_host, server_port)
    client.run()

if __name__ == "__main__":
    main()