# TCP CUBIC Implementation - Changes Made

## Summary
Implemented TCP CUBIC congestion control to replace TCP Reno. CUBIC is designed for high bandwidth-delay product networks and grows more aggressively than Reno.

## Key Changes

### 1. CUBIC Parameters
```python
CUBIC_C = 0.5      # Increased from standard 0.4 for faster growth
CUBIC_BETA = 0.7   # Less aggressive than Reno's 0.5
```

### 2. Initial ssthresh
```python
self.ssthresh = 500 * MSS  # 500 KB - allows aggressive slow start
```

### 3. CUBIC State Variables
- `w_max`: Window size at last congestion event
- `epoch_start`: Timestamp when current CUBIC epoch started
- `K`: Time to reach W_max from current window
- `ack_count`: Counter for ACKs (used for debug logging)

### 4. CUBIC Window Growth Formula
```
W_cubic(t) = C * (t - K)³ + W_max

Where:
- t = time since epoch start
- K = cube_root(W_max * (1 - beta) / C)
- C = 0.5 (cubic scaling)
- beta = 0.7 (window reduction factor)
```

### 5. Congestion Events

**On Timeout:**
- W_max = current cwnd
- ssthresh = cwnd * 0.7
- cwnd = 1 MSS
- Re-enter slow start

**On Fast Retransmit (3 dup ACKs):**
- W_max = current cwnd
- cwnd = cwnd * 0.7
- Stay in congestion avoidance

### 6. Window Increment (Per ACK)
```python
if target > cwnd:
    # Growing towards CUBIC target
    increment = (target - cwnd) * bytes_acked / cwnd
else:
    # TCP-friendly region (below target)
    increment = MSS² / cwnd per ACK
```

## Why Results May Still Differ from Expected

### 1. Network Conditions
- Expected values might be from different network parameters
- Buffer sizes in experiments affect results
- Even "0% loss" can have some packet loss in practice

### 2. Implementation Details
- RTO calculation (bounds: 0.2s to 3.0s)
- Small sleep (1ms) in transfer loop
- SACK implementation differences

### 3. Possible Tuning Needed
If results are still low:
- **Increase ssthresh further**: Try 1000 MSS or 2000 MSS
- **Increase CUBIC_C**: Try 0.6 or 0.7
- **Decrease CUBIC_BETA**: Try 0.8 (less aggressive reduction)
- **Remove/reduce sleep**: Change `time.sleep(0.001)` to `time.sleep(0.0001)`

## Testing

Run the experiment:
```bash
sudo python3 p2_exp.py fixed_bandwidth
```

Expected behavior:
- Slow start should reach 500 MSS quickly
- First congestion event sets W_max
- CUBIC should then grow cubically towards and beyond W_max
- Fair bandwidth sharing (JFI ~0.99) ✓ Already achieved
- Higher link utilization than current results

## Debug Output
Look for these messages:
```
[CUBIC] Exiting Slow Start. cwnd=X MSS
[CUBIC] TIMEOUT! cwnd=X MSS → W_max=X MSS
[CUBIC] t=X.XXs, cwnd=X MSS, target=X MSS, W_max=X MSS, K=X.XXs
```

This shows CUBIC behavior over time.
