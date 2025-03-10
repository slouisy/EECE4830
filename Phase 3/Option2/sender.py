import socket
import struct
import time
import random

def calculate_checksum(data):
    #Custom 16-bit checksum
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
ERROR_PROBABILITY = 0 #% chance of ACK bit-error

retransmissions = 0

def make_packet(seq_num, data):
#Create packet with sequence number and custom checksum
    checksum = calculate_checksum(data)
    header = struct.pack("!B2s", seq_num, checksum)  # 1 byte seq num, 2 bytes checksum
    return header + data

def introduce_error(ack_packet):
    """Introduce bit errors in the ACK packet with a given probability."""
    if len(ack_packet) > 0 and random.random() < ERROR_PROBABILITY:
        print("Introducing error in ACK packet!")
        ack_packet = bytearray(ack_packet)
        # Flip a random bit in the ACK packet
        byte_index = random.randint(0, len(ack_packet) - 1)
        bit_index = random.randint(0, 7)
        ack_packet[byte_index] ^= (1 << bit_index)
        return bytes(ack_packet)
    return ack_packet

def send_file(filename, sock, addr):
    global retransmissions
    with open(filename, "rb") as f:
        seq_num = 0
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
                        ack = introduce_error(ack)  # Introduce error in ACK
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
                start_time = time.time()
                ack_received = False
                while time.time() - start_time < TIMEOUT:
                    try:
                        sock.settimeout(TIMEOUT - (time.time() - start_time))
                        ack, _ = sock.recvfrom(1)
                        ack = introduce_error(ack)  # Introduce error in ACK
                        ack_seq = struct.unpack("!B", ack)[0]
                        if ack_seq == seq_num:
                            print(f"ACK {ack_seq} received correctly.")
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
    global ERROR_PROBABILITY
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver_addr = (UDP_IP, UDP_PORT)
    filename = "image.jpg"

    ERROR_PROBABILITY = int(input("Enter error rate: ")) / 100

    start_time = time.time()
    send_file(filename, sock, receiver_addr)
    print(f"Execution time: {time.time() - start_time:.4f} seconds")
    print(f"Retransmissions: {retransmissions}")
    sock.close()

if __name__ == "__main__":
    main()