import sys, requests
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLineEdit, QSizeGrip
)
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QFont


API_KEY = "<KEY>"
BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-chat"

F_SIZE = 10
OPACITY = 0.35
FG = "#555555"

class GlassTranslator(QWidget):
    def __init__(self):
        super().__init__()
        self._drag: QPoint | None = None
        self._mode = "input"

        self._setup()
        self._ui()
        self._center()

    def _setup(self):
        self.setWindowFlag(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.resize(640, 36)
        self.setMinimumWidth(200)

    def _center(self):
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.width() / 2 - screen.width() / 2, screen.height() / 3)

    def _ui(self):
        self._edit = QLineEdit()
        self._edit.setFont(QFont("monospace", F_SIZE))
        self.setWindowOpacity(OPACITY)
        self._edit.setStyleSheet(f"""
            QLabel{{
                color:{FG};
                background: transparent;
                padding: 4px 8px;
                border: none;
            }}
        """)

        self._edit.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._edit.setPlaceholderText("...")
        self._edit.returnPressed.connect(self._on_enter)

        self._edit.installEventFilter(self)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        self._grip = QSizeGrip(self)
        self._grip.setFixedSize(12, 12)
        self._grip.setStyleSheet("background: transparent;")

    def eventFilter(self, obj, event):
        if obj is self._edit:
            t = event.type()
            if t == event.Type.KeyPress and event.key() == Qt.Key_Tab:
                self._on_enter()
                return True
            if t == event.Type.MouseButtonPress:
                self._mouse_press(event)
                return False
            elif t == event.Type.MouseMove:
                self._mouse_move(event)
                return False
            elif t == event.Type.MouseButtonRelease:
                self._mouse_release(event)
                return False
        return super().eventFilter(obj, event)

    def _mouse_press(self, e):
        if e.button() == Qt.LeftButton:
            self._drag = e.globalPostion().toPoint() - self.frameGeometry().topLeft()

    def _mouse_move(self, e):
        if self._drag is not None:
            self.move(e.globalPosition().toPoint() - self._drag)

    def _mouse_release(self, e):
        self._drag = None

    def _on_enter(self):
        text = self._edit.text().strip()
        if not text:
            return

        if self._mode == "input":
            self._tranlate(text)
        else:
            self._mode = "input"
            self._edit.clear()
            self._edit.setReadOnly(False)
            self._edit.setPlaceholderText("...")
            self._edit.setFocus()

    def _tranlate(self, text):
        self._edit.setReadOnly(True)
        self._edit.setText("...")
        self._edit.setPlaceholderText("")
        QApplication.processEvents()

        try:
            resp = requests.post(
                f"{BASE_URL}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": MODEL,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "Translate to Chinese. Rules:\n"
                                "- Reply ONLY the translation\n"
                                "- If nonsense -> reply exactly: unknow\n"
                                "- Keep it short.\n"
                                "- If misspelled -> just translate the right sentence that you deem."
                            ),
                        },
                        {"role": "user", "content": text},
                    ],
                    "temperature": 0,
                    "max_tokens": 200,
                },
                timeout=10,
            )
            resp.raise_for_status()
            result = resp.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            result = "(API ERROR)"

        self._mode = "result"
        self._edit.setText(result)
        self._edit.setPlaceholderText("Enter -> new input  Esc -> quit")
        self._edit.home(False)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(e)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._grip.move(self.width() - 12, self.height() - 12)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = GlassTranslator()
    w.show()
    sys.exit(app.exec())