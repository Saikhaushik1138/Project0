import sys
import re
import numpy as np

def analyze_gazebo_stats(file_path):
    print(f"Analyzing {file_path} for 1% low frames...")
    
    real_times = []
    # Regex to find real_time { sec: ... nsec: ... }
    # Depending on 'gz topic' output format, it might look different
    # Usually it's a block like:
    # real_time {
    #   sec: 123
    #   nsec: 456
    # }
    
    current_sec = 0
    with open(file_path, 'r') as f:
        for line in f:
            if 'sec:' in line:
                val = int(re.search(r'\d+', line).group())
                if 'real_time' in prev_line or 'sec:' in line: # simplistic
                    current_sec = val
            if 'nsec:' in line:
                nsec = int(re.search(r'\d+', line).group())
                real_times.append(current_sec + nsec / 1e9)
            prev_line = line

    if len(real_times) < 2:
        print("Not enough data to analyze.")
        return

    deltas = np.diff(real_times)
    fps = 1.0 / deltas
    
    avg_fps = np.mean(fps)
    low_1_percent = np.percentile(fps, 1)
    
    print(f"Average Frame Rate: {avg_fps:.2f} FPS")
    print(f"1% Low Frame Rate:  {low_1_percent:.2f} FPS")
    print(f"Peak Stutter (Max Delta): {np.max(deltas)*1000:.2f} ms")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        analyze_gazebo_stats(sys.argv[1])
    else:
        print("Usage: python3 analyze_stats.py <gazebo_stats.log>")
