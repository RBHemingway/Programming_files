import os
import json

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, QListWidgetItem,
    QFileDialog, QComboBox, QLabel, QSlider, QPlainTextEdit, QSplitter, QTabWidget,
    QMessageBox, QMenu, QProgressDialog, QApplication
)
from PyQt5.QtGui import QFont, QColor, QDesktopServices
from .forth_monitor_text_edit import ForthMonitorTextEdit
from PyQt5.QtCore import Qt, QEvent, pyqtSignal, QUrl
from serial_manager import SerialManager
import serial.tools.list_ports

class FileListWidget(QListWidget):
    """Custom ListWidget that supports dragging files from Windows Explorer."""
    files_dropped = pyqtSignal(list)
    open_in_reference = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.CopyAction)
            event.accept()
            paths = []
            for u in event.mimeData().urls():
                if u.isLocalFile():
                    paths.append(u.toLocalFile())
                else:
                    # This handles web URLs dragged from a browser
                    paths.append(u.toString())
            self.files_dropped.emit(paths)
        else:
            event.ignore()

    def show_context_menu(self, pos):
        """Displays a right-click menu to remove items or clear the list."""
        item = self.itemAt(pos)
        menu = QMenu(self)
        open_ref_action = None
        if item:
            open_ref_action = menu.addAction("Open in Reference")
        remove_action = menu.addAction("Remove Selected")
        clear_action = menu.addAction("Clear All")
        
        # Execute menu at global cursor position
        action = menu.exec_(self.viewport().mapToGlobal(pos))
        
        if action == open_ref_action and item:
            self.open_in_reference.emit(item.data(Qt.UserRole))
        elif action == remove_action:
            for item in self.selectedItems():
                self.takeItem(self.row(item))
        elif action == clear_action:
            self.clear()

