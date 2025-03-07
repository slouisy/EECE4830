import socket
import struct
import time
import random

UDP_IP = "127.0.0.1"
UDP_PORT = 5005
PACKET_SIZE = 1024

def calculate_checksum(data):
    checksum = 0
    for i in range(0, len(data), 2):
        word = data[i] + (data[i+1] << 8) if i + 1 < len(data) else data[i]
        checksum += word
        checksum = (checksum & 0xFFFF) + (checksum >> 16)
    
    return (~checksum & 0xFFFF).to_bytes(2, "big")

def is_corrupt(data, received_checksum):
    return received_checksum != calculate_checksum(data)

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))

    expected_seq_num = 0
    last_ack = struct.pack("!B", 1 - expected_seq_num)

    with open("received.jpg", "wb") as f:
        while True:
            print("Waiting for packets...")
            packet, addr = sock.recvfrom(PACKET_SIZE + 3)
            print("Packet received!")

            seq_num, received_checksum = struct.unpack("!B2s", packet[:3])
            data = packet[3:]

            if seq_num == 255:
                print("EOF received. Sending EOF ACK...")
                time.sleep(random.uniform(0, 0.5))  # Simulated delay for EOF ACK
                sock.sendto(struct.pack("!B", 255), addr)
                break

            print(f"Received packet {seq_num}, expected {expected_seq_num}")
            print(f"Received checksum: {received_checksum.hex()}, Computed checksum: {calculate_checksum(data).hex()}")

            if not is_corrupt(data, received_checksum) and seq_num == expected_seq_num:
                f.write(data)
                print(f"Packet {seq_num} received correctly, sending ACK {seq_num}")
                ack_packet = struct.pack("!B", seq_num)
                expected_seq_num = 1 - expected_seq_num
                last_ack = ack_packet
            else:
                print(f"Corrupt packet or unexpected sequence number! Resending last ACK {last_ack.hex()}")

            if random.random() < 0.05: #only delay 5% of the time
                delay = random.uniform(0, 0.5);
                print(f"Delaying ACK {delay:.2f}")
                time.sleep(delay)  # Simulated delay before sending ACK
            
            sock.sendto(last_ack, addr)

    sock.close()

if __name__ == "__main__":
    main()
