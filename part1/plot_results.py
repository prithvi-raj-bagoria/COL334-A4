#!/usr/bin/env python3
"""
Plot Generator for Part 1 Reliability Experiments
Generates plots for loss vs time and jitter vs time with 90% confidence intervals
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats
import sys

def calculate_confidence_interval(data, confidence=0.90):
    """Calculate confidence interval for the data"""
    n = len(data)
    if n == 0:
        return 0, 0, 0
    
    mean = np.mean(data)
    std_err = stats.sem(data)
    margin = std_err * stats.t.ppf((1 + confidence) / 2, n - 1)
    
    return mean, mean - margin, mean + margin

def plot_loss_experiment(csv_file):
    """Plot download time vs packet loss rate"""
    df = pd.read_csv(csv_file)
    
    # Group by loss rate
    loss_rates = sorted(df['loss'].unique())
    means = []
    lower_bounds = []
    upper_bounds = []
    
    for loss in loss_rates:
        subset = df[df['loss'] == loss]['ttc']
        mean, lower, upper = calculate_confidence_interval(subset.values)
        means.append(mean)
        lower_bounds.append(lower)
        upper_bounds.append(upper)
    
    # Create plot
    fig, ax = plt.subplots(figsize=(10, 6))
    
    ax.plot(loss_rates, means, 'b-o', linewidth=2, markersize=8, label='Mean Download Time')
    ax.fill_between(loss_rates, lower_bounds, upper_bounds, alpha=0.3, 
                     label='90% Confidence Interval')
    
    ax.set_xlabel('Packet Loss Rate (%)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Download Time (seconds)', fontsize=12, fontweight='bold')
    ax.set_title('Download Time vs Packet Loss Rate\n(Fixed delay=20ms, jitter=0ms)', 
                 fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.legend(fontsize=10)
    
    # Add value labels
    for i, (loss, mean) in enumerate(zip(loss_rates, means)):
        ax.annotate(f'{mean:.1f}s', 
                   xy=(loss, mean), 
                   xytext=(0, 10), 
                   textcoords='offset points',
                   ha='center',
                   fontsize=9)
    
    plt.tight_layout()
    plt.savefig('loss_experiment.png', dpi=300, bbox_inches='tight')
    print(f"[PLOT] Saved loss_experiment.png")
    plt.close()
    
    # Print statistics
    print("\n=== Loss Experiment Statistics ===")
    print(f"{'Loss (%)':>10} {'Mean (s)':>12} {'90% CI Lower':>15} {'90% CI Upper':>15}")
    print("-" * 55)
    for loss, mean, lower, upper in zip(loss_rates, means, lower_bounds, upper_bounds):
        print(f"{loss:>10} {mean:>12.2f} {lower:>15.2f} {upper:>15.2f}")

def plot_jitter_experiment(csv_file):
    """Plot download time vs delay jitter"""
    df = pd.read_csv(csv_file)
    
    # Group by jitter
    jitter_values = sorted(df['jitter'].unique())
    means = []
    lower_bounds = []
    upper_bounds = []
    
    for jitter in jitter_values:
        subset = df[df['jitter'] == jitter]['ttc']
        mean, lower, upper = calculate_confidence_interval(subset.values)
        means.append(mean)
        lower_bounds.append(lower)
        upper_bounds.append(upper)
    
    # Create plot
    fig, ax = plt.subplots(figsize=(10, 6))
    
    ax.plot(jitter_values, means, 'r-s', linewidth=2, markersize=8, label='Mean Download Time')
    ax.fill_between(jitter_values, lower_bounds, upper_bounds, alpha=0.3, color='red',
                     label='90% Confidence Interval')
    
    ax.set_xlabel('Delay Jitter (ms)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Download Time (seconds)', fontsize=12, fontweight='bold')
    ax.set_title('Download Time vs Delay Jitter\n(Fixed delay=20ms, loss=1%)', 
                 fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.legend(fontsize=10)
    
    # Add value labels
    for i, (jitter, mean) in enumerate(zip(jitter_values, means)):
        ax.annotate(f'{mean:.1f}s', 
                   xy=(jitter, mean), 
                   xytext=(0, 10), 
                   textcoords='offset points',
                   ha='center',
                   fontsize=9)
    
    plt.tight_layout()
    plt.savefig('jitter_experiment.png', dpi=300, bbox_inches='tight')
    print(f"[PLOT] Saved jitter_experiment.png")
    plt.close()
    
    # Print statistics
    print("\n=== Jitter Experiment Statistics ===")
    print(f"{'Jitter (ms)':>12} {'Mean (s)':>12} {'90% CI Lower':>15} {'90% CI Upper':>15}")
    print("-" * 55)
    for jitter, mean, lower, upper in zip(jitter_values, means, lower_bounds, upper_bounds):
        print(f"{jitter:>12} {mean:>12.2f} {lower:>15.2f} {upper:>15.2f}")

def compare_with_benchmark(csv_file, benchmark_file, exp_type):
    """Compare results with TA benchmarks"""
    df = pd.read_csv(csv_file)
    benchmark = pd.read_csv(benchmark_file)
    
    print(f"\n=== Comparison with Benchmark ({exp_type}) ===")
    
    if exp_type == 'loss':
        group_col = 'loss'
    else:
        group_col = 'jitter'
    
    for value in sorted(df[group_col].unique()):
        our_mean = df[df[group_col] == value]['ttc'].mean()
        bench_mean = benchmark[benchmark[group_col] == value]['ttc'].iloc[0]
        diff_pct = ((our_mean - bench_mean) / bench_mean) * 100
        
        status = "✓ PASS" if our_mean <= bench_mean * 1.2 else "✗ NEEDS IMPROVEMENT"
        print(f"{group_col.capitalize()}={value:3}: Our={our_mean:6.2f}s, "
              f"Benchmark={bench_mean:6.2f}s, Diff={diff_pct:+6.1f}% {status}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 plot_results.py <loss|jitter|both> [benchmark_file]")
        sys.exit(1)
    
    exp_type = sys.argv[1].lower()
    
    if exp_type in ['loss', 'both']:
        csv_file = 'reliability_loss.csv'
        try:
            plot_loss_experiment(csv_file)
            
            # Compare with benchmark if provided
            if len(sys.argv) > 2:
                benchmark_file = sys.argv[2]
                compare_with_benchmark(csv_file, benchmark_file, 'loss')
        except FileNotFoundError:
            print(f"[ERROR] File {csv_file} not found. Run experiments first.")
        except Exception as e:
            print(f"[ERROR] Error processing loss experiment: {e}")
    
    if exp_type in ['jitter', 'both']:
        csv_file = 'reliability_jitter.csv'
        try:
            plot_jitter_experiment(csv_file)
            
            # Compare with benchmark if provided
            if len(sys.argv) > 2:
                benchmark_file = sys.argv[2]
                compare_with_benchmark(csv_file, benchmark_file, 'jitter')
        except FileNotFoundError:
            print(f"[ERROR] File {csv_file} not found. Run experiments first.")
        except Exception as e:
            print(f"[ERROR] Error processing jitter experiment: {e}")
    
    if exp_type not in ['loss', 'jitter', 'both']:
        print("Invalid experiment type. Use 'loss', 'jitter', or 'both'")
        sys.exit(1)

if __name__ == "__main__":
    main()