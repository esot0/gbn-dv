import os
import sys
import time
import threading
from socket import socket, AF_INET, SOCK_DGRAM, timeout


class DVNode:
    def __init__(self, local_port, neighbors, last=False):
        self.local_port = local_port
        self.neighbors = neighbors
        self.routing_table = {local_port: (0, local_port)}

        for port, distance in self.neighbors.items():
            self.routing_table[port] = (distance, port)

        self.socket = socket(AF_INET, SOCK_DGRAM)
        self.socket.bind(('localhost', self.local_port))

        if last:
            self.send_routing_messages()

        threading.Thread(target=self.listen_for_messages).start()

    def send_routing_messages(self):
        for port, distance in self.neighbors.items():
            message = f"{self.local_port} {self.routing_table}"
            timestamp = time.time()
            self.socket.sendto(message.encode(), ('localhost', port))
            print(f"[{timestamp}] Message sent from Node {self.local_port} to Node {port}")

    def listen_for_messages(self):
        while True:
            data, addr = self.socket.recvfrom(4096)
            message = data.decode()

            sender_port, routing_table = message.split(" ", 1)
            sender_port = int(sender_port)
            routing_table = eval(routing_table)

            print(f"[{time.time()}] Message received at Node {self.local_port} from Node {sender_port}")
            updated = self.update_routing_table(sender_port, routing_table)

            if updated:
                self.send_routing_messages()

            self.print_routing_table()

    def update_routing_table(self, sender_port, sender_routing_table):
        updated = False
        if sender_port in self.neighbors:
            for port, (distance, next_hop) in sender_routing_table.items():
                if port != self.local_port:
                    new_distance = round(distance + self.neighbors[sender_port], 2)
                    if port not in self.routing_table or new_distance < self.routing_table[port][0]:
                        self.routing_table[port] = (new_distance, sender_port)
                        updated = True

        return updated

    def print_routing_table(self):
        print(f"[{time.time()}] Node {self.local_port} Routing Table")
        for port, (distance, next_hop) in self.routing_table.items():
            if next_hop == port:
                print(f"- ({distance}) -> Node {port}")
            else:
                print(f"- ({distance}) -> Node {port} ; Next hop -> Node {next_hop}")


def main():
    args = sys.argv[1:]
    local_port = int(args.pop(0))
    neighbors = {}
    last = False

    while args:
        neighbor_port = int(args.pop(0))
        loss_rate = float(args.pop(0))
        neighbors[neighbor_port] = loss_rate

        if args and args[0] == 'last':
            last = True
            args.pop(0)

    node = DVNode(local_port, neighbors, last)


if __name__ == '__main__':
    main()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nExiting...")
        os._exit(0)
