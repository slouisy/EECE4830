import socket
import struct
import random
import threading
import queue

def calculate_checksum(data):
    checksum = 0
    for i in range(0, len(data), 2):
        word = data[i] + (data[i+1] << 8) if i + 1 < len(data) else data[i]
        checksum += word
        checksum = (checksum & 0xFFFF) + (checksum >> 16)
    
    return (~checksum & 0xFFFF).to_bytes(2, "big")


UDP_IP = "127.0.0.1"
UDP_PORT = 5005
PACKET_SIZE = 1024
ERROR_RATE = 0.0  # Adjustable error rate (0 to 60)

packet_queue = queue.Queue()
ack_queue = queue.Queue()
process_lock = threading.Lock()

def is_corrupt(data, received_checksum):
    return received_checksum != calculate_checksum(data)

def introduce_errors(data, error_rate):
    if not data:
        return data
    if random.random() < error_rate:
        corrupted_data = bytearray(data)
        num_corruptions = random.randint(1, min(3, len(data)))
        for _ in range(num_corruptions):
            index = random.randint(0, len(data) - 1)
            corrupted_data[index] ^= 0x01  # Flip a single bit
        return bytes(corrupted_data)
    return data

def process_packets(sock):
    expected_seq_num = 0
    last_ack = struct.pack("!B", 1 - expected_seq_num)

    with open("received.jpg", "wb") as f:
        while True:
            packet = packet_queue.get()
            addr = packet[1]
            packet = packet[0]

            seq_num, received_checksum = struct.unpack("!B2s", packet[:3])
            data = packet[3:]

            data = introduce_errors(data, ERROR_RATE)

            if seq_num == 255:
                print("EOF received. Sending EOF ACK...")
                sock.sendto(struct.pack("!B", 255), addr)
                break

            print(f"Received packet {seq_num}, expected {expected_seq_num}")
            print(f"Received checksum: {received_checksum.hex()}, Computed checksum: {calculate_checksum(data).hex()}")

            if not is_corrupt(data, received_checksum) and seq_num == expected_seq_num:
                with process_lock:
                    f.write(data)
                    print(f"Packet {seq_num} received correctly, sending ACK {seq_num}")
                    ack_packet = struct.pack("!B", seq_num)
                    expected_seq_num = 1 - expected_seq_num
                    last_ack = ack_packet
            else:
                print(f"Corrupt packet or unexpected sequence number! Resending last ACK {last_ack.hex()}")

            ack_queue.put((last_ack, addr))

def send_acks(sock):
    while True:
        ack, addr = ack_queue.get()
        sock.sendto(ack, addr)

def main():
    global ERROR_RATE
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))

    process_thread = threading.Thread(target=process_packets, args=(sock,))
    process_thread.daemon = True
    process_thread.start()

    ack_thread = threading.Thread(target=send_acks, args=(sock,))
    ack_thread.daemon = True
    ack_thread.start()

    while True:
        print("Waiting for packets...")
        packet, addr = sock.recvfrom(PACKET_SIZE + 3)
        print("Packet received!")

        # Check if it's an EOF packet (seq_num == 255)
        seq_num, _ = struct.unpack("!B2s", packet[:3])
        if seq_num == 255:
            print("EOF packet received. Terminating receiver.")
            sock.sendto(struct.pack("!B", 255), addr)
            break  # Exit the loop when EOF packet is received

        packet_queue.put((packet, addr))  # Add packet to the queue

    print("Receiver shutting down.")
    sock.close()


if __name__ == "__main__":
    error_input = int(input("Enter error rate (0 to 60): "))
    ERROR_RATE = error_input / 100
    main()
