import socket
import struct

UDP_IP = "127.0.0.1"
UDP_PORT = 5005
PACKET_SIZE = 1024

errors = 0

def calculate_crc16(data):
    # CRC-16 with polynomial 0x8005 (x^16 + x^15 + x^2 + 1)
    crc = 0xFFFF  # Initial value
    for byte in data:
        crc ^= byte << 8  # Align byte to the leftmost position
        for _ in range(8):  # Process each bit
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x8005  # XOR with the polynomial
            else:
                crc <<= 1
            crc &= 0xFFFF  # Ensure CRC is 16-bit
    return struct.pack("!H", crc)  # Return CRC as 2-byte value

def is_corrupt(data, received_crc):
    # Verify if CRC is correct
    return received_crc != calculate_crc16(data)

def main():
    global errors
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))

    expected_seq_num = 0
    last_ack = struct.pack("!B", 1 - expected_seq_num)  # Default last ACK

    with open("received.jpg", "wb") as f:
        while True:
            print("Waiting for packets...")
            packet, addr = sock.recvfrom(PACKET_SIZE + 3)  # Packet includes header (seq num + CRC)
            print("Packet received!")

            seq_num, received_crc = struct.unpack("!B2s", packet[:3])
            data = packet[3:]

            # Check for EOF (End of File) signal
            if seq_num == 255:
                print("EOF received. Sending EOF ACK...")
                sock.sendto(struct.pack("!B", 255), addr)  # Send EOF ACK
                break  # Exit loop and close file

            print(f"Received packet {seq_num}, expected {expected_seq_num}")
            print(f"Received CRC: {received_crc.hex()}, Computed CRC: {calculate_crc16(data).hex()}")

            if not is_corrupt(data, received_crc) and seq_num == expected_seq_num:
                f.write(data)
                print(f"Packet {seq_num} received correctly, sending ACK {seq_num}")
                ack_packet = struct.pack("!B", seq_num)  # Send ACK for the received packet
                expected_seq_num = 1 - expected_seq_num  # Flip sequence number
                last_ack = ack_packet  # Update last ACK
            else:
                errors += 1
                print(f"Corrupt packet or unexpected sequence number! Resending last ACK {last_ack.hex()}")

            sock.sendto(last_ack, addr)

    print(f"Errors Caught: {errors}")
    sock.close()  # Close socket after transmission is complete

if __name__ == "__main__":
    main()
