from PyQt5.QtWidgets import QPlainTextEdit
from PyQt5.QtCore import Qt, pyqtSignal

class ForthMonitorTextEdit(QPlainTextEdit):
    """
    A custom QPlainTextEdit widget that emits a signal when the Return key is pressed,
    along with the text of the current line before the newline character is added.
    """
    return_pressed = pyqtSignal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Optionally, set a default background to distinguish it from a read-only one
        # self.setStyleSheet("background-color: #f0f0f0;")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            cursor = self.textCursor()

            # If Shift is NOT held, append " .s" to the end of the current line
            if not (event.modifiers() & Qt.ShiftModifier):
                cursor.movePosition(cursor.EndOfBlock)
                cursor.insertText(" .s")
                self.setTextCursor(cursor)

            # Get the text of the current block (line) before the newline is inserted
            cursor.movePosition(cursor.StartOfBlock)
            cursor.movePosition(cursor.EndOfBlock, cursor.KeepAnchor)
            line_text = cursor.selectedText()
            self.return_pressed.emit(line_text)

        elif event.key() == Qt.Key_Escape:
            # Select the entire current line and delete it
            cursor = self.textCursor()
            cursor.movePosition(cursor.StartOfBlock)
            cursor.movePosition(cursor.EndOfBlock, cursor.KeepAnchor)
            cursor.removeSelectedText()
            return # Skip the base class implementation for Escape

        super().keyPressEvent(event) # Always call the base class implementation