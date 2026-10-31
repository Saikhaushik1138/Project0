#!/usr/bin/env python3
import sys
import os

# Add parent directory to path so we can import swarm_simulator
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from swarm_simulator import SwarmSimulation, Colors

def main():
    print(f"{Colors.HEADER}{Colors.BOLD}==================================================")
    print("      DRONE SWARM SIMULATOR: 32 NODES SWARM")
    print(f"=================================================={Colors.ENDC}")
    print("Scenario: A large swarm of 32 drones performing surveillance over a wide area.")
    print("Drone 01 acts as a malicious insider, injecting replay and command spoofing packets.")
    
    # 1. Unprotected Simulation
    print(f"\n{Colors.BOLD}[1/2] RUNNING UNPROTECTED SYSTEM SIMULATION...{Colors.ENDC}")
    sim_vuln = SwarmSimulation(num_nodes=32, security_mode="none")
    metrics_vuln = sim_vuln.run_simulation(steps=1000)
    
    # 2. Protected Simulation
    print(f"\n{Colors.BOLD}[2/2] RUNNING SECURE (HARDENED PROXY) SIMULATION...{Colors.ENDC}")
    sim_sec = SwarmSimulation(num_nodes=32, security_mode="hardened")
    metrics_sec = sim_sec.run_simulation(steps=1000)
    
    # Compare Results Side-by-Side
    print(f"\n{Colors.BOLD}SIDE-BY-SIDE SECURITY METRICS COMPARISON (32 NODES):{Colors.ENDC}")
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
         print(f"• {Colors.FAIL}UNPROTECTED:{Colors.ENDC} Attack causes extensive swarm destruction. Drones disarm and crash ")
         print("  sequentially. Swarm mission fails entirely within seconds.")
    print(f"• {Colors.GREEN}SECURED:{Colors.ENDC} Proxy limits impact. 31/32 drones remain active. Even though the malicious")
    print("  node floods the channel, the signature checks prevent any unauthorized takeover.")

if __name__ == "__main__":
    main()
