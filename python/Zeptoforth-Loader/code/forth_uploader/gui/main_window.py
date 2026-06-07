import os
import json

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget,
    QFileDialog, QComboBox, QLabel, QSlider, QPlainTextEdit
)
from PyQt5.QtGui import QFont
from .forth_monitor_text_edit import ForthMonitorTextEdit
from PyQt5.QtCore import Qt
from serial_manager import SerialManager
import serial.tools.list_ports

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQt5 Forth Uploader for zeptoforth")
        self.resize(1400, 900)
        self.setStyleSheet("background-color: #A0A0A0;") # Medium grey background for the main window
        
        # Determine the base directory for profiles relative to the 'forth_uploader' package root
        script_dir = os.path.dirname(os.path.abspath(__file__))
        forth_uploader_root = os.path.dirname(script_dir) # This is .../forth_uploader
        self.profile_dir = os.path.join(forth_uploader_root, "profiles")
        os.makedirs(self.profile_dir, exist_ok=True)

        self.serial = SerialManager()
        self.serial.received.connect(self.on_serial_rx)

        self.current_folder = os.getcwd()
        self.files = []
        self.selected_profile_name = None # To store the actively selected profile

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
        self.data_bits_combo.addItems(["8", "7", "6", "5"]) # Common data bits, 8 is most common
        self.data_bits_combo.setCurrentText("8") # Default to 8
        top.addWidget(self.data_bits_combo)

        top.addWidget(QLabel("Parity:"))
        self.parity_combo = QComboBox()
        self.parity_combo.addItems(["None", "Even", "Odd", "Mark", "Space"])
        self.parity_combo.setCurrentText("None") # Default to None
        top.addWidget(self.parity_combo)

        top.addWidget(QLabel("Stop Bits:"))
        self.stop_bits_combo = QComboBox()
        self.stop_bits_combo.addItems(["1", "1.5", "2"])
        self.stop_bits_combo.setCurrentText("1") # Default to 1
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
        mid = QHBoxLayout()
        layout.addLayout(mid)

        # File list
        left = QVBoxLayout()
        mid.addLayout(left)

        self.choose_btn = QPushButton("Choose Folder")
        self.choose_btn.clicked.connect(self.on_choose_folder)
        left.addWidget(self.choose_btn)

        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QListWidget.MultiSelection)
        # Apply graduated fade color to the file_list QListWidget
        # Using a subtle linear gradient from a light grey to an off-white
        # Updated to a faded graded light green color
        self.file_list.setStyleSheet("""
            QListWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #E0FFE0, stop:1 #F0FFF0);
                border: 1px solid #C0C0C0;
            }""")
        left.addWidget(self.file_list)

        self.upload_sel_btn = QPushButton("Upload Selected")
        self.upload_sel_btn.clicked.connect(self.on_upload_selected)
        left.addWidget(self.upload_sel_btn)

        self.upload_all_btn = QPushButton("Upload All")
        self.upload_all_btn.clicked.connect(self.on_upload_all)
        left.addWidget(self.upload_all_btn)

        # Serial monitor
        right = QVBoxLayout()
        mid.addLayout(right)

        # Use the custom interactive monitor
        self.monitor = ForthMonitorTextEdit()
        self.monitor.return_pressed.connect(self.on_monitor_return_pressed)
        
        # Set the font to Courier for the monitor
        font = QFont("Arial")  # Courier")
        self.monitor.setFont(font)
        # Apply graduated fade color to the monitor QPlainTextEdit
        # Using a subtle linear gradient from a light blue to an off-white blue
        self.monitor.setStyleSheet("""
            QPlainTextEdit {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #8082F7, stop:1 #F0FAFF);
                border: 1px solid #C0C0C0;
            }""")
        right.addWidget(self.monitor)

        self.clear_btn = QPushButton("Clear Monitor")
        self.clear_btn.clicked.connect(lambda: self.monitor.clear())
        right.addWidget(self.clear_btn)

        self.profile_combo = QComboBox()
        self.load_profiles()
        # This connection is intentionally placed after load_profiles() to prevent it from firing during initial population
        # Moved this connection AFTER load_profiles() to prevent it from firing during initial population
        self.profile_combo.currentTextChanged.connect(self.on_profile_selection_changed) # Connect signal
        top.addWidget(QLabel("Profile:"))
        top.addWidget(self.profile_combo)

        self.load_profile_btn = QPushButton("Load")
        self.load_profile_btn.clicked.connect(self.on_load_profile)
        top.addWidget(self.load_profile_btn)

        self.save_profile_btn = QPushButton("Save As…")
        self.save_profile_btn.clicked.connect(self.on_save_profile)
        top.addWidget(self.save_profile_btn)

    def load_profiles(self):
        # Ensure the profile directory exists before trying to list its contents
        os.makedirs(self.profile_dir, exist_ok=True)
        
        self.profiles = []

        for f in os.listdir(self.profile_dir):
            if f.endswith(".json"):
                self.profiles.append(f)
        
        self.profiles.sort() # Sort profiles alphabetically for consistent display

        self.profile_combo.clear()
        if self.profiles:
            self.profile_combo.addItems(self.profiles)
        else:
            self.profile_combo.addItem("No profiles found") # Provide feedback if empty
        
        # Update the selected_profile_name with the initially displayed item and display its content
        self.selected_profile_name = self.profile_combo.currentText()
        if self.selected_profile_name != "No profiles found": # Only preview if a real profile exists
            # Instead of loading settings, just display the content on startup
            self._apply_selected_profile_settings(self.selected_profile_name) # Apply settings on initial load

    def on_profile_selection_changed(self, text):
        """Slot to update the internally stored selected profile name and preview its content."""
        self.selected_profile_name = text
        print(f"DEBUG: Profile selection changed to: '{self.selected_profile_name}'")
        # Immediately preview the profile content when selection changes
        if self.selected_profile_name != "No profiles found": # Only preview if a real profile exists
            # Apply the settings first, then preview the content
            self._apply_selected_profile_settings(self.selected_profile_name)
            self.preview_profile_content(self.selected_profile_name)

    def _apply_selected_profile_settings(self, profile_name):
        """
        Applies the settings from the specified profile to the UI controls and serial manager.
        This is the core logic that updates port, baud, pacing, and folder.
        """
        profile_name = self.selected_profile_name # Use the stored selected name
        print(f"DEBUG: Applying settings from profile: '{profile_name}'")

        # Prevent attempting to load the "No profiles found" placeholder
        if profile_name == "No profiles found" or not profile_name: # Also check if it's empty
            self.monitor.appendPlainText("Cannot load 'No profiles found' placeholder.")
            return
        
        # Disconnect and clear monitor before applying new profile settings
        if self.serial.ser and self.serial.ser.is_open:
            self.serial.close()
            self.connect_btn.setText("Connect")
            self.monitor.appendPlainText("Disconnected due to profile load.")
        self.monitor.clear()
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
            self.current_folder = data.get("folder", self.current_folder)
            # Ensure folder exists before attempting to load files
            if not os.path.isdir(self.current_folder):
                self.monitor.appendPlainText(f"Warning: Profile folder '{self.current_folder}' not found. Defaulting to current.")
                self.current_folder = os.getcwd()
            self.load_files() # Load files from the specified folder

            # --- Update Port ComboBox ---
            profile_port = data.get("port", "")
            if profile_port and self.port_combo.findText(profile_port) == -1: # If port not in current list
                self.port_combo.addItem(profile_port) # Add it temporarily
            self.port_combo.setCurrentText(profile_port)

            # --- Update Baud ComboBox ---
            profile_baud = str(data.get("baud", "115200")) # Ensure baud is string for setcurrentText
            if self.baud_combo.findText(profile_baud) == -1: # If baud not in current list (shouldn't happen if hardcoded)
                self.baud_combo.addItem(profile_baud) # Add it (safety, though hardcoded values imply it exists)
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
                 self.stop_bits_combo.addItem("1.5") # Ensure float is handled as string
            elif self.stop_bits_combo.findText(profile_stop_bits) == -1:
                # Add if not present, though for common values it should be
                self.stop_bits_combo.addItem(profile_stop_bits)

            # Ensure it's set as string for setCurrentText
            try:
                # Check if it's a number that might be like 1.0 but stored as 1
                if float(profile_stop_bits) == 1.0: profile_stop_bits = "1"
            except ValueError:
                pass # Not a number, just use as is

            self.stop_bits_combo.setCurrentText(profile_stop_bits)


            # --- Update Pacing Slider ---
            pacing_value = data.get("pacing", 10) 
            try:
                pacing_value = int(pacing_value)
            except (ValueError, TypeError):
                pacing_value = 10 # Default if conversion fails
            if isinstance(pacing_value, int) and 0 <= pacing_value <= 100:
                self.pacing_slider.setValue(pacing_value)
            else:
                self.monitor.appendPlainText(f"Warning: Invalid pacing value '{pacing_value}' in profile. Using default 10.")
                self.pacing_slider.setValue(10)

            # Store groups for future use
            self.module_groups = data.get("groups", {})

            self.monitor.appendPlainText(f"Successfully applied settings from profile: {profile_name}")
        except Exception as e:
            self.monitor.appendPlainText(f"Error applying profile settings for '{profile_name}': {e}")

    def on_save_profile(self):
        # Now that the core logic is in _apply_selected_profile_settings,
        # this method just needs to call that helper.
        self.monitor.appendPlainText(f"Applying settings from profile: {profile_name}")

    def preview_profile_content(self, profile_name):
        """
        Reads a profile file and displays its JSON content in the monitor.
        This method is now solely for display/preview purposes.
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
        self.monitor.appendPlainText(f"--- Previewing Profile: {profile_name} ---")
        json_string = json.dumps(data, indent=4)
        self.monitor.appendPlainText(json_string)
        self.monitor.appendPlainText(f"--- End Preview of {profile_name} ---")

    def on_load_profile(self):
        """Load button now just triggers the application of the currently selected profile."""
        self._apply_selected_profile_settings(self.selected_profile_name)

        # Guide the user to the 'profiles' directory by default.
        # However, to ensure profiles are always saved IN this directory,
        # we'll extract just the filename from their input.
        suggested_path = os.path.join(self.profile_dir, "new_profile.json")
        full_user_selected_path, ok = QFileDialog.getSaveFileName(
            self, "Save Profile As", suggested_path, "JSON Files (*.json)"
        )
        if not ok or not full_user_selected_path:
            return

                
        # Extract only the base filename to ensure it's saved within our 'profiles' directory
        filename = os.path.basename(full_user_selected_path)
        actual_save_path = os.path.join(self.profile_dir, filename)

        data = {
            "folder": self.current_folder,
            "port": self.port_combo.currentText(),
            "baud": int(self.baud_combo.currentText()),
            "data_bits": int(self.data_bits_combo.currentText()),
            "parity": self.parity_combo.currentText(),
            "stop_bits": float(self.stop_bits_combo.currentText()), # Store as float for 1.5
            "pacing": self.pacing_slider.value(),
            "groups": getattr(self, "module_groups", {})
        }

        with open(actual_save_path, "w") as f:        
            json.dump(data, f, indent=4)

        self.monitor.appendPlainText(f"Saved profile: {actual_save_path}")
        self.load_profiles()



    # --- Serial callbacks ---
    def on_serial_rx(self, text):
        self.monitor.appendPlainText(text)

    # --- UI actions ---
    def refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_combo.clear()
        self.port_combo.addItems(ports)

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
                self.monitor.appendPlainText(f"Connected to {port} @ {baud} bps, {data_bits} data bits, {parity_str} parity, {stop_bits_str} stop bits.")
                self.connect_btn.setText("Disconnect")
            except Exception as e:
                self.monitor.appendPlainText(f"Error connecting: {e}")
                if self.serial.ser and self.serial.ser.is_open:
                    self.serial.close()
                self.connect_btn.setText("Connect")
        else:
            self.serial.close()
            self.monitor.appendPlainText("Disconnected.")
            self.connect_btn.setText("Connect")


    def on_pacing_change(self, value):
        self.serial.set_pacing(value)

    def on_choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose Folder", self.current_folder)
        if folder:
            self.current_folder = folder
            self.load_files()

    def load_files(self):
        self.files = [f for f in os.listdir(self.current_folder) if f.lower().endswith(".fs")]
        self.file_list.clear()
        self.file_list.addItems(self.files)

    def on_upload_selected(self):
        for item in self.file_list.selectedItems():
            path = os.path.join(self.current_folder, item.text())
            self.serial.upload_file(path)
    
    def on_monitor_return_pressed(self, line_to_send):
        """Slot to handle the Return key press in the monitor and send the line."""
        self.serial.send_line(line_to_send)

    def on_upload_all(self):
        for f in self.files:
            path = os.path.join(self.current_folder, f)
            self.serial.upload_file(path)
