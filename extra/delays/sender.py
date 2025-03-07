import socket
import struct
import time
import random

UDP_IP = "127.0.0.1"
UDP_PORT = 5005
PACKET_SIZE = 1024

delay_range = 0
retransmissions = 0
total_delay = 0

def calculate_checksum(data):
    checksum = 0
    for i in range(0, len(data), 2):
        word = data[i] + (data[i+1] << 8) if i + 1 < len(data) else data[i]
        checksum += word
        checksum = (checksum & 0xFFFF) + (checksum >> 16)
    
    return (~checksum & 0xFFFF).to_bytes(2, "big")

def make_packet(seq_num, data):
    checksum = calculate_checksum(data)
    header = struct.pack("!B2s", seq_num, checksum)
    return header + data

def send_file(filename, sock, addr):
    global retransmissions, total_delay
    with open(filename, "rb") as f:
        seq_num = 0
        timeout = 0.1  # Initial timeout

        while True:
            chunk = f.read(PACKET_SIZE)
            if not chunk:
                eof_packet = struct.pack("!B2s", 255, b'\x00\x00')
                sock.sendto(eof_packet, addr)
                print("EOF packet sent. Waiting for EOF ACK...")
                
                while True:
                    try:
                        sock.settimeout(timeout)
                        ack, _ = sock.recvfrom(1)
                        ack_seq, = struct.unpack("!B", ack)
                        
                        if ack_seq == 255:
                            print("EOF ACK received. File transfer complete.")
                            return
                    except socket.timeout:
                        print("Timeout! Resending EOF packet.")
                        sock.sendto(eof_packet, addr)

            packet = make_packet(seq_num, chunk)
            send_time = time.time()

            while True:
                delay = 0
                if random.random() < delay_range: #delay based on range
                    delay = random.uniform(0, 0.5)  # Simulated network delay
                
                total_delay += delay
                print(f"Simulated Network Delay: {delay:.2f}s")
                time.sleep(delay)

                sock.sendto(packet, addr)
                print(f"Sent packet {seq_num}, waiting for ACK...")

                try:
                    sock.settimeout(timeout)
                    ack, _ = sock.recvfrom(1)
                    ack_seq, = struct.unpack("!B", ack)

                    if ack_seq == seq_num:
                        rtt = time.time() - send_time
                        timeout = min(0.5, rtt * 1.5)  # Adaptive timeout

                        print(f"ACK {ack_seq} received, moving to next packet.")
                        if timeout:
                            print(f"New timeout: {timeout:.2f}s")
                            
                        seq_num = 1 - seq_num
                        break
                except socket.timeout:
                    print(f"Timeout! Resending packet {seq_num}")
                    retransmissions += 1
                except BlockingIOError:
                    # Handle the BlockingIOError gracefully
                    print("BlockingIOError occurred. Waiting and retrying...")
                    retransmissions += 1
                    time.sleep(0.1)  # Sleep before retrying the recvfrom
                    continue

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver_addr = (UDP_IP, UDP_PORT)

    global delay_range
    delay_range = int(input("Enter delay range: "))
    delay_range = delay_range/100

    filename = "image.jpg"
    start_time = time.time()
    send_file(filename, sock, receiver_addr)
    end_time = time.time()

    global retransmissions
    
    sock.close()
    print(f"Total transmission time: {end_time - start_time:.4f} seconds")
    print(f"Retransmissions: {retransmissions}")

if __name__ == "__main__":
    main()
