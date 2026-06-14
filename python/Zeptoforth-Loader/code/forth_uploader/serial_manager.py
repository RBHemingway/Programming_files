import serial
import threading
import time
from PyQt5.QtCore import QObject, pyqtSignal

class SerialManager(QObject):
    received = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.ser = None
        self.running = False
        self.pacing_ms = 10

    def set_pacing(self, ms):
        self.pacing_ms = ms

    def open(self, port, baud, data_bits, parity_str, stop_bits_float):
        if self.ser:
            self.close()
        
        # Map parity string to serial constants
        parity_map = {
            "None": serial.PARITY_NONE,
            "Even": serial.PARITY_EVEN,
            "Odd": serial.PARITY_ODD,
            "Mark": serial.PARITY_MARK,
            "Space": serial.PARITY_SPACE,
        }
        parity = parity_map.get(parity_str, serial.PARITY_NONE)

        # Map stop bits float to serial constants
        stop_bits_map = {
            1.0: serial.STOPBITS_ONE,
            1.5: serial.STOPBITS_ONE_POINT_FIVE,
            2.0: serial.STOPBITS_TWO,
        }
        stop_bits = stop_bits_map.get(stop_bits_float, serial.STOPBITS_ONE)

        # Open the serial port with all specified parameters
        self.ser = serial.Serial(port, baud, bytesize=data_bits, parity=parity, stopbits=stop_bits, timeout=0.1)
        self.running = True # Only set running to True if serial port opened successfully
        threading.Thread(target=self._rx_loop, daemon=True).start()

    def close(self):
        self.running = False
        if self.ser:
            try:
                self.ser.close()
            except:
                pass
        self.ser = None

    def _rx_loop(self):
        while self.running and self.ser and self.ser.is_open:
            try:
                data = self.ser.read(1024)
                if data:
                    self.received.emit(data.decode(errors='ignore'))
            except:
                break

    def send_line(self, line):
        if not self.ser or not self.ser.is_open:
            return

        # Ignore anything from the first backslash or '(' to the end of the line
        indices = [i for i in [line.find('\\'), line.find('(')] if i != -1]
        if indices:
            comment_idx = min(indices)
            line = line[:comment_idx]

        self.ser.write(line.encode('utf-8') + b'\n')
        self.ser.flush()
        time.sleep(self.pacing_ms / 1000.0)

    def upload_file(self, path):
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    self.send_line(line)
