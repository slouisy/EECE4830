import socket
import struct
import time
import random

def calculate_checksum(data):
    # Custom 16-bit checksum
    checksum = 0
    for i in range(0, len(data), 2):
        word = data[i] + (data[i+1] << 8) if i + 1 < len(data) else data[i]
        checksum += word
        checksum = (checksum & 0xFFFF) + (checksum >> 16)  # Wrap around carry
    
    return (~checksum & 0xFFFF).to_bytes(2, "big")  # One’s complement

UDP_IP = "127.0.0.1"
UDP_PORT = 5005
PACKET_SIZE = 1024
TIMEOUT = 0.05  # 50ms timeout
ACK_LOSS_PROBABILITY = 0  

drops = 0
retransmissions = 0

def make_packet(seq_num, data):
    # Create packet with sequence number and custom checksum
    checksum = calculate_checksum(data)
    header = struct.pack("!B2s", seq_num, checksum)  # 1 byte seq num, 2 bytes checksum
    return header + data

#Timer object for simplicity
class Timer:
    def __init__(self, timeout):
        self.timeout = timeout
        self.start_time = 0
        self.running = False

    def start(self):
        self.start_time = time.time()
        self.running = True

    def stop(self):
        self.running = False

    def timed_out(self):
        return self.running and (time.time() - self.start_time > self.timeout)

def send_file(filename, sock, addr):
    global drops, retransmissions
    with open(filename, "rb") as f:
        seq_num = 0
        timer = Timer(TIMEOUT)
        while True:
            chunk = f.read(PACKET_SIZE)
            if not chunk:
                eof_packet = struct.pack("!B2s", 255, b'\x00\x00')
                sock.sendto(eof_packet, addr)
                print("EOF packet sent. Waiting for EOF ACK...")
                while True:
                    try:
                        sock.settimeout(TIMEOUT)
                        ack, _ = sock.recvfrom(1)
                        if struct.unpack("!B", ack)[0] == 255:
                            print("EOF ACK received. Transfer complete.")
                            return
                    except socket.timeout:
                        print("Timeout! Resending EOF packet.")
                        sock.sendto(eof_packet, addr)

            packet = make_packet(seq_num, chunk)
            while True:
                sock.sendto(packet, addr)
                print(f"Sent packet {seq_num}, waiting for ACK...")
                timer.start()
                ack_received = False
                while not timer.timed_out():
                    try:
                        sock.settimeout(TIMEOUT - (time.time() - timer.start_time))
                        ack, _ = sock.recvfrom(1)
                        
                        ###############################################
                        # Simulate ACK packet loss by using a random number
                        if random.random() < ACK_LOSS_PROBABILITY:
                            print(f"Simulating ACK loss for packet {seq_num}")
                            drops += 1
                            continue  # Drop the ACK and try again
                        ###############################################

                        ack_seq = struct.unpack("!B", ack)[0]
                        if ack_seq == seq_num:
                            print(f"ACK {ack_seq} received.")
                            timer.stop()
                            ack_received = True
                            seq_num = 1 - seq_num
                            break
                    except socket.timeout:
                        print(f"Timeout! Resending packet {seq_num}.")
                        retransmissions += 1
                        break
                if ack_received:
                    break

def main():
    global ACK_LOSS_PROBABILITY
    global retransmissions, drops
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver_addr = (UDP_IP, UDP_PORT)
    filename = "image.jpg"

    ACK_LOSS_PROBABILITY = int(input("Enter error rate: ")) / 100

    start_time = time.time()
    send_file(filename, sock, receiver_addr)
    print(f"Execution time: {time.time() - start_time:.4f} seconds")
    print(f"Dropped packets: {drops}")
    print(f"Retransmissions: {retransmissions}")
    sock.close()

if __name__ == "__main__":
    main()