class ReferenceTextEdit(QPlainTextEdit):
    """Custom QPlainTextEdit that supports dropping a file to load its content."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.CopyAction)
            event.accept()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.CopyAction)
            event.accept()
            file_path = event.mimeData().urls()[0].toLocalFile()
            if os.path.isfile(file_path) and file_path.lower().endswith((".fs", ".f", ".txt")):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        self.setPlainText(f.read())
                except Exception as e:
                    print(f"Error loading dropped file: {e}")
        else:
            super().dropEvent(event)

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQt5 Forth Uploader for zeptoforth")
        self.resize(1600, 1000)
        self.setStyleSheet("background-color: #A0A0A0;")  # Medium grey background for the main window

        # Determine the base directory for profiles relative to the 'forth_uploader' package root
        script_dir = os.path.dirname(os.path.abspath(__file__))
        forth_uploader_root = os.path.dirname(script_dir)  # This is .../forth_uploader
        self.profile_dir = os.path.join(forth_uploader_root, "profiles")
        os.makedirs(self.profile_dir, exist_ok=True)

        self.serial = SerialManager()
        self.serial.received.connect(self.on_serial_rx)

        self.current_folder = os.getcwd()
        self.files = []
        self.selected_profile_name = None  # To store the actively selected profile
        self.reference_fullpath = ""
        self.last_loaded_files = []        # To track file list changes for auto-saving

        self.build_ui()
        self.refresh_ports()
        self.load_files()

    def build_ui(self):
        layout = QVBoxLayout(self)

        # --- Top controls ---
        top = QHBoxLayout()
        layout.addLayout(top)

        top.addWidget(QLabel("Port:"))
        self.port_combo = QComboBox()
        top.addWidget(self.port_combo)

        top.addWidget(QLabel("Baud:"))
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["115200", "9600"])
        top.addWidget(self.baud_combo)

        top.addWidget(QLabel("Data Bits:"))
        self.data_bits_combo = QComboBox()
        self.data_bits_combo.addItems(["8", "7", "6", "5"])  # Common data bits, 8 is most common
        self.data_bits_combo.setCurrentText("8")  # Default to 8
        top.addWidget(self.data_bits_combo)

        top.addWidget(QLabel("Parity:"))
        self.parity_combo = QComboBox()
        self.parity_combo.addItems(["None", "Even", "Odd", "Mark", "Space"])
        self.parity_combo.setCurrentText("None")  # Default to None
        top.addWidget(self.parity_combo)

        top.addWidget(QLabel("Stop Bits:"))
        self.stop_bits_combo = QComboBox()
        self.stop_bits_combo.addItems(["1", "1.5", "2"])
        self.stop_bits_combo.setCurrentText("1")  # Default to 1
        top.addWidget(self.stop_bits_combo)

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.on_connect)
        top.addWidget(self.connect_btn)

        top.addWidget(QLabel("Pacing (ms):"))
        self.pacing_slider = QSlider(Qt.Horizontal)
        self.pacing_slider.setRange(0, 100)
        self.pacing_slider.setValue(10)
        self.pacing_slider.valueChanged.connect(self.on_pacing_change)
        top.addWidget(self.pacing_slider)

        # --- Middle: file list + serial monitor ---
        # Using QSplitter for horizontal adjustability
        mid_splitter = QSplitter(Qt.Horizontal)  # Create the main horizontal splitter

        # 2.0. Left Section: Tabbed Widget for Monitor and Files
        self.tab_widget_left = QTabWidget()

        # --- a. Monitor Tab (moved from middle) ---
        self.monitor = ForthMonitorTextEdit()
        self.monitor.return_pressed.connect(self.on_monitor_return_pressed)
        self.monitor.setFont(QFont("Consolas", 10))
        self.monitor.setStyleSheet("""
            QPlainTextEdit {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #8082F7, stop:1 #F0FAFF);
                border: 1px solid #C0C0C0;
            }""")

        monitor_tab_layout = QVBoxLayout()
        monitor_tab_layout.addWidget(self.monitor)

        monitor_btn_layout = QHBoxLayout()
        self.clear_btn = QPushButton("Clear Monitor")
        self.clear_btn.clicked.connect(lambda: self.monitor.clear())
        monitor_btn_layout.addWidget(self.clear_btn)

        self.new_profile_btn = QPushButton("New Profile")
        self.new_profile_btn.clicked.connect(self.on_new_profile)
        monitor_btn_layout.addWidget(self.new_profile_btn)

        monitor_tab_layout.addLayout(monitor_btn_layout)
        monitor_tab_widget = QWidget()
        monitor_tab_widget.setLayout(monitor_tab_layout)
        self.tab_widget_left.addTab(monitor_tab_widget, "Monitor")

        # --- b. Files Tab ---
        files_tab_layout = QVBoxLayout()
        folder_ref_btns_layout = QHBoxLayout()

        self.reference_btn = QPushButton("Choose Reference File")
        self.reference_btn.clicked.connect(self.open_Reference_File)
        folder_ref_btns_layout.addWidget(self.reference_btn)

        self.choose_btn = QPushButton("Choose Folder")
        self.choose_btn.clicked.connect(self.on_choose_folder)
        folder_ref_btns_layout.addWidget(self.choose_btn)
        files_tab_layout.addLayout(folder_ref_btns_layout)

        # Vertical splitter for Code and Documentation lists
        self.files_v_splitter = QSplitter(Qt.Vertical)
        
        # Code List
        self.code_file_list = FileListWidget()
        self._setup_file_list(self.code_file_list)
        code_container = QWidget()
        code_layout = QVBoxLayout(code_container)
        code_layout.setContentsMargins(0,0,0,0)
        code_layout.addWidget(QLabel("Code Files (.fs, .f):"))
        code_layout.addWidget(self.code_file_list)

        # Upload buttons placed directly below the code list
        upload_btns_layout = QHBoxLayout()
        self.upload_sel_btn = QPushButton("Upload Selected")
        self.upload_sel_btn.clicked.connect(self.on_upload_selected)
        upload_btns_layout.addWidget(self.upload_sel_btn)

        self.upload_all_btn = QPushButton("Upload All")
        self.upload_all_btn.clicked.connect(self.on_upload_all)
        upload_btns_layout.addWidget(self.upload_all_btn)
        code_layout.addLayout(upload_btns_layout)

        self.files_v_splitter.addWidget(code_container)

        # Documentation List
        self.doc_file_list = FileListWidget()
        self._setup_file_list(self.doc_file_list)
        doc_container = QWidget()
        doc_layout = QVBoxLayout(doc_container)
        doc_layout.setContentsMargins(0,0,0,0)
        doc_layout.addWidget(QLabel("Documentation & URLs:"))
        doc_layout.addWidget(self.doc_file_list)
        self.files_v_splitter.addWidget(doc_container)

        style = """
            QListWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #E0FFE0, stop:1 #F0FFF0);
                border: 1px solid #C0C0C0;
            }"""
        self.code_file_list.setStyleSheet(style)
        self.doc_file_list.setStyleSheet(style)
        
        files_tab_layout.addWidget(self.files_v_splitter)

        files_tab_widget = QWidget()
        files_tab_widget.setLayout(files_tab_layout)
        self.tab_widget_left.addTab(files_tab_widget, "Files")

        # --- c. Words Tab ---
        words_tab_layout = QVBoxLayout()
        self.definitions_list = QListWidget()
        self.definitions_list.setFont(QFont("Consolas", 10))
        self.definitions_list.setStyleSheet("""
            QListWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFF0E0, stop:1 #FFF8F0);
                border: 1px solid #C0C0C0;
            }""")
        self.definitions_list.itemClicked.connect(self.on_definition_clicked)
        words_tab_layout.addWidget(self.definitions_list)
        words_tab_widget = QWidget()
        words_tab_widget.setLayout(words_tab_layout)
        self.tab_widget_left.addTab(words_tab_widget, "Words")

        # Set tab background colors via stylesheet
        self.tab_widget_left.setStyleSheet("""
            QTabBar::tab {
                color: black;
                padding: 6px 15px;
                min-width: 80px;
                background: #E0FFE0; /* Default (Middle): Files Green */
                border: 1px solid #C0C0C0;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:first { background: #8082F7; } /* Monitor Blue */
            QTabBar::tab:last { background: #FFF0E0; }  /* Words Brown */
            QTabBar::tab:selected { border-bottom: 2px solid #404040; font-weight: bold; }
        """)

        # 2. Middle Section: Tabbed Widget for Scratchpad and Reference
        self.tab_widget = QTabWidget()

        # b. Scratchpad Tab (new plain text widget)
        self.scratchpad_text_edit = QPlainTextEdit()
        self.scratchpad_text_edit.setFont(QFont("Consolas", 10))
        self.scratchpad_text_edit.setStyleSheet("""
            QPlainTextEdit {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #F0FFF0, stop:1 #E0dF80);
                border: 1px solid #C0C0C0;
                padding: 5px;
            }""")

        scratchpad_tab_layout = QVBoxLayout()
        scratchpad_tab_layout.addWidget(self.scratchpad_text_edit)

        scratchpad_tab_widget = QWidget()
        scratchpad_tab_widget.setLayout(scratchpad_tab_layout)
        self.tab_widget.addTab(scratchpad_tab_widget, "Editor Copy")

        # c. Add a second qplaintext to tab control
        self.reference_text_edit = ReferenceTextEdit()
        self.reference_text_edit.setFont(QFont("Consolas", 10))
        self.reference_text_edit.setStyleSheet("""
            QPlainTextEdit {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #F0FFF0, stop:1 #b0FF80);
                border: 1px solid #000000;
                padding: 5px;
            }""")

        reference_tab_layout = QVBoxLayout()
        reference_tab_layout.addWidget(self.reference_text_edit)

        reference_tab_widget = QWidget()
        reference_tab_widget.setLayout(reference_tab_layout)
        self.tab_widget.addTab(reference_tab_widget, "Reference")

        # d. Words Tab (Copy of the words list for the middle section)
        words_tab_layout_2 = QVBoxLayout()
        self.definitions_list_2 = QListWidget()
        self.definitions_list_2.setFont(QFont("Consolas", 10))
        self.definitions_list_2.setStyleSheet("""
            QListWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFF0E0, stop:1 #FFF8F0);
                border: 1px solid #C0C0C0;
            }""")
        self.definitions_list_2.itemClicked.connect(self.on_definition_clicked)
        words_tab_layout_2.addWidget(self.definitions_list_2)
        words_tab_widget_2 = QWidget()
        words_tab_widget_2.setLayout(words_tab_layout_2)
        self.tab_widget.addTab(words_tab_widget_2, "Words")

        # Set tab background colors via stylesheet
        self.tab_widget.setStyleSheet("""
            QTabBar::tab {
                color: black;
                padding: 6px 15px;
                min-width: 120px;
                background: #E0FFE0; /* Default (First/Middle): Editor/Ref Green */
                border: 1px solid #C0C0C0;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:last { background: #FFF0E0; }  /* Words Brown */
            QTabBar::tab:selected { border-bottom: 2px solid #404040; font-weight: bold; }
        """)

        # 3. Right Section: Existing Editor Window
        editor_layout = QVBoxLayout()  # Define the editor_layout here

        self.editor_label = QLabel("File Editor:")
        self.editor_label.setFont(QFont("Arial", 10, QFont.Bold))
        editor_layout.addWidget(self.editor_label)
        self.editor_fullpath = ""

        self.editor_text_edit = QPlainTextEdit()
        self.editor_text_edit.textChanged.connect(self.update_definitions_list)
        self.editor_text_edit.document().modificationChanged.connect(self.on_editor_modified_changed)
        self.editor_text_edit.setFont(QFont("Consolas", 10))
        self.editor_text_edit.setStyleSheet("""
            QPlainTextEdit {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #E6F0FF, stop:1 #FFFFFF);
                border: 1px solid #C0C0C0;
                padding: 5px;
            }""")
        editor_layout.addWidget(self.editor_text_edit)

        editor_buttons_layout = QHBoxLayout()
        self.load_editor_btn = QPushButton("Load File...")
        self.load_editor_btn.clicked.connect(self.on_load_editor_file)
        editor_buttons_layout.addWidget(self.load_editor_btn)

        self.saveas_editor_btn = QPushButton("Save File As...")
        self.saveas_editor_btn.clicked.connect(self.on_saveas_editor_file)
        editor_buttons_layout.addWidget(self.saveas_editor_btn)

        self.save_editor_btn = QPushButton("Save File")
        self.save_editor_btn.clicked.connect(self.on_save_editor_file)
        editor_buttons_layout.addWidget(self.save_editor_btn)

        editor_layout.addLayout(editor_buttons_layout)
        editor_widget = QWidget()
        editor_widget.setLayout(editor_layout)

        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumContentsLength(30)
        self.profile_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.load_profiles()
        # This connection is intentionally placed after load_profiles() to prevent it from firing during initial population
        # Moved this connection AFTER load_profiles() to prevent it from firing during initial population
        self.profile_combo.currentTextChanged.connect(self.on_profile_selection_changed)  # Connect signal
        top.addWidget(QLabel("Profile:"))
        top.addWidget(self.profile_combo)

        self.save_profile_btn = QPushButton("Save Profile...")
        self.save_profile_btn.clicked.connect(self.on_save_profile)
        top.addWidget(self.save_profile_btn)

        # Add widgets to the splitter
        layout.addWidget(mid_splitter)  # Add the splitter to the main layout
        mid_splitter.addWidget(self.tab_widget_left)
        mid_splitter.addWidget(self.tab_widget)  # Add the new tabbed widget as the middle section
        mid_splitter.addWidget(editor_widget)

    def _setup_file_list(self, list_widget):
        """Helper to initialize file list settings and connections."""
        list_widget.files_dropped.connect(self.add_dropped_files)
        list_widget.open_in_reference.connect(self.load_into_reference)
        list_widget.itemClicked.connect(self.load_selected_file)
        list_widget.setSelectionMode(QListWidget.SingleSelection)

    def load_profiles(self):
        # Ensure the profile directory exists before trying to list its contents
        os.makedirs(self.profile_dir, exist_ok=True)

        self.profiles = []

        for f in os.listdir(self.profile_dir):
            if f.endswith(".json"):
                self.profiles.append(f)

        self.profiles.sort()  # Sort profiles alphabetically for consistent display

        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        if self.profiles:
            self.profile_combo.addItems(self.profiles)
        else:
            self.profile_combo.addItem("No profiles found")  # Provide feedback if empty
        self.profile_combo.blockSignals(False)

        # Update the selected_profile_name with the initially displayed item and display its content
        self.selected_profile_name = self.profile_combo.currentText()
        if self.selected_profile_name != "No profiles found":  # Only preview if a real profile exists
            # Instead of loading settings, just display the content on startup
            self._apply_selected_profile_settings(self.selected_profile_name)  # Apply settings on initial load

    def on_profile_selection_changed(self, text):
        """Slot to update the internally stored selected profile name and preview its content.
                This must use the text-editor window, not the monitor window
        """
        # If files in the list changed since loading the last profile, auto-update it before switching
        if self.selected_profile_name and self.selected_profile_name != "No profiles found":
            current_files = self._get_all_file_paths()
            if current_files != self.last_loaded_files:
                self._save_profile_by_name(self.selected_profile_name)
                self.monitor.appendPlainText(f"Auto-updated profile before switch: {self.selected_profile_name}")

        self.selected_profile_name = text
        # print(f"DEBUG: Profile selection changed to: '{self.selected_profile_name}'")
        # Immediately preview the profile content when selection changes
        if self.selected_profile_name != "No profiles found":  # Only preview if a real profile exists
            # Apply the settings first, then preview the content
            self._apply_selected_profile_settings(self.selected_profile_name)

    def _apply_selected_profile_settings(self, profile_name):
        """
        Applies the settings from the specified profile to the UI controls and serial manager.
        This is the core logic that updates port, baud, pacing, and folder.
        """
        profile_name = self.selected_profile_name  # Use the stored selected name
        # print(f"DEBUG: Applying settings from profile: '{profile_name}'")

        # Prevent attempting to load the "No profiles found" placeholder
        if profile_name == "No profiles found" or not profile_name:  # Also check if it's empty
            self.monitor.appendPlainText("Cannot load 'No profiles found' placeholder.")
            return

        # Disconnect and clear monitor before applying new profile settings
        if self.serial.ser and self.serial.ser.is_open:
            self.serial.close()
            self.connect_btn.setText("Connect")
            self.monitor.clear()
            self.monitor.appendPlainText("Disconnected due to profile load.")

        # --- END NEW SECTION ---
        profile_path = os.path.join(self.profile_dir, profile_name)

        # Apply settings with validation
        try:
            with open(profile_path, "r") as f:
                data = json.load(f)
        except FileNotFoundError:
            self.monitor.appendPlainText(f"Error: Profile file not found: {profile_path}")
            return
        except json.JSONDecodeError as e:
            self.monitor.appendPlainText(f"Error: Malformed JSON in profile '{profile_name}': {e}")
            self.monitor.appendPlainText("Please check the profile file for syntax errors or if it's empty.")
            return
        except Exception as e:
            self.monitor.appendPlainText(f"An unexpected error occurred while reading profile '{profile_name}': {e}")
            return

        # Apply settings with validation
        try:
            # --- Update Port ComboBox ---
            profile_port = data.get("port", "")
            if profile_port and self.port_combo.findText(profile_port) == -1:  # If port not in current list
                self.port_combo.addItem(profile_port)  # Add it temporarily
            self.port_combo.setCurrentText(profile_port)

            # --- Update Baud ComboBox ---
            profile_baud = str(data.get("baud", "115200"))  # Ensure baud is string for setcurrentText
            if self.baud_combo.findText(
                    profile_baud) == -1:  # If baud not in current list (shouldn't happen if hardcoded)
                self.baud_combo.addItem(profile_baud)  # Add it (safety, though hardcoded values imply it exists)
            self.baud_combo.setCurrentText(profile_baud)

            # --- Update Data Bits ComboBox ---
            profile_data_bits = str(data.get("data_bits", "8"))
            if self.data_bits_combo.findText(profile_data_bits) == -1:
                # Add if not present, though for common values it should be
                self.data_bits_combo.addItem(profile_data_bits)
            self.data_bits_combo.setCurrentText(profile_data_bits)

            # --- Update Parity ComboBox ---
            profile_parity = data.get("parity", "None")
            if self.parity_combo.findText(profile_parity) == -1:
                # Add if not present, though for common values it should be
                self.parity_combo.addItem(profile_parity)
            self.parity_combo.setCurrentText(profile_parity)

            # --- Update Stop Bits ComboBox ---
            profile_stop_bits = str(data.get("stop_bits", "1"))
            # Special handling for float 1.5 if stored as float in JSON
            if profile_stop_bits == "1.5" and self.stop_bits_combo.findText("1.5") == -1:
                self.stop_bits_combo.addItem("1.5")  # Ensure float is handled as string
            elif self.stop_bits_combo.findText(profile_stop_bits) == -1:
                # Add if not present, though for common values it should be
                self.stop_bits_combo.addItem(profile_stop_bits)

            # --- Get the number of chars to ignore in the serial output line
            # usually an ord(6) spades
            self.ignoreChars = int(data.get("ignore_chars", 0))  # Default to 0 if not specified

            # Ensure it's set as string for setCurrentText
            try:
                # Check if it's a number that might be like 1.0 but stored as 1
                if float(profile_stop_bits) == 1.0: profile_stop_bits = "1"
            except ValueError:
                pass  # Not a number, just use as is

            self.stop_bits_combo.setCurrentText(profile_stop_bits)

            # --- Update Pacing Slider ---
            pacing_value = data.get("pacing", 10)
            try:
                pacing_value = int(pacing_value)
            except (ValueError, TypeError):
                pacing_value = 10  # Default if conversion fails
            if isinstance(pacing_value, int) and 0 <= pacing_value <= 100:
                self.pacing_slider.setValue(pacing_value)
            else:
                self.monitor.appendPlainText(
                    f"Warning: Invalid pacing value '{pacing_value}' in profile. Using default 10.")
                self.pacing_slider.setValue(10)

            # Store groups for future use
            self.module_groups = data.get("groups", {})

            # --- Update File List (Project Repository behavior) ---
            self.code_file_list.clear()
            self.doc_file_list.clear()
            project_files = data.get("files", [])
            for path in project_files:
                # add_file_path handles path validation and distribution
                self.add_file_path(path)

            # Track current files to detect future changes
            self.last_loaded_files = self._get_all_file_paths()

            # --- Load Editor and Reference Files ---
            editor_path = data.get("editor_file", "")
            if editor_path and os.path.exists(editor_path):
                try:
                    with open(editor_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    self.editor_text_edit.setPlainText(content)
                    self.scratchpad_text_edit.setPlainText(content)
                    self.editor_fullpath = editor_path
                    self.setWindowTitle(editor_path)
                except Exception as e:
                    self.monitor.appendPlainText(f"Error loading saved editor file: {e}")

            ref_path = data.get("reference_file", "")
            if ref_path and os.path.exists(ref_path):
                try:
                    with open(ref_path, "r", encoding="utf-8") as f:
                        self.reference_text_edit.setPlainText(f.read())
                    self.reference_fullpath = ref_path
                except Exception as e:
                    self.monitor.appendPlainText(f"Error loading saved reference file: {e}")

            self.monitor.appendPlainText(f"Successfully applied settings from profile: {profile_name}")
        except Exception as e:
            self.monitor.appendPlainText(f"Error applying profile settings for '{profile_name}': {e}")

    def _get_all_file_paths(self):
        """Gathers paths from both code and documentation lists."""
        paths = []
        for i in range(self.code_file_list.count()):
            paths.append(self.code_file_list.item(i).data(Qt.UserRole))
        for i in range(self.doc_file_list.count()):
            paths.append(self.doc_file_list.item(i).data(Qt.UserRole))
        return paths

    def _save_profile_by_name(self, profile_name):
        """Internal helper to save current settings and the file list to a JSON file."""
        actual_save_path = os.path.join(self.profile_dir, profile_name)
        
        file_paths = self._get_all_file_paths()

        try:
            baud_text = self.baud_combo.currentText()
            baud_val = int(baud_text) if baud_text.isdigit() else 115200
        except Exception:
            baud_val = 115200

        data = {
            "port": self.port_combo.currentText(),
            "baud": baud_val,
            "data_bits": int(self.data_bits_combo.currentText()),
            "parity": self.parity_combo.currentText(),
            "stop_bits": float(self.stop_bits_combo.currentText()),
            "pacing": self.pacing_slider.value(),
            "ignore_chars": getattr(self, "ignoreChars", 0),
            "files": file_paths,
            "editor_file": self.editor_fullpath,
            "reference_file": self.reference_fullpath,
            "groups": getattr(self, "module_groups", {})
        }

        with open(actual_save_path, "w") as f:
            json.dump(data, f, indent=4)
        
        self.last_loaded_files = list(file_paths)

    def on_save_profile(self):
        """Saves current settings and the current file list into a project JSON file."""
        suggested_path = os.path.join(self.profile_dir, "new_project.json")
        full_user_selected_path, ok = QFileDialog.getSaveFileName(
            self, "Save Project/Profile As", suggested_path, "JSON Files (*.json)"
        )
        if not ok or not full_user_selected_path:
            return

        filename = os.path.basename(full_user_selected_path)
        self._save_profile_by_name(filename)

        self.monitor.appendPlainText(f"Saved project profile: {filename}")
        self.load_profiles()
        self.profile_combo.setCurrentText(filename)

    def on_new_profile(self):
        """Saves current profile if file list changed, then clears workspace."""
        if self.selected_profile_name and self.selected_profile_name != "No profiles found":
            current_files = self._get_all_file_paths()
            if current_files != self.last_loaded_files:
                self._save_profile_by_name(self.selected_profile_name)
                self.monitor.appendPlainText(f"Auto-saved profile: {self.selected_profile_name}")

        # Clear UI components
        self.code_file_list.clear()
        self.doc_file_list.clear()
        self.editor_text_edit.clear()
        self.scratchpad_text_edit.clear()
        self.reference_text_edit.clear()

        # Reset internal state
        self.editor_fullpath = ""
        self.reference_fullpath = ""
        self.last_loaded_files = []
        self.selected_profile_name = None

        # Reset profile combo and title without triggering signals
        self.profile_combo.blockSignals(True)
        self.profile_combo.setCurrentIndex(-1)
        self.profile_combo.blockSignals(False)
        self.setWindowTitle("PyQt5 Forth Uploader for zeptoforth")
        self.monitor.appendPlainText("Workspace cleared for new profile.")

    def preview_profile_content(self, profile_name):
        """
        Reads a profile file and displays its JSON content in the text-editor window.
        """
        profile_path = os.path.join(self.profile_dir, profile_name)
        try:
            with open(profile_path, "r") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            # Errors should ideally be caught by _apply_selected_profile_settings first,
            # but good to have fallback for preview.
            self.monitor.appendPlainText(f"Error previewing profile '{profile_name}': {e}")
            return

        # Show the profile lines to monitor, pretty-printed
        self.editor_text_edit.clear()
        # self.editor_text_edit.appendPlainText(f"--- Previewing Profile: {profile_name} ---")
        json_string = json.dumps(data, indent=4)
        self.editor_text_edit.appendPlainText(json_string)
        # self.editor_text_edit.appendPlainText(f"--- End Preview of {profile_name} ---")

    # --- Serial callbacks ---
    def on_serial_rx(self, text):
        # Debugging: print all ordinal numbers in the received text
        ord_numbers = [ord(char) for char in text]
        print(f"\nReceived ords: {ord_numbers}")

        self.monitor.appendPlainText(text)

        # --- UI actions ---

    def refresh_ports(self):
        # ports = [p.device for p in serial.tools.list_ports.comports()]
        # self.port_combo.clear()
        # self.port_combo.addItems(ports)

        # Full list COM1–COM25
        all_ports = [f"COM{i}" for i in range(1, 26)]

        # Detect actual connected ports
        detected = {p.device for p in serial.tools.list_ports.comports()}

        self.port_combo.clear()

        # Add all ports, marking detected ones
        for port in all_ports:
            if port in detected:
                self.port_combo.addItem(port)
            else:
                self.port_combo.addItem(f"{port}")  #  (not present)")

    def on_connect(self):
        if self.connect_btn.text() == "Connect":
            try:
                port = self.port_combo.currentText()
                baud = int(self.baud_combo.currentText())
                data_bits = int(self.data_bits_combo.currentText())
                parity_str = self.parity_combo.currentText()
                stop_bits_str = self.stop_bits_combo.currentText()

                # Convert stop_bits_str to float correctly
                stop_bits_float = float(stop_bits_str)

                self.serial.open(
                    port=port,
                    baud=baud,
                    data_bits=data_bits,
                    parity_str=parity_str,
                    stop_bits_float=stop_bits_float
                )
                self.monitor.appendPlainText(
                    f"Connected to {port} @ {baud} bps, {data_bits} data bits, {parity_str} parity, {stop_bits_str} stop bits.")
                self.connect_btn.setText("Disconnect")
            except Exception as e:
                self.monitor.appendPlainText(f"Error connecting: {e}")
                if self.serial.ser and self.serial.ser.is_open:
                    self.serial.close()
                self.connect_btn.setText("Connect")
        else:
            self.serial.close()
            self.monitor.clear()
            self.monitor.appendPlainText("Disconnected.")
            self.connect_btn.setText("Connect")

        self.tab_widget_left.setCurrentIndex(0)
        self.monitor.setFocus()

    def on_pacing_change(self, value):
        self.serial.set_pacing(value)

    def on_choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose Folder", self.current_folder)
        if folder:
            self.current_folder = folder
            self.load_files()

    def add_file_path(self, path):
        """Adds a file to the list widget, storing the full path in UserRole."""
        lower_path = path.lower()
        
        # Avoid duplicate paths
        if path in self._get_all_file_paths():
            return

        # Determine which list to use
        is_forth = lower_path.endswith((".fs", ".f")) and not lower_path.startswith("http")
        target_list = self.code_file_list if is_forth else self.doc_file_list

        if lower_path.startswith(("http://", "https://")):
            name = path
        else:
            if not os.path.exists(path):
                return
            name = os.path.basename(path)
            
        item = QListWidgetItem(name)
        item.setData(Qt.UserRole, path)
        item.setToolTip(path)  # Show full path on hover
        target_list.addItem(item)

    def add_dropped_files(self, paths):
        """Processes files dropped onto the list widget."""
        for path in paths:
            lp = path.lower()
            if lp.startswith(("http://", "https://")):
                self.add_file_path(path)
            elif os.path.isfile(path) and lp.endswith((".fs", ".f", ".txt", ".docx", ".pdf", ".html", ".epub")):
                self.add_file_path(path)

    def load_files(self):
        if os.path.isdir(self.current_folder):
            for f in os.listdir(self.current_folder):
                if f.lower().endswith((".fs", ".f", ".txt", ".docx", ".pdf", ".html", ".epub")):
                    self.add_file_path(os.path.join(self.current_folder, f))

    def on_upload_selected(self):
        progress = QProgressDialog("Please wait, uploading...", None, 0, 0, self)
        progress.setWindowTitle("Uploading")
        progress.setWindowModality(Qt.WindowModal)
        progress.show()
        QApplication.processEvents()

        self.setCursor(Qt.WaitCursor)
        self.upload_all_btn.setEnabled(False)
        self.upload_sel_btn.setEnabled(False)
        
        # Collect selected items from both lists
        selected_items = self.code_file_list.selectedItems() + self.doc_file_list.selectedItems()
        
        for item in selected_items:
            path = item.data(Qt.UserRole)
            # Only upload Forth source files
            if path and path.lower().endswith((".fs", ".f")) and not path.lower().startswith("http"):
                self.serial.upload_file(path)
                QApplication.processEvents()

        self.setCursor(Qt.ArrowCursor)
        self.upload_all_btn.setEnabled(True)
        self.upload_sel_btn.setEnabled(True)
        progress.close()
        self.tab_widget_left.setCurrentIndex(0)
        self.monitor.setFocus()

    def on_monitor_return_pressed(self, line_to_send):
        ord_numbers = [ord(char) for char in line_to_send]
        print(f"\nOriginal ords: {ord_numbers}")

        """Slot to handle the Return key press in the monitor and send the line."""
        print(f"Sending {line_to_send}")  # Debug print to verify the line being sent
        self.serial.send_line(line_to_send)

    def on_upload_all(self):
        progress = QProgressDialog("Please wait, uploading all files...", None, 0, 0, self)
        progress.setWindowTitle("Uploading")
        progress.setWindowModality(Qt.WindowModal)
        progress.show()
        QApplication.processEvents()

        self.setCursor(Qt.WaitCursor)
        self.upload_all_btn.setEnabled(False)
        self.upload_sel_btn.setEnabled(False)
        
        # "Upload All" typically refers to the code files
        for i in range(self.code_file_list.count()):
            item = self.code_file_list.item(i)
            path = item.data(Qt.UserRole)
            if path and path.lower().endswith((".fs", ".f")) and not path.lower().startswith("http"):
                self.serial.upload_file(path)
                QApplication.processEvents()

        self.setCursor(Qt.ArrowCursor)
        self.upload_all_btn.setEnabled(True)
        self.upload_sel_btn.setEnabled(True)
        progress.close()
        self.tab_widget_left.setCurrentIndex(0)
        self.monitor.setFocus()

    def on_load_editor_file(self):
        """Load a file into the text editor."""
        path, _ = QFileDialog.getOpenFileName(self, "Open File", "", "All Files (*)")
        if path:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
            self.editor_text_edit.clear()
            self.editor_text_edit.setPlainText(text)
            # and into scratchpad
            self.scratchpad_text_edit.clear()
            self.scratchpad_text_edit.setPlainText(text)

            self.setWindowTitle(path)
            self.editor_fullpath = path

    def load_selected_file(self, item):
        path = item.data(Qt.UserRole)
        if not path:
            return

        lower_path = path.lower()
        # If it's a URL or a binary document, open with system default
        # Added .txt, .html, and .epub to external open list per user request
        if lower_path.startswith(("http://", "https://")) or lower_path.endswith((".docx", ".pdf", ".txt", ".html", ".epub")):
            QDesktopServices.openUrl(QUrl(path) if lower_path.startswith("http") else QUrl.fromLocalFile(path))
            return

        try:
            if path and os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    text = f.read()
                self.editor_text_edit.clear()
                self.editor_text_edit.setPlainText(text)
                # and also into scratchpad
                self.scratchpad_text_edit.clear()
                self.scratchpad_text_edit.setPlainText(text)

                # self.editor_label.setText(path)
                self.setWindowTitle(path)
                self.editor_fullpath = path
        except Exception as e:
            print("Error loading file:", e)

    def on_saveas_editor_file(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save File", "", "AllFiles (*)")
        try:
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self.editor_text_edit.toPlainText())
                # Update state so subsequent 'Save' operations target this new path
                self.editor_fullpath = path
                self.setWindowTitle(path)
                self.editor_text_edit.document().setModified(False)
                # if a json file re-load profiles
                if os.path.splitext(path)[1].lower() == ".json":
                    self.load_profiles()
        except Exception as e:
            print("Error saving editor file as...", e)

    def on_save_editor_file(self):
        if not self.editor_text_edit.document().isModified():
            QMessageBox.critical(self, "Not saving file", "Nothing has changed")
            return
        # save to same as loaded
        if self.editor_fullpath == "":
            QMessageBox.critical(self, "Error saving file", "This was loaded from profile combobox")
        else:
            path = self.editor_fullpath
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self.editor_text_edit.toPlainText())
                
                # Sync the scratchpad and reset modification state
                text = self.editor_text_edit.toPlainText()
                self.scratchpad_text_edit.setPlainText(text)
                self.editor_text_edit.document().setModified(False)
                self.setWindowTitle(path)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not save file: {e}")

    def open_Reference_File(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Reference File",
            "",
            "All Files (*)"
        )

        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.reference_text_edit.setPlainText(f.read())
            self.reference_fullpath = path
        except Exception as e:
            print("Error loading reference file:", e)

    def on_editor_modified_changed(self, modified):
        if modified:
            # Light yellow background when modified
            self.editor_text_edit.setStyleSheet("""
            QPlainTextEdit {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #7F70F6, stop:1 #FFFFFF);
                border: 1px solid #000000;
                padding: 5px;
            }""")
            self.save_editor_btn.setStyleSheet("background-color: yellow; color: black;")

            # self.editor_text_edit.setStyleSheet("QPlainTextEdit { background-color: #fff8c4; }")
        else:
            # Normal background when clean
            self.editor_text_edit.setStyleSheet("""
            QPlainTextEdit {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #E6F0FF, stop:1 #FFFFFF);
                border: 1px solid #C0C0C0;
                padding: 5px;
            }""")
            self.save_editor_btn.setStyleSheet("background-color: #a15a59; color: white;")

            # self.editor_text_edit.setStyleSheet("QPlainTextEdit { background-color: white; }")

    def update_definitions_list(self):
        """Update the list of Forth definitions (lines starting with ':') from the editor."""
        self.definitions_list.clear()
        self.definitions_list_2.clear()
        text = self.editor_text_edit.toPlainText()
        for i, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith(":"):
                # Format with 3-character wide line number prefix
                display_text = f"{i:3} {stripped}"
                self.definitions_list.addItem(display_text)
                self.definitions_list_2.addItem(display_text)

    def on_definition_clicked(self, item):
        """Jump to the corresponding line in the editor when a word is clicked."""
        try:
            # Extract the line number from the 3-character prefix
            line_num = int(item.text()[:3].strip())
            block = self.editor_text_edit.document().findBlockByLineNumber(line_num - 1)
            cursor = self.editor_text_edit.textCursor()
            cursor.setPosition(block.position())
            self.editor_text_edit.setTextCursor(cursor)
            self.editor_text_edit.setFocus()
        except Exception:
            pass

    def load_into_reference(self, path):
        """Loads a file into the reference text edit and switches to its tab."""
        try:
            if path and os.path.exists(path) and path.lower().endswith((".fs", ".f", ".txt")):
                with open(path, "r", encoding="utf-8") as f:
                    text = f.read()
                self.reference_text_edit.setPlainText(text)
                self.reference_fullpath = path
                self.tab_widget.setCurrentIndex(1)  # Switch to Reference tab (index 1)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not load reference: {e}")
