import socket
import struct
import time
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

ack_queue = queue.Queue()  # Thread-safe queue for ACKs
send_lock = threading.Lock()  # Lock for thread-safe packet transmission

def make_packet(seq_num, data):
    checksum = calculate_checksum(data)
    header = struct.pack("!B2s", seq_num, checksum)
    return header + data

def send_file(filename, sock, addr):
    with open(filename, "rb") as f:
        seq_num = 0  # Sequence numbers: 0 or 1

        while True:
            chunk = f.read(PACKET_SIZE)
            if not chunk:
                eof_packet = struct.pack("!B2s", 255, b'\x00\x00')  # 255 indicates EOF
                sock.sendto(eof_packet, addr)
                print("EOF packet sent. Waiting for EOF ACK...")
                while True:
                    try:
                        sock.settimeout(1.0)  # Timeout for retransmission
                        ack, _ = sock.recvfrom(1)
                        ack_seq, = struct.unpack("!B", ack)
                        if ack_seq == 255:
                            print("EOF ACK received. File transfer complete.")
                            return
                        else:
                            print(f"Unexpected ACK {ack_seq}, waiting for EOF ACK...")
                    except socket.timeout:
                        print("Timeout! Resending EOF packet.")
                        sock.sendto(eof_packet, addr)

            packet = make_packet(seq_num, chunk)
            while True:
                with send_lock:
                    sock.sendto(packet, addr)
                    print(f"Sent packet {seq_num}, waiting for ACK...")

                try:
                    sock.settimeout(1.0)
                    ack, _ = sock.recvfrom(1)
                    ack_seq, = struct.unpack("!B", ack)

                    if ack_seq == seq_num:
                        print(f"ACK {ack_seq} received, moving to next packet.")
                        seq_num = 1 - seq_num
                        break
                    else:
                        print(f"Unexpected ACK {ack_seq}, resending packet {seq_num}")
                except socket.timeout:
                    print(f"Timeout! Resending packet {seq_num}")

def listen_for_acks(sock):
    while True:
        ack, _ = sock.recvfrom(1)
        ack_queue.put(ack)

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver_addr = (UDP_IP, UDP_PORT)

    filename = "image.jpg"
    ack_thread = threading.Thread(target=listen_for_acks, args=(sock,))
    ack_thread.daemon = True
    ack_thread.start()

    send_thread = threading.Thread(target=send_file, args=(filename, sock, receiver_addr))
    send_thread.start()

    start_time = time.time()
    send_thread.join()
    end_time = time.time()

    sock.close()

    execution_time = end_time - start_time
    print(f"Execution time: {execution_time:.4f} seconds")

if __name__ == "__main__":
    main()