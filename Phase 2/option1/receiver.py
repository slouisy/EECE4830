import socket
import struct
import random

UDP_IP = "127.0.0.1"
UDP_PORT = 5005
PACKET_SIZE = 1024
ERROR_RATE = 0.0  # Set error rate (0.0 to 0.6 for 0% to 60% corruption)

def calculate_checksum(data):
    """Custom 16-bit checksum similar to UDP"""
    checksum = 0
    for i in range(0, len(data), 2):
        word = data[i] + (data[i+1] << 8) if i + 1 < len(data) else data[i]
        checksum += word
        checksum = (checksum & 0xFFFF) + (checksum >> 16)  # Wrap around carry
    
    return (~checksum & 0xFFFF).to_bytes(2, "big")  # One’s complement

def is_corrupt(data, received_checksum):
    """Verify if checksum is correct"""
    return received_checksum != calculate_checksum(data)

def introduce_errors(data):
    """Randomly corrupts data based on the ERROR_RATE"""
    data = bytearray(data)
    for i in range(len(data)):
        if random.random() < ERROR_RATE:
            data[i] ^= 0xFF  # Flip all bits of the byte
    return bytes(data)

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))

    expected_seq_num = 0
    last_ack = struct.pack("!B", 1 - expected_seq_num)  # Default last ACK

    with open("received.jpg", "wb") as f:
        while True:
            print("Waiting for packets...")
            packet, addr = sock.recvfrom(PACKET_SIZE + 3)
            print("Packet received!")

            seq_num, received_checksum = struct.unpack("!B2s", packet[:3])
            data = packet[3:]
            
            # Introduce errors intentionally
            data = introduce_errors(data)

            # Check for EOF (End of File) signal
            if seq_num == 255:
                print("EOF received. Sending EOF ACK...")
                sock.sendto(struct.pack("!B", 255), addr)  # Send EOF ACK
                break  # Exit loop and close file

            print(f"Received packet {seq_num}, expected {expected_seq_num}")
            print(f"Received checksum: {received_checksum.hex()}, Computed checksum: {calculate_checksum(data).hex()}")

            if not is_corrupt(data, received_checksum) and seq_num == expected_seq_num:
                f.write(data)
                print(f"Packet {seq_num} received correctly, sending ACK {seq_num}")
                ack_packet = struct.pack("!B", seq_num)  # Send ACK for the received packet
                expected_seq_num = 1 - expected_seq_num  # Flip sequence number
                last_ack = ack_packet  # Update last ACK
            else:
                print(f"Corrupt packet or unexpected sequence number! Resending last ACK {last_ack.hex()}")

            sock.sendto(last_ack, addr)

    sock.close()  # Close socket after transmission is complete

if __name__ == "__main__":
    main()
