import json
import os
import socket
import threading
import random
import sys
import time
import argparse
import random
from collections import deque


class GBNNode:
    def __init__(self, self_port, peer_port, window_size, drop_type, drop_value, show_messages=True):
        self.self_port = self_port
        self.peer_port = peer_port
        self.window_size = window_size
        self.drop_type = drop_type
        self.drop_value = drop_value
        self.num_dropped = 0
        self.show_messages = show_messages
        self.num_sent = 0
        self.message_length = 0
        self.buffer = deque()
        self.window_start = 0
        self.seq_num = 0
        self.expected_seq_num = 0
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('localhost', self.self_port))
        self.timer = None
        self.timeout = .5
        self.lock = threading.Lock()

    def send_message(self, seq_num, type, data, port):
        packet = json.dumps({"seq_num": seq_num, "type": type, "data": data, "sent": 0})
        self.sock.sendto(packet.encode(), ('localhost', port))

    def fill_buffer(self, message):
        self.message_length = len(message) + 1
        for ch in message:
            packet = {"seq_num": self.seq_num, "type": "DATA", "data": ch, "sent": 0}
            self.buffer.append(packet)
            self.seq_num += 1
        eot_packet = {"seq_num": self.seq_num, "type": "EOT", "data": "", "sent": 0}
        self.buffer.append(eot_packet)

    def sender(self):
        # Handle sender side logic
        while True:
            with self.lock:
                if self.buffer and self.timer is None:  # If no packet is currently sent out
                    self.timer = threading.Timer(self.timeout, self.resend_packets)
                    self.timer.start()

                    for i in range(self.window_start, self.window_start + self.window_size):

                        if i >= len(self.buffer):
                            break
                        packet_data = self.buffer[i]
                        drop = False
                        self.num_sent += 1

                        if self.drop_type == "probabilistic":
                            rand = random.randint(1, 100)
                            if rand <= self.drop_value * 100:
                                self.num_dropped += 1
                                drop = True

                        elif self.drop_type == "deterministic":
                            if self.num_sent % self.drop_value==0:
                                drop = True
                                self.num_dropped += 1

                        if not packet_data['sent'] and not drop:
                            self.send_message(packet_data['seq_num'], packet_data['type'], packet_data['data'],
                                              self.peer_port)
                            packet_data['sent'] = 1
            time.sleep(.01)

    def resend_packets(self):
        with self.lock:
            for packet_data in list(self.buffer)[0:self.window_size]:
                drop = False
                if self.drop_type == "probabilistic":
                    rand = random.randint(1, 100)
                    if rand <= self.drop_value * 100:
                        # print("Dropped packet", packet_data['seq_num'])
                        self.num_dropped += 1
                        drop = True

                elif self.drop_type == "deterministic":
                    if self.num_sent % self.drop_value == 0:
                        drop = True
                        self.num_dropped += 1
                if not drop:
                    self.send_message(packet_data['seq_num'], packet_data['type'], packet_data['data'], self.peer_port)
        self.timer = None
    def receiver(self):
        while True:
            try:
                data, addr = self.sock.recvfrom(1024, socket.MSG_DONTWAIT)
                packet = json.loads(data.decode())
                packet_type = packet['type']
                recv_seq_num = packet['seq_num']
                packet_data = packet['data']

                if packet_type == "EOT":
                    if recv_seq_num == self.expected_seq_num:
                        if self.show_messages:
                            print("EOT Received, Transmission finished")
                        self.send_ack(recv_seq_num, "EOT")
                        loss_rate = (self.num_dropped / self.num_sent) * 100
                        if self.show_messages:
                            print(
                                f"[Summary] {self.num_dropped}/{self.num_sent} packets discarded, loss rate = {round(loss_rate, 2)}%")
                        self.reset_state()

                elif packet_type == "DATA":
                    if recv_seq_num == self.expected_seq_num:
                        if (self.show_messages):
                            print(f"[{time.time()}] packet{recv_seq_num} {packet_data} received")
                        self.send_ack(recv_seq_num)
                        self.expected_seq_num += 1
                    else:
                        if (self.show_messages):
                            print(
                                f"[{time.time()}] packet{recv_seq_num} {packet_data} discarded, expected {self.expected_seq_num}")
                        # Send ACK for the last in-order packet received, or -1 if no packets have been received to prompt the sender to start
                        self.send_ack(self.expected_seq_num - 1)
                elif packet_type == "ACK":
                    self.handle_ack(recv_seq_num)

            except socket.error:
                pass
            time.sleep(.01)

    def send_ack(self, ack_seq_num, data=""):
        self.num_sent+=1
        drop = False
        if self.drop_type == "probabilistic":
            rand = random.randint(1, 100)
            if rand <= self.drop_value * 100:
                # print("Dropped packet", packet_data['seq_num'])
                self.num_dropped += 1
                drop = True

        elif self.drop_type == "deterministic":
            if self.num_sent % self.drop_value == 0:
                drop = True
                self.num_dropped += 1
        if data:
            if (self.show_messages):
                print(f"[{time.time()}] ACK{ack_seq_num} sent.")
        else:
            if (self.show_messages):
                print(f"[{time.time()}] ACK{ack_seq_num} sent, expecting packet{ack_seq_num + 1}")
        packet = json.dumps({"seq_num": ack_seq_num, "type": "ACK", "data": data})
        if not drop:
            self.sock.sendto(packet.encode(), ('localhost', self.peer_port))

    def reset_state(self):
        self.buffer = deque()
        self.window_start = 0
        self.message_length = 0
        self.seq_num = 0
        self.expected_seq_num = 0
        self.num_dropped = 0
        self.num_sent = 0
        self.timer = None

    def handle_ack(self, ack_seq_num):
        with self.lock:
            # Check if the received ACK sequence number is greater than the current window start
            if ack_seq_num >= self.window_start:
                # Calculate the number of packets to be acknowledged and removed from the buffer
                num_acks = ack_seq_num - self.window_start + 1
                # Remove the acknowledged packets from the buffer
                for _ in range(num_acks):
                    if self.buffer:
                        self.buffer.popleft()
                # Move the window forward with cumulative ACK
                self.window_start += num_acks
                self.expected_seq_num += num_acks

                # Reset the timer
                if self.timer is not None:
                    self.timer.cancel()
                    self.timer = None

                if (self.show_messages):
                    print(f"ACK{ack_seq_num} received, window moves to {self.window_start}")

                if self.window_start >= self.message_length-1 and self.window_start != 0 and self.num_sent != 0:
                    if (self.show_messages):
                        print(
                            f"[Summary] {self.num_dropped}/{self.num_sent} packets discarded, loss rate = {(self.num_dropped / self.num_sent) * 100 }%")
                    self.reset_state()  # Reset sender state
            else:
                if self.show_messages:
                    print(f"[{time.time()}] ACK{ack_seq_num} discarded")


