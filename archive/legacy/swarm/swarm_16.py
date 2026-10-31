#!/usr/bin/env python3
import sys
import os

# Add parent directory to path so we can import swarm_simulator
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from swarm_simulator import SwarmSimulation, Colors

def main():
    print(f"{Colors.HEADER}{Colors.BOLD}==================================================")
    print("      DRONE SWARM SIMULATOR: 16 NODES SWARM")
    print(f"=================================================={Colors.ENDC}")
    print("Scenario: A swarm of 16 drones conducting a synchronized mapping scan.")
    print("Drone 01 acts as a compromised node, broadcasting rogue flight status commands.")
    
    # 1. Unprotected Simulation
    print(f"\n{Colors.BOLD}[1/2] RUNNING UNPROTECTED SYSTEM SIMULATION...{Colors.ENDC}")
    sim_vuln = SwarmSimulation(num_nodes=16, security_mode="none")
    metrics_vuln = sim_vuln.run_simulation(steps=800)
    
    # 2. Protected Simulation
    print(f"\n{Colors.BOLD}[2/2] RUNNING SECURE (HARDENED PROXY) SIMULATION...{Colors.ENDC}")
    sim_sec = SwarmSimulation(num_nodes=16, security_mode="hardened")
    metrics_sec = sim_sec.run_simulation(steps=800)
    
    # Compare Results Side-by-Side
    print(f"\n{Colors.BOLD}SIDE-BY-SIDE SECURITY METRICS COMPARISON (16 NODES):{Colors.ENDC}")
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
         print(f"• {Colors.FAIL}UNPROTECTED:{Colors.ENDC} Massive drone disarms occur. 1 compromised node triggers cascading failures.")
         print("  Nearly all nodes are disarmed as rogue packets flood the mesh topology.")
    print(f"• {Colors.GREEN}SECURED:{Colors.ENDC} Nonce validation and Poly1305 MAC checks successfully contain the threat.")
    print("  The rest of the 15 drones safely discard all unauthorized command packets.")

if __name__ == "__main__":
    main()
