#!/usr/bin/env python3
"""
Plot results for Part 2 experiments from CSV files.
Usage: python3 plot_results.py <experiment_name>
"""

import sys
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats


def calculate_confidence_interval(data, confidence=0.90):
    """Calculate confidence interval for data."""
    n = len(data)
    if n <= 1:
        return 0
    mean = np.mean(data)
    stderr = stats.sem(data)
    margin = stderr * stats.t.ppf((1 + confidence) / 2, n - 1)
    return margin


def plot_fixed_bandwidth(csv_file, output_file):
    """Plot fixed bandwidth experiment results."""
    print(f"Reading {csv_file}...")
    df = pd.read_csv(csv_file)
    
    # Strip whitespace from column names
    df.columns = df.columns.str.strip()
    
    # Group by bandwidth and calculate statistics
    grouped = df.groupby('bw').agg({
        'link_util': ['mean', 'std', 'count'],
        'jfi': ['mean', 'std', 'count']
    }).reset_index()
    
    # Flatten column names
    grouped.columns = ['bw', 'util_mean', 'util_std', 'util_count', 
                       'jfi_mean', 'jfi_std', 'jfi_count']
    
    # Calculate confidence intervals
    ci_util = []
    ci_jfi = []
    for _, row in grouped.iterrows():
        bw = row['bw']
        util_data = df[df['bw'] == bw]['link_util'].values
        jfi_data = df[df['bw'] == bw]['jfi'].values
        ci_util.append(calculate_confidence_interval(util_data))
        ci_jfi.append(calculate_confidence_interval(jfi_data))
    
    grouped['util_ci'] = ci_util
    grouped['jfi_ci'] = ci_jfi
    
    # Create plot
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    # Plot 1: Link Utilization
    ax1.errorbar(grouped['bw'], grouped['util_mean'], yerr=grouped['util_ci'],
                 marker='o', linestyle='-', linewidth=2, markersize=8,
                 capsize=5, capthick=2, label='Link Utilization', color='#1F77B4')
    ax1.set_xlabel('Bandwidth (Mbps)', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Link Utilization', fontsize=12, fontweight='bold')
    ax1.set_title('Fixed Bandwidth: Link Utilization vs Bandwidth', 
                  fontsize=13, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.legend(fontsize=11)
    
    for _, row in grouped.iterrows():
        ax1.annotate(f"{row['util_mean']:.3f}", 
                    xy=(row['bw'], row['util_mean']),
                    xytext=(0, 10), textcoords='offset points',
                    ha='center', fontsize=8)
    
    # Plot 2: Jain Fairness Index
    ax2.errorbar(grouped['bw'], grouped['jfi_mean'], yerr=grouped['jfi_ci'],
                 marker='s', linestyle='-', linewidth=2, markersize=8,
                 capsize=5, capthick=2, label='JFI', color='#27AE60')
    ax2.set_xlabel('Bandwidth (Mbps)', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Jain Fairness Index', fontsize=12, fontweight='bold')
    ax2.set_title('Fixed Bandwidth: Fairness vs Bandwidth', 
                  fontsize=13, fontweight='bold')
    ax2.set_ylim([0.95, 1.01])
    ax2.grid(True, alpha=0.3)
    ax2.legend(fontsize=11)
    
    for _, row in grouped.iterrows():
        ax2.annotate(f"{row['jfi_mean']:.3f}", 
                    xy=(row['bw'], row['jfi_mean']),
                    xytext=(0, 5), textcoords='offset points',
                    ha='center', fontsize=8)
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"✅ Plot saved to {output_file}")
    
    print("\n" + "="*60)
    print("FIXED BANDWIDTH - SUMMARY STATISTICS")
    print("="*60)
    print(f"{'BW (Mbps)':>10} | {'Link Util':>10} | {'±CI (90%)':>10} | {'JFI':>10}")
    print("-"*60)
    for _, row in grouped.iterrows():
        print(f"{int(row['bw']):>10} | {row['util_mean']:>10.4f} | "
              f"{row['util_ci']:>10.4f} | {row['jfi_mean']:>10.4f}")
    print("-"*60)
    print(f"{'Average':>10} | {grouped['util_mean'].mean():>10.4f} | "
          f"{'':>10} | {grouped['jfi_mean'].mean():>10.4f}")
    print("="*60)


def plot_varying_loss(csv_file, output_file):
    """Plot varying loss experiment results."""
    print(f"Reading {csv_file}...")
    df = pd.read_csv(csv_file)
    df.columns = df.columns.str.strip()
    
    grouped = df.groupby('loss').agg({
        'link_util': ['mean', 'std', 'count'],
        'jfi': ['mean', 'std', 'count']
    }).reset_index()
    
    grouped.columns = ['loss', 'util_mean', 'util_std', 'util_count',
                       'jfi_mean', 'jfi_std', 'jfi_count']
    
    ci_util = []
    ci_jfi = []
    for _, row in grouped.iterrows():
        loss = row['loss']
        util_data = df[df['loss'] == loss]['link_util'].values
        jfi_data = df[df['loss'] == loss]['jfi'].values
        ci_util.append(calculate_confidence_interval(util_data))
        ci_jfi.append(calculate_confidence_interval(jfi_data))
    
    grouped['util_ci'] = ci_util
    grouped['jfi_ci'] = ci_jfi
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    ax1.errorbar(grouped['loss'], grouped['util_mean'], yerr=grouped['util_ci'],
                 marker='o', linestyle='-', linewidth=2, markersize=8,
                 capsize=5, capthick=2, label='Link Utilization', color='#E74C3C')
    ax1.set_xlabel('Packet Loss Rate (%)', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Link Utilization', fontsize=12, fontweight='bold')
    ax1.set_title('Varying Loss: Link Utilization vs Loss Rate', 
                  fontsize=13, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.legend(fontsize=11)
    
    for _, row in grouped.iterrows():
        ax1.annotate(f"{row['util_mean']:.3f}", 
                    xy=(row['loss'], row['util_mean']),
                    xytext=(0, 10), textcoords='offset points',
                    ha='center', fontsize=9)
    
    ax2.errorbar(grouped['loss'], grouped['jfi_mean'], yerr=grouped['jfi_ci'],
                 marker='s', linestyle='-', linewidth=2, markersize=8,
                 capsize=5, capthick=2, label='JFI', color='#27AE60')
    ax2.set_xlabel('Packet Loss Rate (%)', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Jain Fairness Index', fontsize=12, fontweight='bold')
    ax2.set_title('Varying Loss: Fairness vs Loss Rate', 
                  fontsize=13, fontweight='bold')
    ax2.set_ylim([0.95, 1.01])
    ax2.grid(True, alpha=0.3)
    ax2.legend(fontsize=11)
    
    for _, row in grouped.iterrows():
        ax2.annotate(f"{row['jfi_mean']:.3f}", 
                    xy=(row['loss'], row['jfi_mean']),
                    xytext=(0, 5), textcoords='offset points',
                    ha='center', fontsize=9)
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"✅ Plot saved to {output_file}")
    
    print("\n" + "="*60)
    print("VARYING LOSS - SUMMARY STATISTICS")
    print("="*60)
    print(f"{'Loss (%)':>10} | {'Link Util':>10} | {'±CI (90%)':>10} | {'JFI':>10}")
    print("-"*60)
    for _, row in grouped.iterrows():
        print(f"{row['loss']:>10.1f} | {row['util_mean']:>10.4f} | "
              f"{row['util_ci']:>10.4f} | {row['jfi_mean']:>10.4f}")
    print("-"*60)
    print(f"{'Average':>10} | {grouped['util_mean'].mean():>10.4f} | "
          f"{'':>10} | {grouped['jfi_mean'].mean():>10.4f}")
    print("="*60)


def plot_asymmetric_flows(csv_file, output_file):
    """Plot asymmetric flows experiment results."""
    print(f"Reading {csv_file}...")
    df = pd.read_csv(csv_file)
    df.columns = df.columns.str.strip()
    
    grouped = df.groupby('delay_c2_ms').agg({
        'link_util': ['mean', 'std', 'count'],
        'jfi': ['mean', 'std', 'count']
    }).reset_index()
    
    grouped.columns = ['delay_c2_ms', 'util_mean', 'util_std', 'util_count',
                       'jfi_mean', 'jfi_std', 'jfi_count']
    
    ci_util = []
    ci_jfi = []
    for _, row in grouped.iterrows():
        delay = row['delay_c2_ms']
        util_data = df[df['delay_c2_ms'] == delay]['link_util'].values
        jfi_data = df[df['delay_c2_ms'] == delay]['jfi'].values
        ci_util.append(calculate_confidence_interval(util_data))
        ci_jfi.append(calculate_confidence_interval(jfi_data))
    
    grouped['util_ci'] = ci_util
    grouped['jfi_ci'] = ci_jfi
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    ax1.errorbar(grouped['delay_c2_ms'], grouped['util_mean'], yerr=grouped['util_ci'],
                 marker='o', linestyle='-', linewidth=2, markersize=8,
                 capsize=5, capthick=2, label='Link Utilization', color='#1F77B4')
    ax1.set_xlabel('Client 2 Delay (ms)', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Link Utilization', fontsize=12, fontweight='bold')
    ax1.set_title('Asymmetric Flows: Link Utilization vs RTT Asymmetry', 
                  fontsize=13, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.legend(fontsize=11)
    
    for _, row in grouped.iterrows():
        ax1.annotate(f"{row['util_mean']:.3f}", 
                    xy=(row['delay_c2_ms'], row['util_mean']),
                    xytext=(0, 10), textcoords='offset points',
                    ha='center', fontsize=9)
    
    ax2.errorbar(grouped['delay_c2_ms'], grouped['jfi_mean'], yerr=grouped['jfi_ci'],
                 marker='s', linestyle='-', linewidth=2, markersize=8,
                 capsize=5, capthick=2, label='JFI', color='#FF7F0E')
    ax2.set_xlabel('Client 2 Delay (ms)', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Jain Fairness Index', fontsize=12, fontweight='bold')
    ax2.set_title('Asymmetric Flows: Fairness vs RTT Asymmetry (CRITICAL)', 
                  fontsize=13, fontweight='bold')
    ax2.axhline(y=0.95, color='red', linestyle='--', linewidth=1.5, 
                label='Good Fairness Threshold (0.95)')
    ax2.set_ylim([0.85, 1.01])
    ax2.grid(True, alpha=0.3)
    ax2.legend(fontsize=10)
    
    for _, row in grouped.iterrows():
        ax2.annotate(f"{row['jfi_mean']:.3f}", 
                    xy=(row['delay_c2_ms'], row['jfi_mean']),
                    xytext=(0, 5), textcoords='offset points',
                    ha='center', fontsize=9)
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"✅ Plot saved to {output_file}")
    
    print("\n" + "="*60)
    print("ASYMMETRIC FLOWS - SUMMARY STATISTICS")
    print("="*60)
    print(f"{'Delay (ms)':>12} | {'Link Util':>10} | {'±CI (90%)':>10} | {'JFI':>10}")
    print("-"*60)
    for _, row in grouped.iterrows():
        print(f"{int(row['delay_c2_ms']):>12} | {row['util_mean']:>10.4f} | "
              f"{row['util_ci']:>10.4f} | {row['jfi_mean']:>10.4f}")
    print("-"*60)
    print(f"{'Average':>12} | {grouped['util_mean'].mean():>10.4f} | "
          f"{'':>10} | {grouped['jfi_mean'].mean():>10.4f}")
    print("="*60)


def plot_background_udp(csv_file, output_file):
    """Plot background UDP experiment results."""
    print(f"Reading {csv_file}...")
    df = pd.read_csv(csv_file)
    df.columns = df.columns.str.strip()
    
    grouped = df.groupby('udp_off_mean').agg({
        'link_util': ['mean', 'std', 'count'],
        'jfi': ['mean', 'std', 'count']
    }).reset_index()
    
    grouped.columns = ['udp_off_mean', 'util_mean', 'util_std', 'util_count',
                       'jfi_mean', 'jfi_std', 'jfi_count']
    
    grouped = grouped.sort_values('udp_off_mean', ascending=False)
    
    ci_util = []
    ci_jfi = []
    for _, row in grouped.iterrows():
        udp_mean = row['udp_off_mean']
        util_data = df[df['udp_off_mean'] == udp_mean]['link_util'].values
        jfi_data = df[df['udp_off_mean'] == udp_mean]['jfi'].values
        ci_util.append(calculate_confidence_interval(util_data))
        ci_jfi.append(calculate_confidence_interval(jfi_data))
    
    grouped['util_ci'] = ci_util
    grouped['jfi_ci'] = ci_jfi
    
    labels = []
    for off_mean in grouped['udp_off_mean']:
        if off_mean >= 1.0:
            labels.append(f'Light\n({off_mean:.1f}s)')
        elif off_mean >= 0.7:
            labels.append(f'Medium\n({off_mean:.1f}s)')
        else:
            labels.append(f'Heavy\n({off_mean:.1f}s)')
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    x_pos = np.arange(len(grouped))
    
    bars1 = ax1.bar(x_pos, grouped['util_mean'], yerr=grouped['util_ci'],
                    capsize=5, alpha=0.7, color=['#27AE60', '#FF7F0E', '#E74C3C'])
    ax1.set_xlabel('UDP Background Load', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Link Utilization', fontsize=12, fontweight='bold')
    ax1.set_title('Background UDP: Link Utilization vs UDP Load', 
                  fontsize=13, fontweight='bold')
    ax1.set_xticks(x_pos)
    ax1.set_xticklabels(labels, fontsize=10)
    ax1.grid(True, alpha=0.3, axis='y')
    
    for i, (bar, row) in enumerate(zip(bars1, grouped.itertuples())):
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height,
                f'{row.util_mean:.3f}',
                ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    bars2 = ax2.bar(x_pos, grouped['jfi_mean'], yerr=grouped['jfi_ci'],
                    capsize=5, alpha=0.7, color=['#27AE60', '#FF7F0E', '#E74C3C'])
    ax2.set_xlabel('UDP Background Load', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Jain Fairness Index', fontsize=12, fontweight='bold')
    ax2.set_title('Background UDP: Fairness vs UDP Load', 
                  fontsize=13, fontweight='bold')
    ax2.set_xticks(x_pos)
    ax2.set_xticklabels(labels, fontsize=10)
    ax2.set_ylim([0.85, 1.01])
    ax2.axhline(y=0.95, color='red', linestyle='--', linewidth=1, 
                label='Good Fairness (0.95)')
    ax2.grid(True, alpha=0.3, axis='y')
    ax2.legend(fontsize=10)
    
    for i, (bar, row) in enumerate(zip(bars2, grouped.itertuples())):
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height,
                f'{row.jfi_mean:.3f}',
                ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"✅ Plot saved to {output_file}")
    
    print("\n" + "="*60)
    print("BACKGROUND UDP - SUMMARY STATISTICS")
    print("="*60)
    print(f"{'UDP Load':>15} | {'Link Util':>10} | {'JFI':>10}")
    print("-"*60)
    for i, row in grouped.iterrows():
        load_label = labels[list(grouped.index).index(i)].split('\n')[0]
        print(f"{load_label:>15} | {row['util_mean']:>10.4f} | "
              f"{row['jfi_mean']:>10.4f}")
    print("-"*60)
    print(f"{'Average':>15} | {grouped['util_mean'].mean():>10.4f} | "
          f"{grouped['jfi_mean'].mean():>10.4f}")
    print("="*60)


def plot_all_experiments():
    """Plot all experiments."""
    experiments = [
        ('fixed_bandwidth', plot_fixed_bandwidth),
        ('varying_loss', plot_varying_loss),
        ('asymmetric_flows', plot_asymmetric_flows),
        ('background_udp', plot_background_udp)
    ]
    
    print("="*70)
    print("PLOTTING ALL EXPERIMENTS")
    print("="*70)
    
    for exp_name, plot_func in experiments:
        csv_file = f'p2_fairness_{exp_name}.csv'
        output_file = f'p2_{exp_name}_plot.png'
        print(f"\n{'='*70}")
        print(f"Processing: {exp_name}")
        print(f"{'='*70}")
        
        try:
            plot_func(csv_file, output_file)
        except FileNotFoundError:
            print(f"❌ Error: {csv_file} not found. Skipping {exp_name}.")
        except Exception as e:
            print(f"❌ Error plotting {exp_name}: {e}")
    
    print(f"\n{'='*70}")
    print("✅ ALL PLOTS COMPLETED!")
    print(f"{'='*70}")


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 plot_results.py <experiment_name>")
        print("\nAvailable experiment names:")
        print("  - fixed_bandwidth")
        print("  - varying_loss")
        print("  - asymmetric_flows")
        print("  - background_udp")
        print("  - all (plots all experiments)")
        print("\nExample:")
        print("  python3 plot_results.py fixed_bandwidth")
        print("  python3 plot_results.py all")
        sys.exit(1)
    
    experiment = sys.argv[1]
    
    experiment_map = {
        'fixed_bandwidth': plot_fixed_bandwidth,
        'varying_loss': plot_varying_loss,
        'asymmetric_flows': plot_asymmetric_flows,
        'background_udp': plot_background_udp,
        'all': plot_all_experiments
    }
    
    if experiment not in experiment_map:
        print(f"❌ Error: Unknown experiment '{experiment}'")
        print("\nAvailable experiments:")
        for exp in experiment_map.keys():
            print(f"  - {exp}")
        sys.exit(1)
    
    if experiment == 'all':
        plot_all_experiments()
    else:
        csv_file = f'p2_fairness_{experiment}.csv'
        output_file = f'p2_{experiment}_plot.png'
        
        print("="*70)
        print(f"PLOTTING: {experiment}")
        print("="*70)
        
        try:
            experiment_map[experiment](csv_file, output_file)
        except FileNotFoundError:
            print(f"❌ Error: {csv_file} not found.")
            print(f"   Make sure you have run the experiment first.")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Error: {e}")
            sys.exit(1)
    
    print("\n✅ Done!")


if __name__ == "__main__":
    main()