# Need to be able to continuously send stuff, come to smoother stops. Not working rn
def main():
    parser = argparse.ArgumentParser(description="GBN node implementation")
    parser.add_argument("self_port", type=int, help="Node's own port")
    parser.add_argument("peer_port", type=int, help="Peer node's port")
    parser.add_argument("window_size", type=int, help="Window size for the Go-Back-N protocol")
    parser.add_argument("-d", "--deterministic", type=int, metavar="N", help="Deterministic drop of every N-th packet")
    parser.add_argument("-p", "--probabilistic", type=float, metavar="P", help="Probabilistic drop with probability P")

    args = parser.parse_args()

    if args.deterministic and args.probabilistic:
        print("You should only specify either -d or -p.")
        return

    if args.deterministic:
        drop_type = "deterministic"
        drop_value = args.deterministic
    elif args.probabilistic:
        drop_type = "probabilistic"
        drop_value = args.probabilistic
    else:
        drop_type = None
        drop_value = None

    gbn_node = GBNNode(args.self_port, args.peer_port, args.window_size, drop_type, drop_value)

    sender_thread = threading.Thread(target=gbn_node.sender)
    receiver_thread = threading.Thread(target=gbn_node.receiver)

    sender_thread.start()
    receiver_thread.start()

    while True:
        try:
            command = input("node> ")
            if command.startswith("send "):
                message = command[5:]
                gbn_node.fill_buffer(message)
            else:
                print("Invalid command. Only 'send <message>' is allowed.")
        except KeyboardInterrupt:
            print("\nExiting...")
            os._exit(0)

    sender_thread.join()
    receiver_thread.join()


if __name__ == "__main__":
    main()
