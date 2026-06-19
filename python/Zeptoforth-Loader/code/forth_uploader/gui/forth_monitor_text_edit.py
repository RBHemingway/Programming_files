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
        self._history = []
        self._history_index = -1
        self._max_history = 10

    def _cursor_in_last_line(self):
        cursor = self.textCursor()
        return cursor.blockNumber() == self.document().blockCount() - 1

    def _replace_current_line(self, text):
        cursor = self.textCursor()
        cursor.beginEditBlock()
        cursor.movePosition(cursor.StartOfBlock)
        cursor.movePosition(cursor.EndOfBlock, cursor.KeepAnchor)
        cursor.removeSelectedText()
        cursor.insertText(text)
        cursor.movePosition(cursor.EndOfBlock)
        self.setTextCursor(cursor)
        cursor.endEditBlock()

    def _add_history(self, line_text):
        cleaned = line_text.rstrip()
        if not cleaned:
            return
        if self._history and self._history[-1] == cleaned:
            return
        self._history.append(cleaned)
        if len(self._history) > self._max_history:
            self._history.pop(0)
        self._history_index = -1

    def _history_entry(self, direction):
        if not self._history:
            return None
        if direction == "up":
            if self._history_index == -1:
                self._history_index = len(self._history) - 1
            elif self._history_index > 0:
                self._history_index -= 1
        elif direction == "down":
            if self._history_index == -1:
                return ""
            self._history_index += 1
            if self._history_index >= len(self._history):
                self._history_index = -1
                return ""
        if self._history_index == -1:
            return ""
        return self._history[self._history_index]

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Up and self._cursor_in_last_line():
            entry = self._history_entry("up")
            if entry is not None:
                self._replace_current_line(entry)
                return

        if event.key() == Qt.Key_Down and self._cursor_in_last_line():
            entry = self._history_entry("down")
            if entry is not None:
                self._replace_current_line(entry)
                return

        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            cursor = self.textCursor()
            cursor.movePosition(cursor.StartOfBlock)
            cursor.movePosition(cursor.EndOfBlock, cursor.KeepAnchor)
            current_line = cursor.selectedText()

            if not (event.modifiers() & Qt.ShiftModifier):
                cursor.clearSelection()
                cursor.movePosition(cursor.EndOfBlock)
                cursor.insertText(" .s")
                self.setTextCursor(cursor)
                cursor.movePosition(cursor.StartOfBlock)
                cursor.movePosition(cursor.EndOfBlock, cursor.KeepAnchor)
                current_line = cursor.selectedText()

            self._add_history(current_line)
            self.return_pressed.emit(current_line)

        elif event.key() == Qt.Key_Escape:
            # Select the entire current line and delete it
            cursor = self.textCursor()
            cursor.movePosition(cursor.StartOfBlock)
            cursor.movePosition(cursor.EndOfBlock, cursor.KeepAnchor)
            cursor.removeSelectedText()
            return # Skip the base class implementation for Escape

        super().keyPressEvent(event) # Always call the base class implementation