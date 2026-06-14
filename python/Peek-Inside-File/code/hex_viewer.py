import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTextEdit, 
                             QPushButton, QVBoxLayout, QHBoxLayout, QSplitter,
                             QWidget, QFileDialog, QLabel)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt

class HexViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('PyQt5 File Hex Viewer')
        self.resize(1200, 700)

        # Central Widget and Main Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Header/Button Layout
        header_layout = QHBoxLayout()
        self.load_btn = QPushButton("Open File")
        self.load_btn.clicked.connect(self.open_file_dialog)
        header_layout.addWidget(self.load_btn)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)

        # Splitter for Side by Side views
        self.splitter = QSplitter(Qt.Horizontal)

        # Text View
        self.text_view = QTextEdit()
        self.text_view.setReadOnly(True)
        self.text_view.setPlaceholderText("Text content will appear here...")
        self.text_view.setFont(QFont("Courier New", 10))
        
        # Hex View
        self.hex_view = QTextEdit()
        self.hex_view.setReadOnly(True)
        self.hex_view.setPlaceholderText("Hexadecimal content will appear here...")
        self.hex_view.setFont(QFont("Courier New", 10))

        # Synchronize Scrollbars
        self.text_view.verticalScrollBar().valueChanged.connect(
            self.hex_view.verticalScrollBar().setValue
        )
        self.hex_view.verticalScrollBar().valueChanged.connect(
            self.text_view.verticalScrollBar().setValue
        )

        self.splitter.addWidget(self.text_view)
        self.splitter.addWidget(self.hex_view)
        main_layout.addWidget(self.splitter)

    def open_file_dialog(self):
        # Restricted extensions as requested
        file_filter = "Supported Files (*.txt *.bat *.py *.f *.fs *.zf);;All Files (*)"
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open File", "", file_filter
        )

        if file_path:
            self.process_file(file_path)

    def process_file(self, path):
        try:
            # Read as binary to get exact hex values (including \n as 0A)
            with open(path, 'rb') as f:
                blob = f.read()

            # 1. Generate Text View (Replacing non-printable characters for display)
            # We use 'replace' to handle decoding errors gracefully
            text_content = blob.decode('utf-8', errors='replace')
            self.text_view.setPlainText(text_content)

            # 2. Generate Hex View
            # We iterate byte by byte. If we encounter a newline (0x0A), 
            # we add a newline in the hex view to keep them somewhat aligned.
            hex_lines = []
            current_line = []
            for byte in blob:
                hex_val = f"{byte:02X}"
                if byte < 0x20:
                    # Highlight control characters (less than 0x20) in red
                    current_line.append(f'<span style="color: red;">{hex_val}</span>')
                else:
                    current_line.append(hex_val)

                if byte == 10:  # ASCII Newline (0A)
                    hex_lines.append(" ".join(current_line))
                    current_line = []
            
            if current_line:
                hex_lines.append(" ".join(current_line))

            # Use setHtml to support the colored spans, wrapped in <pre> for alignment
            self.hex_view.setHtml(f'<pre>{"<br>".join(hex_lines)}</pre>')

        except Exception as e:
            self.text_view.setPlainText(f"Error loading file: {e}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    viewer = HexViewer()
    viewer.show()
    sys.exit(app.exec_())