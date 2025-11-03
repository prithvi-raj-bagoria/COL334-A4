#!/usr/bin/env python3
"""
Simple local test for Part 2 congestion control implementation.
Tests server and client without Mininet.
"""

import subprocess
import time
import sys
import os
import hashlib

def compute_md5(file_path):
    """Compute MD5 hash of a file."""
    hasher = hashlib.md5()
    try:
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()
    except FileNotFoundError:
        return None

def test_basic_transfer():
    """Test basic file transfer with congestion control."""
    print("="*60)
    print("TEST: Basic File Transfer with Congestion Control")
    print("="*60)
    
    SERVER_IP = "127.0.0.1"
    SERVER_PORT = 9999
    PREFIX = "test_"
    
    # Start server
    print(f"\n[1] Starting server on {SERVER_IP}:{SERVER_PORT}...")
    server_proc = subprocess.Popen(
        ["python3", "p2_server.py", SERVER_IP, str(SERVER_PORT)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    time.sleep(1)  # Give server time to start
    
    # Start client
    print(f"[2] Starting client with prefix '{PREFIX}'...")
    client_proc = subprocess.Popen(
        ["python3", "p2_client.py", SERVER_IP, str(SERVER_PORT), PREFIX],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Wait for client to finish (with timeout)
    try:
        client_stdout, client_stderr = client_proc.communicate(timeout=60)
        print("\n[3] Client finished!")
        print("Client output:")
        print(client_stdout)
        if client_stderr:
            print("Client errors:")
            print(client_stderr)
    except subprocess.TimeoutExpired:
        print("\n[ERROR] Client timed out after 60 seconds!")
        client_proc.kill()
        server_proc.kill()
        return False
    
    # Kill server
    server_proc.kill()
    server_stdout, server_stderr = server_proc.communicate()
    print("\nServer output:")
    print(server_stdout)
    
    # Verify file
    print("\n[4] Verifying transferred file...")
    expected_file = "data.txt"
    received_file = f"{PREFIX}received_data.txt"
    
    if not os.path.exists(received_file):
        print(f"[ERROR] Received file '{received_file}' not found!")
        return False
    
    expected_md5 = compute_md5(expected_file)
    received_md5 = compute_md5(received_file)
    
    print(f"Expected MD5: {expected_md5}")
    print(f"Received MD5: {received_md5}")
    
    if expected_md5 == received_md5:
        print("\n✓ SUCCESS! File transferred correctly with congestion control!")
        
        # Check file size
        expected_size = os.path.getsize(expected_file)
        received_size = os.path.getsize(received_file)
        print(f"File size: {received_size} bytes (expected: {expected_size} bytes)")
        return True
    else:
        print("\n✗ FAILED! MD5 mismatch!")
        return False

def main():
    # Change to part2 directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    if not os.path.exists("data.txt"):
        print("ERROR: data.txt not found in current directory!")
        sys.exit(1)
    
    success = test_basic_transfer()
    
    if success:
        print("\n" + "="*60)
        print("ALL TESTS PASSED!")
        print("="*60)
        sys.exit(0)
    else:
        print("\n" + "="*60)
        print("TESTS FAILED!")
        print("="*60)
        sys.exit(1)

if __name__ == "__main__":
    main()
