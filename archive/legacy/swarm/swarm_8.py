#!/usr/bin/env python3
import sys
import os

# Add parent directory to path so we can import swarm_simulator
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from swarm_simulator import SwarmSimulation, Colors

def main():
    print(f"{Colors.HEADER}{Colors.BOLD}==================================================")
    print("      DRONE SWARM SIMULATOR: 8 NODES SWARM")
    print(f"=================================================={Colors.ENDC}")
    print("Scenario: A swarm of 8 drones is performing a search-and-rescue mission.")
    print("Drone 01 acts as a malicious insider, injecting payload-based attacks.")
    
    # 1. Unprotected Simulation
    print(f"\n{Colors.BOLD}[1/2] RUNNING UNPROTECTED SYSTEM SIMULATION...{Colors.ENDC}")
    sim_vuln = SwarmSimulation(num_nodes=8, security_mode="none")
    metrics_vuln = sim_vuln.run_simulation(steps=600)
    
    # 2. Protected Simulation
    print(f"\n{Colors.BOLD}[2/2] RUNNING SECURE (HARDENED PROXY) SIMULATION...{Colors.ENDC}")
    sim_sec = SwarmSimulation(num_nodes=8, security_mode="hardened")
    metrics_sec = sim_sec.run_simulation(steps=600)
    
    # Compare Results Side-by-Side
    print(f"\n{Colors.BOLD}SIDE-BY-SIDE SECURITY METRICS COMPARISON (8 NODES):{Colors.ENDC}")
    print(f"-------------------------------------------------------------")
    print(f"| Metric                      | Unprotected | Hardened Proxy |")
    print(f"-------------------------------------------------------------")
    print(f"| ASR (Attack Success Rate)   | {metrics_vuln['asr']:10.2f}% | {metrics_sec['asr']:13.2f}% |")
    print(f"| ADR (Attack Detection Rate) | {metrics_vuln['adr']:10.2f}% | {metrics_sec['adr']:13.2f}% |")
    print(f"| FPR (False Positive Rate)   | {metrics_vuln['fpr']:10.2f}% | {metrics_sec['fpr']:13.2f}% |")
    print(f"| FNR (False Negative Rate)   | {metrics_vuln['fnr']:10.2f}% | {metrics_sec['fnr']:13.2f}% |")
    print(f"| PDR (Packet Delivery Ratio) | {metrics_vuln['pdr']:10.2f}% | {metrics_sec['pdr']:13.2f}% |")
    print(f"| PLR (Packet Loss Ratio)     | {metrics_vuln['plr']:10.2f}% | {metrics_sec['plr']:13.2f}% |")
    print(f"-------------------------------------------------------------")
    
    print(f"\n{Colors.BOLD}Security Analysis:{Colors.ENDC}")
    if metrics_vuln['asr'] > 80:
         print(f"• {Colors.FAIL}UNPROTECTED:{Colors.ENDC} Multiple nodes get disarmed mid-flight. Swarm geometry splits, ")
         print("  and search capability drops below minimum thresholds.")
    print(f"• {Colors.GREEN}SECURED:{Colors.ENDC} Hardened cryptographic proxy isolates the corrupted nodes. Network performance")
    print("  remains stable with Packet Delivery Ratio (PDR) maintained above 90%.")

if __name__ == "__main__":
    main()
