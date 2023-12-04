from netmiko import ConnectHandler
from collections import defaultdict
import os
import re
import time
import getpass
import sys
# This script is able to determine where the CPP saturation is coming from.

def detect_loop_from_output(trace_output):
    macs_per_port_vlan = defaultdict(set)
    macs_to_ports = defaultdict(set)

    for line in trace_output.splitlines():
        if "dst=ff-ff-ff-ff-ff-ff" in line and "vid=" in line:
            src_mac = line.split("src=")[1].split()[0]
            port = line.split("port=")[1].split()[0]
            vid_hex_dirty = line.split("vid=")[1].split()[0]
            vid_hex = re.sub(r'[^0-9a-fA-Fx]', '', vid_hex_dirty)
            vid_decimal = int(vid_hex, 16)
            macs_per_port_vlan[(port, vid_decimal)].add(src_mac)
            macs_to_ports[src_mac].add(port)

    if not macs_per_port_vlan:
        print("No loops detected from the trace output.")
        return

    # Calculate dynamic threshold
    avg_macs = sum(len(macs) for macs in macs_per_port_vlan.values()) / len(macs_per_port_vlan)
    dynamic_threshold = avg_macs * 2  # Setting threshold as double the average can be adjusted whenever

    for (port, vid), macs in macs_per_port_vlan.items():
        if len(macs) > max(dynamic_threshold, 10):  # Use the larger of the two thresholds -
            print(f"Possible loop detected on Port: {port}, VLAN ID: {vid}")
            print(f"MACs associated with the loop: {', '.join(macs)}")

    # In the event we cannot determine if there is a loop from broadcast but have duplicate macs southbound (ingress
    # vlan mapping or vid mismatch)
    for mac, ports in macs_to_ports.items():
        if len(ports) > 1:
            print(f"MAC address {mac} detected on multiple ports: {', '.join(ports)}. Possible loop.")


def detect_loop_from_device(device):
    # Connect to the device
    connection = ConnectHandler(**device)

    # Enter enabled mode
    connection.send_command("en")

    # Clear any possible traces
    connection.send_command("clear trace")

    # Set trace level
    connection.send_command("trace level 9 3")

    # set terminal length to 0
    connection.send_command("terminal more disable")

    # Time to sleep before next command this is kinda broken if the switch is being hammered

    time.sleep(15)

    # Stop trace after 15 seconds
    connection.send_command_timing("Trace shut")

    # Retrieve the trace file
    trace_output = connection.send_command("show trace file")
    print(trace_output)

    # close our sessions
    connection.disconnect()

    detect_loop_from_output(trace_output)


def main():
    choice = input("Do you want to (1) connect to the device or (2) read from a text file named 'loop'? Enter 1 or 2: ")

    if choice == "1":

        device_type = "extreme_vsp"
        ip = input("Enter device IP address: ")
        username = input("Enter username: ")
        password = input("Password: ")

        device = {
            'device_type': device_type,
            'ip': ip,
            'username': username,
            'password': password,
            'session_log': "log.txt",
        }

        detect_loop_from_device(device)
    elif choice == "2":
        file_path = os.path.join(os.getcwd(), "../Lanes Scripts/loop.txt")
        if os.path.exists(file_path):
            with open(file_path, 'r') as file:
                trace_output = file.read()
            detect_loop_from_output(trace_output)
        else:
            print(f"File named 'loop' not found in directory: {os.getcwd()}")
    else:
        print("Invalid choice. Please enter 1 or 2.")


if __name__ == "__main__":
    main()
