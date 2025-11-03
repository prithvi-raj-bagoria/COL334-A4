#!/usr/bin/env python3
"""
Reliable-UDP file receiver (State-Driven Design) with prefix support.

This version supports a prefix filename parameter for Part 2.

Usage: python3 p2_client.py <SERVER_IP> <SERVER_PORT> <PREF_FILENAME>
"""
import socket
import struct
import sys
import time

# Protocol constants
UDP_MAX = 1200
HEADER_LEN = 20

class Receiver:
    def __init__(self, srv_ip, srv_port, prefix=""):
        self.srv_ip = srv_ip
        self.srv_port = srv_port
        self.srv_addr = (srv_ip, srv_port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.prefix = prefix
        self.output_file = f"{prefix}received_data.txt"
        
        # State variables
        self.buffered = {}  # seq -> bytes (out-of-order buffer)
        self.next_expected = 0
        self.saw_eof = False
        self.eof_seq = None
        self.consecutive_timeouts = 0

    # ---------------- Packet Helper Methods (Unchanged) ----------------
    @staticmethod
    def _compose_ack(next_expected, sack_blocks=None):
        """Create an ACK packet with optional SACK blocks."""
        if sack_blocks is None:
            sack_blocks = []
        buf = struct.pack('!I', next_expected)
        opt = b''
        for start, end in sack_blocks[:2]:
            opt += struct.pack('!I', start) + struct.pack('!I', end)
        opt = opt.ljust(16, b'\x00')
        return buf + opt

    @staticmethod
    def _parse_packet(pkt):
        """Parse an incoming data packet."""
        if len(pkt) < HEADER_LEN:
            return None, None, False
        seq = struct.unpack('!I', pkt[:4])[0]
        payload = pkt[HEADER_LEN:]
        if payload == b'EOF':
            return seq, b'', True
        return seq, payload, False

    # ---------------- Core Logic Methods (Unchanged) ----------------
    def _drain_inorder_buffer(self, file_obj):
        """Write any buffered contiguous segments starting at next_expected."""
        while self.next_expected in self.buffered:
            piece = self.buffered.pop(self.next_expected)
            file_obj.write(piece)
            self.next_expected += len(piece)

    def _get_sack_blocks(self):
        """Create up to two SACK blocks from buffered segments."""
        if not self.buffered:
            return []
        seqs = sorted(self.buffered.keys())
        blocks = []
        cur_s, cur_e = None, None
        for s in seqs:
            seg_end = s + len(self.buffered[s])
            if cur_s is None:
                cur_s, cur_e = s, seg_end
            elif s <= cur_e:
                cur_e = max(cur_e, seg_end)
            else:
                blocks.append((cur_s, cur_e))
                cur_s, cur_e = s, seg_end
            if len(blocks) >= 2:
                break
        if cur_s is not None and len(blocks) < 2:
            blocks.append((cur_s, cur_e))
        return blocks[:2]

    # ---------------- Refactored Control Flow ----------------
    def _run_handshake(self):
        """
        Handles the initial connection request state.
        Tries 5 times, 2-sec timeout.
        """
        self.sock.settimeout(2.0)
        for attempt in range(5):
            try:
                print(f"Request attempt {attempt+1}/5")
                self.sock.sendto(b'D', self.srv_addr)
                
                pkt, addr = self.sock.recvfrom(UDP_MAX)
                if addr == self.srv_addr:
                    print("Server contacted. Beginning download...")
                    # Process this first packet
                    self._process_data_packet(pkt)
                    return True # Handshake successful
            except socket.timeout:
                if attempt < 4:
                    print("No response, retrying...")
                continue
            except Exception as e:
                print(f"Handshake error: {e}")
                return False
                
        print("Failed to contact server after 5 attempts.")
        return False # Handshake failed

    def _run_download(self):
        """
        Handles the main data transfer state.
        Assumes handshake was successful.
        """
        try:
            with open(self.output_file, 'wb') as fout:
                # Set a shorter timeout for the transfer loop
                self.sock.settimeout(1.0)
                
                # Drain the first packet(s) received during handshake
                self._drain_inorder_buffer(fout)
                
                while not self._is_complete():
                    try:
                        # Wait for a packet
                        pkt, addr = self.sock.recvfrom(UDP_MAX)
                        if addr == self.srv_addr:
                            self._handle_packet_recv(pkt, fout)
                            
                    except socket.timeout:
                        self._handle_timeout()
                        
                        if self.consecutive_timeouts > 10:
                            print("Too many consecutive timeouts, aborting.")
                            return False
                            
                # Loop finished normally
                print(f"Total bytes written: {self.next_expected}")
                return True

        except Exception as e:
            print(f"Download loop error: {e}")
            return False

    def _handle_packet_recv(self, pkt, file_obj):
        """Logic for processing a newly received packet."""
        self.consecutive_timeouts = 0
        seq, data, eof_flag = self._parse_packet(pkt)
        if seq is None:
            return # Ignore malformed packet

        # Process the packet data
        if eof_flag:
            self.saw_eof = True
            self.eof_seq = seq
        elif data:
            if seq == self.next_expected:
                file_obj.write(data)
                self.next_expected += len(data)
                self._drain_inorder_buffer(file_obj) # Drain buffer
            elif seq > self.next_expected:
                self.buffered.setdefault(seq, data) # Buffer out-of-order
        
        # Always send an ACK in response
        self._send_ack()

    def _process_data_packet(self, pkt):
        """
        Simplified version of _handle_packet_recv used *only* during handshake,
        where we can't write to a file yet. We just buffer.
        """
        seq, data, eof_flag = self._parse_packet(pkt)
        if seq is None:
            return

        if eof_flag:
            self.saw_eof = True
            self.eof_seq = seq
        elif data:
            # We can't write to file yet, so just buffer everything
            self.buffered.setdefault(seq, data)
        
        # Send an ACK for this first packet
        self._send_ack()

    def _handle_timeout(self):
        """Logic for handling a socket timeout."""
        self.consecutive_timeouts += 1
        # Proactively re-send our last ACK to trigger retransmit
        self._send_ack()

    def _send_ack(self):
        """Consolidated ACK sender."""
        sacks = self._get_sack_blocks()
        ack_pkt = self._compose_ack(self.next_expected, sack_blocks=sacks)
        self.sock.sendto(ack_pkt, self.srv_addr)

    def _is_complete(self):
        """Checks if the file transfer is finished."""
        return self.saw_eof and (self.eof_seq == self.next_expected)

    def start(self):
        """
        Public entry point. Runs the client's state machine.
        """
        try:
            if not self._run_handshake():
                return False # Handshake failed
            
            # Handshake OK, proceed to download
            return self._run_download()
            
        finally:
            self.sock.close()
            print("Socket closed.")

# ---------------- Main ----------------
def main():
    if len(sys.argv) != 4:
        print("Usage: python3 p2_client.py <SERVER_IP> <SERVER_PORT> <PREF_FILENAME>")
        sys.exit(1)
    ip = sys.argv[1]
    port = int(sys.argv[2])
    prefix = sys.argv[3]
    
    r = Receiver(ip, port, prefix)
    ok = r.start()
    
    if ok:
        print(f"Download successful. File saved to '{r.output_file}'")
        sys.exit(0)
    else:
        print("Download failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()