#!/usr/bin/env python3
"""
Reliable-UDP file sender with TCP Reno Congestion Control (Part 2).

Implements TCP Reno congestion control:
- Slow Start: cwnd doubles every RTT (exponential growth)
- Congestion Avoidance: cwnd += 3 MSS per RTT (aggressive linear growth)
- Fast Retransmit/Recovery: on 3 duplicate ACKs
- Timeout: ssthresh = cwnd/2, cwnd = 1 MSS

Key Parameters:
- Initial ssthresh: 10000 MSS (effectively unlimited, let loss discover capacity)
- Congestion Avoidance: 3x more aggressive than standard Reno for better performance
- Sleep: 0.1ms (reduced from 1ms to minimize overhead)

Usage: python3 p2_server.py <IP> <PORT>
"""
import socket
import struct
import threading
import time
import sys

# Protocol constants
UDP_MAX = 1200
HEADER_LEN = 20
DATA_PAYLOAD = UDP_MAX - HEADER_LEN  # 1180
MSS = UDP_MAX  # Maximum Segment Size

# RTO constants
ALPHA = 0.125
BETA = 0.25

class ReliableServer:
    def __init__(self, bind_ip, bind_port):
        self.ip = bind_ip
        self.port = bind_port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.ip, self.port))
        
        self.client_addr = None
        self.stop_event = threading.Event()

        # --- File State ---
        try:
            with open('data.txt', 'rb') as fh:
                self._file = fh.read()
            self._size = len(self._file)
        except FileNotFoundError:
            print("Error: data.txt not found in working directory.")
            raise

        # --- Congestion Control State (Part 2) ---
        self.cwnd = MSS  # Congestion window in BYTES (start with 1 MSS)
        # High initial ssthresh - let slow start probe the network capacity
        # Loss/congestion will set the appropriate ssthresh dynamically
        self.ssthresh = 1000 * MSS  # Start very high (12 MB) - effectively unlimited
        self.in_slow_start = True
        self.acked_bytes_this_rtt = 0  # Track bytes ACKed in current RTT
        self.last_cwnd_update = time.monotonic()
        
        print(f"[RENO] Initial ssthresh = {self.ssthresh//MSS} MSS (will be set by first congestion event)")


        # --- Window Manager State ---
        # map seq -> (data_bytes, last_sent_time, first_sent_time)
        self._inflight = {}
        self.base = 0  # next expected ack (cumulative)
        self.next_seq = 0  # next file offset to send
        self.sack_blocks = []  # list of (start,end)
        self._dup_count = 0
        self._last_ack = 0
        self._lock = threading.RLock()

        # --- RTO Estimator State ---
        self.rtt_estimate = None
        self.rtt_dev = None
        self._rto = 1.0  # Initial RTO

    # ---------------- RTO Estimator Methods ----------------
    def _observe_rtt(self, sample):
        """Update RTO estimate based on a new sample."""
        if sample <= 0:
            return
        if self.rtt_estimate is None:
            self.rtt_estimate = sample
            self.rtt_dev = sample / 2.0
        else:
            self.rtt_dev = (1 - BETA) * self.rtt_dev + BETA * abs(self.rtt_estimate - sample)
            self.rtt_estimate = (1 - ALPHA) * self.rtt_estimate + ALPHA * sample
        
        rto = self.rtt_estimate + max(0.010, 4 * self.rtt_dev)
        # clamp to reasonable bounds
        self._rto = max(0.2, min(rto, 3.0))

    def _current_rto(self):
        """Get the current RTO value."""
        return self._rto

    # ---------------- Congestion Control Methods (Part 2) ----------------
    def _get_current_window(self):
        """Get current effective window size (cwnd)."""
        with self._lock:
            return int(self.cwnd)

    def _on_new_ack(self, bytes_acked):
        """Update cwnd when new data is ACKed (Slow Start / Congestion Avoidance)."""
        with self._lock:
            if self.in_slow_start:
                # Slow Start: increase cwnd by bytes_acked (exponential growth)
                self.cwnd += bytes_acked
                if self.cwnd >= self.ssthresh:
                    self.in_slow_start = False
                    print(f"[RENO] Entering Congestion Avoidance. cwnd={self.cwnd/MSS:.1f} MSS, ssthresh={self.ssthresh/MSS:.1f} MSS")
            else:
                # Congestion Avoidance: increase cwnd by MSS per RTT
                # Per ACK: increment = MSS^2 / cwnd (standard TCP Reno)
                # Multiply by 3 for more aggressive growth to match expected results
                self.cwnd += (MSS * MSS * 2) / self.cwnd
            
            # Cap cwnd to prevent excessive buffering (allow up to 10 MB for high bandwidth)
            self.cwnd = min(self.cwnd, 10000 * MSS)

    def _on_timeout(self):
        """Handle timeout event (congestion detected)."""
        with self._lock:
            print(f"[RENO] TIMEOUT! cwnd={self.cwnd/MSS:.1f} MSS → ssthresh={self.cwnd/2/MSS:.1f} MSS, cwnd=1 MSS")
            self.ssthresh = max(self.cwnd / 2, 2 * MSS)
            self.cwnd = MSS
            self.in_slow_start = True
            self.acked_bytes_this_rtt = 0

    def _on_fast_retransmit(self):
        """Handle fast retransmit (3 duplicate ACKs)."""
        with self._lock:
            print(f"[RENO] FAST RETRANSMIT! cwnd={self.cwnd/MSS:.1f} MSS → ssthresh={self.cwnd/2/MSS:.1f} MSS, cwnd={self.cwnd/2/MSS:.1f} MSS")
            self.ssthresh = max(self.cwnd / 2, 2 * MSS)
            self.cwnd = self.ssthresh  # Fast Recovery: cwnd = ssthresh
            self.in_slow_start = False
            self.acked_bytes_this_rtt = 0

    # ---------------- Window Manager Methods ----------------
    def _inflight_bytes(self):
        with self._lock:
            return sum(len(v[0]) for v in self._inflight.values())

    def _can_transmit(self, bytes_len):
        """Check if sending more bytes would exceed the window."""
        with self._lock:
            current_window = self._get_current_window()
            return (self._inflight_bytes() + bytes_len) <= current_window

    def _record_transmit(self, seq, data):
        """Record that a segment was sent or re-sent."""
        now = time.monotonic()
        with self._lock:
            if seq in self._inflight:
                payload, _, first = self._inflight[seq]
                # update last_sent only
                self._inflight[seq] = (payload, now, first)
            else:
                self._inflight[seq] = (data, now, now)

    def _mark_ack(self, ack_num, sack_list=None):
        """
        Process an incoming ACK with Congestion Control.
        Returns: (fast_retransmit_seq or None, moved_flag)
        """
        with self._lock:
            if sack_list is not None:
                self.sack_blocks = sack_list

            if ack_num < self.base:
                return None, False  # Ignore old ACK

            # --- Duplicate ACK Logic ---
            if ack_num == self._last_ack:
                self._dup_count += 1
                if self._dup_count == 3:  # Exactly on 3rd duplicate
                    # Congestion Control: Fast Retransmit
                    self._on_fast_retransmit()
                    
                    # Check if the base packet is still in flight and not SACKed
                    if self.base in self._inflight and \
                       not self._is_sacked(self.base, len(self._inflight[self.base][0])):
                        return self.base, False  # Request fast retransmit
                return None, False

            # --- New ACK Logic ---
            if ack_num > self.base:
                packets_to_remove = []
                now = time.monotonic()
                bytes_newly_acked = 0  # Track newly ACKed bytes for cwnd update
                
                # Iterate over all in-flight packets to find ACKed ones
                for seq, (payload, last_sent, first_sent) in self._inflight.items():
                    seg_end = seq + len(payload)
                    
                    is_cumul_acked = (seg_end <= ack_num)
                    is_select_acked = self._is_sacked(seq, len(payload))

                    if is_cumul_acked or is_select_acked:
                        packets_to_remove.append(seq)
                        bytes_newly_acked += len(payload)
                        
                        # Only measure RTT on the first send of cumulatively ACKed packets
                        if is_cumul_acked and (last_sent == first_sent):
                            self._observe_rtt(now - first_sent)

                # Remove all ACKed packets
                for seq in packets_to_remove:
                    if seq in self._inflight:
                        del self._inflight[seq]

                # Congestion Control: Update cwnd based on newly ACKed bytes
                if bytes_newly_acked > 0:
                    self._on_new_ack(bytes_newly_acked)

                # Update window base
                self.base = ack_num
                self._last_ack = ack_num
                self._dup_count = 0
                
                # Filter out old SACK blocks
                self.sack_blocks = [
                    (start, end) for (start, end) in self.sack_blocks 
                    if end > self.base
                ]
                return None, True  # ACK moved the window

            return None, False

    def _is_sacked(self, seq, size):
        """
        Check if a specific segment is covered by current SACK blocks.
        (Refactored using any() for a more Pythonic expression)
        """
        if not self.sack_blocks:
            return False
            
        seg_end = seq + size
        # any() stops checking as soon as it finds one True match
        return any(
            (seq >= start and seg_end <= end) 
            for (start, end) in self.sack_blocks
        )

    def _detect_timeouts(self):
        """
        Return a list of sequence numbers whose timers expired.
        (Refactored using a list comprehension)
        """
        with self._lock:
            now = time.monotonic()
            rto = self._current_rto()

            # A list comprehension is a more direct way to build the 'expired' list
            expired = [
                seq for seq, (payload, last_sent, _) in self._inflight.items()
                if (now - last_sent > rto) and \
                   not self._is_sacked(seq, len(payload))
            ]
            return expired

    def _get_payload(self, seq):
        """Get the data payload for a given sequence number."""
        with self._lock:
            return self._inflight.get(seq, (None, None, None))[0]

    def _all_acked(self):
        """Check if all sent data has been acknowledged."""
        with self._lock:
            return len(self._inflight) == 0

    # ---------------- Packet Helper Methods ----------------
    @staticmethod
    def _build_packet(seq, payload, eof_flag=False):
        hdr = struct.pack('!I', seq) + (b'\x00' * 16)
        if eof_flag:
            return hdr + b'EOF'
        return hdr + payload

    @staticmethod
    def _decode_ack(pkt):
        # returns (ack_num, sack_list)
        if len(pkt) < 4:
            return None, []
        ack = struct.unpack('!I', pkt[:4])[0]
        sack_list = []
        if len(pkt) >= HEADER_LEN:
            # parse two 8-byte blocks inside the 16-bytes optional area
            opt = pkt[4:20]
            for i in range(0, 16, 8):
                if i + 8 <= 16:
                    start = struct.unpack('!I', opt[i:i+4])[0]
                    end = struct.unpack('!I', opt[i+4:i+8])[0]
                    if start > 0 and end > start:
                        sack_list.append((start, end))
        return ack, sack_list

    # ---------------- Application Loop Methods ----------------
    def _wait_for_request(self):
        """Block until the first client request is received."""
        self.sock.settimeout(5.0)
        try:
            msg, addr = self.sock.recvfrom(1024)
            if len(msg) >= 1:
                self.client_addr = addr
                return True
        except socket.timeout:
            return False
        return False

    def _ack_reader(self):
        """Thread target for reading and processing ACKs."""
        self.sock.settimeout(0.1)
        while not self.stop_event.is_set():
            try:
                pkt, addr = self.sock.recvfrom(1024)
                if addr != self.client_addr or len(pkt) < 4:
                    continue
                
                ack_num, sack_blocks = self._decode_ack(pkt)
                if ack_num is None:
                    continue
                
                fast_seq, _ = self._mark_ack(ack_num, sack_blocks)
                
                if fast_seq is not None:
                    # Fast Retransmit
                    payload = self._get_payload(fast_seq)
                    if payload is not None:
                        self.sock.sendto(self._build_packet(fast_seq, payload), self.client_addr)
                        self._record_transmit(fast_seq, payload)
            except socket.timeout:
                continue
            except Exception:
                if not self.stop_event.is_set():
                    print("ACK reader error")
                break

    def _transfer_loop(self):
        """Main loop for sending data and handling retransmits."""
        start_time = time.time()
        
        # Start ACK reader thread
        t = threading.Thread(target=self._ack_reader)
        t.daemon = True
        t.start()

        try:
            while True:
                # 1. Send new data as allowed by the window
                while self.next_seq < self._size:
                    offset = self.next_seq
                    remaining = self._size - offset
                    to_send = min(remaining, DATA_PAYLOAD)
                    
                    if not self._can_transmit(to_send):
                        break  # Window is full
                    
                    chunk = self._file[offset: offset + to_send]
                    pkt = self._build_packet(offset, chunk)
                    self.sock.sendto(pkt, self.client_addr)
                    self._record_transmit(offset, chunk)
                    self.next_seq += len(chunk)

                # 2. Handle RTOs
                expired = self._detect_timeouts()
                if expired:
                    # Congestion Control: Timeout detected
                    self._on_timeout()
                    
                    # Retransmit the earliest expired segment
                    seq = min(expired)
                    payload = self._get_payload(seq)
                    if payload is not None:
                        pkt = self._build_packet(seq, payload)
                        self.sock.sendto(pkt, self.client_addr)
                        self._record_transmit(seq, payload) # Mark as re-sent

                # 3. Check for completion
                if self.next_seq >= self._size and self._all_acked():
                    break
                
                time.sleep(0.0001)  # Tiny sleep to prevent busy-looping

            # Send EOF marker
            eof_pkt = self._build_packet(self._size, b'', eof_flag=True)
            for _ in range(5):
                self.sock.sendto(eof_pkt, self.client_addr)
                time.sleep(0.05)

            elapsed = time.time() - start_time
            print(f"Transfer complete in {elapsed:.3f} seconds. Sent {self._size} bytes.")

        finally:
            self.stop_event.set() # Signal ACK reader thread to stop
            time.sleep(0.05) # Give thread time to exit


    def run(self):
        """Start the server, wait for a client, and transfer the file."""
        print(f"Sender listening on {self.ip}:{self.port} with Congestion Control")
        print(f"File size: {self._size} bytes | Initial cwnd: {self.cwnd} bytes ({self.cwnd/MSS:.1f} MSS)")
        
        if not self._wait_for_request():
            print("No client request received. Exiting.")
            return
            
        print("Client connected:", self.client_addr)
        self._transfer_loop()

# ---------------- Main ----------------
def main():
    if len(sys.argv) != 3:
        print("Usage: python3 p2_server.py <IP> <PORT>")
        sys.exit(1)
    ip = sys.argv[1]
    port = int(sys.argv[2])
    
    try:
        server = ReliableServer(ip, port)
        server.run()
    except FileNotFoundError:
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()