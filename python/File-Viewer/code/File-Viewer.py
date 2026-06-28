import os
import sys

from PyQt5.QtCore import QDir, QModelIndex, Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QFileDialog,
    QFileSystemModel,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSplitter,
    QTreeView,
    QVBoxLayout,
    QWidget,
    QTextEdit,
    QComboBox,
)


class ZoomableTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont("Courier", 11))
        self.setStyleSheet(
            "background-color: #0d1117;"
            "color: #c9d1d9;"
            "selection-background-color: #3b4174;"
            "selection-color: #ffffff;"
            "border: none;"
        )

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            angle = event.angleDelta().y()
            if angle > 0:
                self.zoomIn(1)
            elif angle < 0:
                self.zoomOut(1)
        else:
            super().wheelEvent(event)


class FileViewer(QMainWindow):
    allowed_extensions = [
        ".txt",
        ".bat",
        ".py",
        ".h",
        ".cpp",
        ".zf",
        ".f",
        ".sf",
        ".fth",
        ".ino",
    ]
    name_filters = [f"*{ext}" for ext in allowed_extensions]

    def __init__(self, root_path=None):
        super().__init__()
        self.setWindowTitle("PyQt5 File Viewer")
        self.resize(1100, 720)

        self.root_path = root_path or os.getcwd()
        self._create_actions()
        self._create_widgets()
        self._create_layout()
        self._create_shortcuts()

    def _create_shortcuts(self):
        save_action = QAction("Save", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_current_file)
        self.addAction(save_action)

    def _create_actions(self):
        self.go_up_button = QPushButton("Up")
        self.go_up_button.clicked.connect(self.go_up_directory)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_file_tree)
        self.open_root_button = QPushButton("Change Root Folder")
        self.open_root_button.clicked.connect(self.choose_root_directory)

    def _create_widgets(self):
        self.model = QFileSystemModel(self)
        self.model.setRootPath(self.root_path)
        self.model.setNameFilters(self.name_filters)
        self.model.setNameFilterDisables(False)
        self.model.setFilter(QDir.AllDirs | QDir.Files | QDir.NoDotAndDotDot)

        self.tree = QTreeView(self)
        self.tree.setModel(self.model)
        self.tree.setRootIndex(self.model.index(self.root_path))
        self.tree.setHeaderHidden(False)
        self.tree.doubleClicked.connect(self.open_selected_file)
        self.tree.setAnimated(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSortingEnabled(True)
        self.tree.sortByColumn(0, Qt.AscendingOrder)
        self.tree.setColumnHidden(1, True)
        self.tree.setColumnHidden(2, True)
        self.tree.setColumnHidden(3, True)

        self.target_combo = QComboBox(self)
        self.target_combo.addItems(["Left editor", "Right editor"])
        self.open_button = QPushButton("Open Selected File")
        self.open_button.clicked.connect(self.open_selected_file)
        self.save_button = QPushButton("Save File")
        self.save_button.clicked.connect(self.save_current_file)
        self.status_label = QLabel("")

        self.left_file_path = None
        self.right_file_path = None

        self.top_editor = ZoomableTextEdit(self)
        self.top_editor.setReadOnly(False)
        self.top_editor.setPlaceholderText("Left editor: file contents appear here.")

        self.bottom_editor = ZoomableTextEdit(self)
        self.bottom_editor.setReadOnly(False)
        self.bottom_editor.setPlaceholderText("Right editor: file contents appear here.")

    def _create_layout(self):
        control_layout = QHBoxLayout()
        control_layout.addWidget(QLabel("Open target:"))
        control_layout.addWidget(self.target_combo)
        control_layout.addWidget(self.go_up_button)
        control_layout.addWidget(self.refresh_button)
        control_layout.addWidget(self.open_button)
        control_layout.addWidget(self.save_button)
        control_layout.addStretch(1)
        control_layout.addWidget(self.status_label)
        control_layout.addWidget(self.open_root_button)

        top_group = QGroupBox("Left Editor")
        top_layout = QVBoxLayout(top_group)
        top_layout.addWidget(self.top_editor)

        bottom_group = QGroupBox("Right Editor")
        bottom_layout = QVBoxLayout(bottom_group)
        bottom_layout.addWidget(self.bottom_editor)

        editors_splitter = QSplitter(Qt.Horizontal)
        editors_splitter.addWidget(top_group)
        editors_splitter.addWidget(bottom_group)
        editors_splitter.setStretchFactor(0, 1)
        editors_splitter.setStretchFactor(1, 1)

        right_widget = QWidget(self)
        right_layout = QVBoxLayout(right_widget)
        right_layout.addLayout(control_layout)
        right_layout.addWidget(editors_splitter)
        right_layout.setContentsMargins(0, 0, 0, 0)

        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.addWidget(self.tree)
        main_splitter.addWidget(right_widget)
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setSizes([320, 760])

        container = QWidget(self)
        container_layout = QVBoxLayout(container)
        container_layout.addWidget(main_splitter)
        container_layout.setContentsMargins(4, 4, 4, 4)

        self.setCentralWidget(container)

    def open_selected_file(self, index=None):
        if isinstance(index, QModelIndex):
            file_path = self.model.filePath(index)
        else:
            index = self.tree.currentIndex()
            file_path = self.model.filePath(index)

        if not file_path:
            self.status_label.setText("Select a valid file to open.")
            return

        if os.path.isdir(file_path):
            self.set_directory_root(file_path)
            return

        if not os.path.isfile(file_path):
            self.status_label.setText("Select a valid file to open.")
            return

        if not self._has_valid_extension(file_path):
            self.status_label.setText("File extension is not supported.")
            return

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as stream:
                text = stream.read()
        except OSError as exc:
            self.status_label.setText(f"Unable to open file: {exc}")
            return

        if self.target_combo.currentIndex() == 0:
            self.top_editor.setPlainText(text)
            self.left_file_path = file_path
        else:
            self.bottom_editor.setPlainText(text)
            self.right_file_path = file_path

        self.status_label.setText(f"Opened: {os.path.basename(file_path)}")

    def save_current_file(self):
        current_index = self.target_combo.currentIndex()
        file_path = self.left_file_path if current_index == 0 else self.right_file_path
        editor = self.top_editor if current_index == 0 else self.bottom_editor

        if not file_path:
            self.status_label.setText("No file loaded in the selected editor.")
            return

        try:
            with open(file_path, "w", encoding="utf-8", errors="replace") as stream:
                stream.write(editor.toPlainText())
            self.status_label.setText(f"Saved: {os.path.basename(file_path)}")
        except OSError as exc:
            self.status_label.setText(f"Unable to save file: {exc}")

    def go_up_directory(self):
        parent_dir = os.path.dirname(self.root_path.rstrip(os.sep))
        if parent_dir and os.path.isdir(parent_dir) and parent_dir != self.root_path:
            self.set_directory_root(parent_dir)
        else:
            self.status_label.setText("Already at the top directory.")

    def refresh_file_tree(self):
        self.set_directory_root(self.root_path)

    def set_directory_root(self, directory):
        directory = os.path.abspath(directory)
        if not os.path.isdir(directory):
            self.status_label.setText("Cannot navigate to the selected directory.")
            return
        self.root_path = directory
        root_index = self.model.setRootPath(directory)
        self.tree.setRootIndex(root_index)
        self.tree.scrollTo(root_index)
        self.status_label.setText(f"Navigated to: {directory}")

    def choose_root_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Root Folder", self.root_path)
        if directory:
            self.set_directory_root(directory)

    def _has_valid_extension(self, file_path):
        _, extension = os.path.splitext(file_path)
        return extension.lower() in self.allowed_extensions


def main():
    app = QApplication(sys.argv)
    viewer = FileViewer()
    viewer.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
