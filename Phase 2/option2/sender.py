import socket
import struct
import time
import random

UDP_IP = "127.0.0.1"
UDP_PORT = 5005
PACKET_SIZE = 1024

retransmissions = 0
errors = 0

def calculate_checksum(data):
    #Custom 16-bit checksum similar to UDP#
    checksum = 0
    for i in range(0, len(data), 2):
        word = data[i] + (data[i+1] << 8) if i + 1 < len(data) else data[i]
        checksum += word
        checksum = (checksum & 0xFFFF) + (checksum >> 16)  # Wrap around carry
    
    return (~checksum & 0xFFFF).to_bytes(2, "big")  # One’s complement

def make_packet(seq_num, data):
    #Create packet with sequence number and custom checksum#
    checksum = calculate_checksum(data)
    header = struct.pack("!B2s", seq_num, checksum)  # 1 byte seq num, 2 bytes checksum
    return header + data

def introduce_ack_error(ack_seq, error_rate):
    global errors
    #Randomly corrupt the ACK based on error rate#
    if random.randint(1, 100) <= error_rate:  # Simulate corruption based on percentage
        corrupted_ack = ack_seq ^ 1  # Flip sequence number (0 ↔ 1)
        print(f"!! Introducing error: Received corrupted ACK {corrupted_ack} instead of {ack_seq}")
        errors += 1
        return corrupted_ack
    return ack_seq

def send_file(filename, sock, addr, error_rate):
    global retransmissions
    with open(filename, "rb") as f:
        seq_num = 0  # Sequence numbers: 0 or 1

        while True:
            chunk = f.read(PACKET_SIZE)
            if not chunk:
                # Send EOF packet with special seq_num = 255
                eof_packet = struct.pack("!B2s", 255, b'\x00\x00')  # 255 indicates EOF
                sock.sendto(eof_packet, addr)
                print("EOF packet sent. Waiting for EOF ACK...")

                while True:
                    try:
                        sock.settimeout(1.0)  # Timeout for retransmission
                        ack, _ = sock.recvfrom(1)  # Expect 1-byte EOF ACK
                        ack_seq, = struct.unpack("!B", ack)
                        
                        if ack_seq == 255:
                            print("EOF ACK received. File transfer complete.")
                            return  # Exit function
                        else:
                            print(f"Unexpected ACK {ack_seq}, waiting for EOF ACK...")
                    except socket.timeout:
                        print("Timeout! Resending EOF packet.")
                        sock.sendto(eof_packet, addr)

            packet = make_packet(seq_num, chunk)
            while True:
                sock.sendto(packet, addr)
                print(f"Sent packet {seq_num}, waiting for ACK...")
                
                try:
                    sock.settimeout(1.0)  # Timeout for retransmission
                    ack, _ = sock.recvfrom(1)  # Expect 1-byte ACK
                    ack_seq, = struct.unpack("!B", ack)

                    # Introduce corruption in ACKs
                    ack_seq = introduce_ack_error(ack_seq, error_rate)

                    if ack_seq == seq_num:
                        print(f"ACK {ack_seq} received, moving to next packet.")
                        seq_num = 1 - seq_num  # Flip sequence number
                        break  # Move to next packet
                    else:
                        print(f"Corrupt ACK {ack_seq} detected, resending packet {seq_num}")
                        retransmissions += 1
                except socket.timeout:
                    print(f"Timeout! Resending packet {seq_num}")
                    retransmissions += 1

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver_addr = (UDP_IP, UDP_PORT)

    # Get error rate from user
    error_rate = int(input("Enter error rate: "))
    error_rate = max(0, min(error_rate, 100))  # Limit range to 0-100%

    filename = "image.jpg"

    start_time = time.time()
    send_file(filename, sock, receiver_addr, error_rate)
    end_time = time.time()

    sock.close()

    global retransmissions
    global errors
    execution_time = end_time - start_time  # Calculate the execution time
    print(f"Execution time: {execution_time:.4f} seconds")
    print(f"Retransmissions: {retransmissions}")
    print(f"Errors Introduced: {errors}")

if __name__ == "__main__":
    main()
