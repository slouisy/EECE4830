import sys
import threading
import socket
import struct
import time
import subprocess
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QLabel, QPushButton, QProgressBar,
    QGraphicsView, QGraphicsScene, QGraphicsEllipseItem, QVBoxLayout, QWidget, QHBoxLayout
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt, QTimer, pyqtSignal

UDP_IP = "127.0.0.1"
UDP_PORT = 5005
PACKET_SIZE = 1024

class FileTransferApp(QMainWindow):
    update_progress = pyqtSignal(int)  # Signal to update progress bar
    update_fsm = pyqtSignal(str)       # Signal to update FSM state
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("File Transfer & FSM")
        self.setGeometry(100, 100, 500, 500)
        self.update_progress.connect(self.update_progress_bar)
        self.update_fsm.connect(self.update_fsm_state)

        # Layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        layout = QVBoxLayout(self.central_widget)

        # Image Display (Data Transfer)
        self.image_label = QLabel(self)
        self.image_label.setPixmap(QPixmap("background.jpg"))  # Initial image
        self.image_label.setScaledContents(True)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setFixedSize(800, 400)
        layout.addWidget(self.image_label)

        # FSM Visualization
        self.scene = QGraphicsScene()
        self.fsm_view = QGraphicsView(self.scene, self)
        self.fsm_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.fsm_view.setFixedSize(320, 130)
        layout.addWidget(self.fsm_view)

        # FSM States (Sender & Receiver)
        self.sender_state = QGraphicsEllipseItem(50, 50, 50, 50)
        self.receiver_state = QGraphicsEllipseItem(300, 50, 50, 50)
        self.scene.addItem(self.sender_state)
        self.scene.addItem(self.receiver_state)

        # Progress Bar
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        # Buttons
        self.start_button = QPushButton("Start Transfer", self)
        self.stop_button = QPushButton("Stop", self)
        layout.addWidget(self.start_button)
        layout.addWidget(self.stop_button)

        # Connect Buttons
        self.start_button.clicked.connect(self.start_transfer)
        self.stop_button.clicked.connect(self.stop_transfer)

        # Timer for GUI Updates
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_gui)
        self.transfer_progress = 0

        # Variables for Thread Handling
        self.transfer_active = False

    # Start Transfer
    def start_transfer(self):
        if not self.transfer_active:
            self.transfer_active = True
            self.transfer_progress = 0
            self.timer.start(500)  # Update every 500ms
            self.receiver_thread = threading.Thread(target=self.begin_reception, daemon=True)
            self.receiver_thread.start()
            time.sleep(1)
            self.sender_process = subprocess.Popen([sys.executable, "sender.py"])  # Fixed subprocess call

    # Stop Transfer
    def stop_transfer(self):
        self.transfer_active = False
        self.timer.stop()
        self.progress_bar.setValue(0)
        self.update_fsm_state("IDLE")

    # Update Image as Transfer Progresses
    def update_image_progress(self, progress):
        """Update image to reflect transfer progress"""
        full_image = QPixmap("background.jpg")  # Load full image
        cropped_image = full_image.copy(0, 0, int(full_image.width() * (progress / 100)), full_image.height())
        self.image_label.setPixmap(cropped_image)

    def update_progress_bar(self, progress):
        """Update progress bar and image dynamically."""
        self.progress_bar.setValue(progress)
        self.update_image_progress(progress)

    # Update FSM State
    def update_fsm_state(self, state):
        """Change FSM visualization based on sender/receiver states"""
        if state == "SENDING":
            self.sender_state.setBrush(Qt.GlobalColor.yellow)
            self.receiver_state.setBrush(Qt.GlobalColor.gray)
        elif state == "RECEIVING":
            self.sender_state.setBrush(Qt.GlobalColor.gray)
            self.receiver_state.setBrush(Qt.GlobalColor.yellow)
        elif state == "COMPLETED":
            self.sender_state.setBrush(Qt.GlobalColor.green)
            self.receiver_state.setBrush(Qt.GlobalColor.green)
        elif state == "IDLE":
            self.sender_state.setBrush(Qt.GlobalColor.gray)
            self.receiver_state.setBrush(Qt.GlobalColor.gray)

    # Update GUI during Transfer
    def update_gui(self):
        if self.transfer_active and self.transfer_progress < 100:
            self.transfer_progress += 10
            self.progress_bar.setValue(self.transfer_progress)
            self.update_image_progress(self.transfer_progress)

            # FSM Logic: Sending (0-50%), Receiving (50-100%)
            if self.transfer_progress < 50:
                self.update_fsm_state("SENDING")
            else:
                self.update_fsm_state("RECEIVING")
        else:
            self.timer.stop()
            self.update_fsm_state("COMPLETED")  # Mark as completed

    # Custom 16-bit checksum
    def calculate_checksum(self, data):
        checksum = 0
        for i in range(0, len(data), 2):
            word = data[i] + (data[i+1] << 8) if i + 1 < len(data) else data[i]
            checksum += word
            checksum = (checksum & 0xFFFF) + (checksum >> 16)
        return (~checksum & 0xFFFF).to_bytes(2, "big")

    def is_corrupt(self, data, received_checksum):
        return received_checksum != self.calculate_checksum(data)

    def begin_reception(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((UDP_IP, UDP_PORT))

        received_size = 0
        expected_size = 2048 * 100
        expected_seq_num = 0
        last_ack = struct.pack("!B", 1 - expected_seq_num)  # Default last ACK

        with open("received.jpg", "wb") as f:
            while True:
                print("Waiting for packets...")
                packet, addr = sock.recvfrom(PACKET_SIZE + 3)
                print("Packet received!")

                seq_num, received_checksum = struct.unpack("!B2s", packet[:3])
                data = packet[3:]

                # Check for EOF (End of File) signal
                if seq_num == 255:
                    print("EOF received. Sending EOF ACK...")
                    sock.sendto(struct.pack("!B", 255), addr)  # Send EOF ACK
                    break  # Exit loop and close file

                print(f"Received packet {seq_num}, expected {expected_seq_num}")
                print(f"Received checksum: {received_checksum.hex()}, Computed checksum: {self.calculate_checksum(data).hex()}")

                if not self.is_corrupt(data, received_checksum) and seq_num == expected_seq_num:
                    f.write(data)
                    received_size += len(data)
                    progress = min(100, int((received_size / expected_size) * 100))
                    self.update_progress.emit(progress)
                    self.update_fsm.emit("RECEIVING")
                    print(f"Packet {seq_num} received correctly, sending ACK {seq_num}")
                    ack_packet = struct.pack("!B", seq_num)  # Send ACK for the received packet
                    expected_seq_num = 1 - expected_seq_num  # Flip sequence number
                    last_ack = ack_packet  # Update last ACK
                else:
                    print(f"Corrupt packet or unexpected sequence number! Resending last ACK {last_ack.hex()}")

                sock.sendto(last_ack, addr)
        sock.close()  # Close socket after transmission is complete

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FileTransferApp()
    window.show()
    sys.exit(app.exec())
