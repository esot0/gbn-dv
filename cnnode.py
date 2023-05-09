import argparse
import os
import sys
import threading
from gbnnode import GBNNode
from dvnode import DVNode
import time
import socket
import json

WINDOW_SIZE = 5
TYPE = "probabilistic"
SENDER_PORT_OFFSET = 7  # primes :)
REC_PORT_OFFSET = 11


def unique_port_offset(port1, port2):
    base_offset = port1 + port2
    sender_offset = (base_offset + SENDER_PORT_OFFSET) % 99
    receiver_offset = (base_offset + REC_PORT_OFFSET) % 99
    return sender_offset, receiver_offset


class ProbeDVNode(DVNode):
    def __init__(self, local_port, receive_neighbors, send_neighbors, loss_rate, is_probe_sender, last=False):
        self.ready = False
        self.loss_rate = loss_rate
        self.gbn_sender_nodes = {}
        self.gbn_receiver_nodes = {}
        self.is_probe_sender = is_probe_sender
        self.start_probing = threading.Event()
        self.local_port = local_port
        self.receive_neighbors = receive_neighbors
        self.send_neighbors = send_neighbors
        self.neighbors = {**receive_neighbors, **send_neighbors}
        self.last = last
        self.lock = threading.Lock()
        self.routing_table = {local_port: (0, local_port)}
        self.gbn_sender_nodes = {}

        for port, l_rate in self.receive_neighbors.items():  # Neighbors to receive from
            self.routing_table[port] = (0, port)
            unique_sender_offset, unique_receiver_offset = unique_port_offset(local_port, port)
            receiver_port = local_port + unique_receiver_offset
            neighbor_sender_port = port + unique_sender_offset

            self.gbn_receiver_nodes[port] = GBNNode(receiver_port,
                                                    neighbor_sender_port,
                                                    WINDOW_SIZE, TYPE,
                                                    0, show_messages=False)

            sender_thread = threading.Thread(target=self.gbn_receiver_nodes[port].sender, daemon=True)
            receiver_thread = threading.Thread(target=self.gbn_receiver_nodes[port].receiver, daemon=True)

            sender_thread.start()
            receiver_thread.start()

        for port, l_rate in self.send_neighbors.items():  # Neighbors to send to
            self.routing_table[port] = (0, port)
            unique_sender_offset, unique_receiver_offset = unique_port_offset(local_port, port)
            sender_port = local_port + unique_sender_offset
            neighbor_receiver_port = port + unique_receiver_offset

            self.gbn_sender_nodes[port] = GBNNode(sender_port,
                                                  neighbor_receiver_port,
                                                  WINDOW_SIZE, TYPE,
                                                  self.loss_rate, show_messages=False)
            sender_thread = threading.Thread(target=self.gbn_sender_nodes[port].sender, daemon=True)
            receiver_thread = threading.Thread(target=self.gbn_sender_nodes[port].receiver, daemon=True)

            sender_thread.start()
            receiver_thread.start()

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(('localhost', self.local_port))

        threading.Thread(target=self.listen_for_messages, daemon=True).start()
        threading.Thread(target=self.send_probe_packets, daemon=True).start()

        if self.last:
            self.send_routing_messages()

    def send_routing_messages(self):
        for port, distance in self.neighbors.items():
            message = f"{self.local_port} {self.routing_table}"
            timestamp = time.time()
            self.socket.sendto(message.encode(), ('localhost', port))
            print(f"[{timestamp}] Message sent from Node {self.local_port} to Node {port}")

    def update_routing_table(self, sender_port, sender_routing_table):
        updated = False
        for port, (distance, next_hop) in sender_routing_table.items():
            if port != self.local_port and sender_port in self.receive_neighbors:
                new_distance = round(distance + self.receive_neighbors[sender_port], 2)
                if port not in self.routing_table:
                    self.routing_table[port] = (new_distance, sender_port)
                    updated = True
                elif new_distance < self.routing_table[port][0] and new_distance != 0 or self.routing_table[port][0]==0:
                    self.routing_table[port] = (new_distance, sender_port)
                    updated = True

        self.print_routing_table()
        return updated

    def send_probe_packets(self):
        last_check = time.time()
        last_stat_print = time.time()
        updated = False
        while True:
            for dest_port, dist in self.send_neighbors.items():
                if dest_port != self.local_port:
                    self.gbn_sender_nodes[dest_port].fill_buffer("PROBE")
                    num_sent = self.gbn_sender_nodes[dest_port].num_sent
                    num_dropped = self.gbn_sender_nodes[dest_port].num_dropped
                    with self.lock:
                        if num_sent != 0:
                            p_dropped = round(num_dropped / num_sent, 2)

                            now = time.time()
                            if(now-last_stat_print>=1):
                                print(
                                    f"[{time.time()}] Link to {dest_port}: <{num_sent}> packets sent, {num_dropped} packets lost, loss rate {p_dropped}")
                                last_stat_print = now
                            if self.routing_table[dest_port][0] != p_dropped:
                                updated = True
                                self.routing_table[dest_port] = (p_dropped, dest_port)
            now = time.time()
            if now-last_check >= 5 and updated:
                updated = False
                self.send_routing_messages()
                last_check = now


def create_nodes(network_info, sender_neighbors, receiver_neighbors, drop_value):
    dv_nodes = {}

    # Create GBNNode and DVNode instances for each node
    for i, node_info in enumerate(network_info):
        node_port, neighbors, loss_rate = node_info

        if i == 0:  # Make the first node the probe sender
            print(i)
            print(f"Creating probe sender node {node_port}")
            dv_nodes[node_port] = ProbeDVNode(node_port, neighbors, drop_value, True, last=False)
        elif node_info != network_info[-1]:
            print(f"Creating node {node_port}")
            dv_nodes[node_port] = ProbeDVNode(node_port, neighbors, drop_value, False, last=False)
        else:
            print(f"Creating last node {node_port}")
            dv_nodes[node_port] = ProbeDVNode(node_port, neighbors, drop_value, False, last=True)

    for node_info in network_info:
        node_port, receive_dict, send_loss_rate = node_info
        receiver_neighbors[node_port] = receive_dict

        send_dict = {}
        for other_node_info in network_info:
            other_node_port, _, other_send_loss_rate = other_node_info
            if other_node_port in receive_dict:
                send_dict[other_node_port] = other_send_loss_rate
        sender_neighbors[node_port] = send_dict

    for dv_node in dv_nodes.values():
        dv_node.start_threads()

    return dv_nodes


def main():
    args = sys.argv[1:]
    local_port = int(args.pop(0))
    args.pop(0)  # Remove 'receive'
    receive_neighbors = {}
    send_neighbors = {}

    while args and args[0] != 'send':
        neighbor_port = int(args.pop(0))
        loss_rate = float(args.pop(0))
        receive_neighbors[neighbor_port] = loss_rate

    args.pop(0)  # Remove 'send'

    while args and args[0] != 'last':
        neighbor_port = int(args.pop(0))
        loss_rate = float(args.pop(0))
        send_neighbors[neighbor_port] = loss_rate

    last = False
    if args and args[0] == 'last':
        last = True

    dv_node = ProbeDVNode(local_port, receive_neighbors, send_neighbors, loss_rate,
                          is_probe_sender=(len(send_neighbors) > 0), last=last)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\nNode {local_port} routing table after update:")
        dv_node.print_routing_table()
        print("Exiting...")
        sys.exit(0)


if __name__ == '__main__':
    main()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Exiting...")
        os._exit(0)
