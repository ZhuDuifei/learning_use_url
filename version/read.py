import sys, os, json, requests
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout,
    QMenu, QFileDialog, QSizePolicy
)
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QFont, QMouseEvent

CHARS = 80
OPACITY = 0.35
F_SIZE = 9
FG = "#555555"
DFILE = "r.txt"

# API_KEY = os.getenv("API_KEY")
API_KEY = "<KEY>"
BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-chat"


class Reader(QWidget):
    def __init__(self):
        super().__init__()
        self._lines: list[str] = []
        self._line = 0
        self._off = 0
        self._n = CHARS
        self._op = OPACITY
        self._drag: QPoint | None = None
        self._path: str = ""
        self._mode = "read"  # translation mode
        self._trans: dict[str, str] = {}  # translation cache

        self._setup()
        self._ui()

        path = None
        if len(sys.argv) > 1:
            path = sys.argv[1]
        elif os.path.exists(DFILE):
            path = DFILE

        if path:
            self._load(path)
            self._restore(path)

        self._show()

    def _setup(self):
        # 修复：只保留纯粹的无边框、置顶和工具窗口属性，去掉 CustomizeWindowHint，彻底隐藏标题栏
        self.setWindowFlag(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )

        # 设置背景透明
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.resize(720, 48)
        self.setMinimumWidth(720)

    def _ui(self):
        self._lab = QLabel("(no text - right-click  ->  open file)")
        self._lab.setFont(QFont("monospace", F_SIZE))
        self.setWindowOpacity(self._op)

        self._lab.setStyleSheet(f"""
            QLabel{{
                color:{FG};
                padding: 3px 8px;
                background: transparent;
            }}
        """)
        self._lab.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self._lab.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._lab.setContextMenuPolicy(Qt.CustomContextMenu)
        self._lab.customContextMenuRequested.connect(self._menu)

        # 安装事件过滤器，让窗口能够接收鼠标事件实现拖动
        self._lab.installEventFilter(self)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._lab)

        # 注意：这里绝对不能加 QSizeGrip，否则它会拦截鼠标事件，导致你原本写好的拖动代码失效！

    def eventFilter(self, obj, e):
        """事件过滤器，处理 QLabel 上的鼠标事件实现窗口拖动"""
        if obj == self._lab:
            # 使用整数值比较事件类型
            if e.type() == QMouseEvent.MouseButtonPress and e.button() == Qt.LeftButton:
                self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
                return True
            elif e.type() == QMouseEvent.MouseMove and (e.buttons() & Qt.LeftButton):
                if self._drag is not None:
                    self.move(e.globalPosition().toPoint() - self._drag)
                return True
            elif e.type() == QMouseEvent.MouseButtonRelease:
                self._drag = None
                return True
            elif e.type() == QMouseEvent.MouseButtonDblClick and e.button() == Qt.LeftButton:
                self._copy()
                return True
        return super().eventFilter(obj, e)

    def _menu(self, pos):
        m = QMenu(self)
        m.addAction("Open File...", self._open)
        m.addAction("Copy line(Ctrl+C / Double-Click)", self._copy)
        m.addAction("Translate(Tab)", self._toggle)
        m.addSeparator()
        m.addAction("Chars +5 (Ctrl+=)", lambda: self._adjust(5))
        m.addAction("Chars -5 (Ctrl+-)", lambda: self._adjust(-5))
        m.addSeparator()
        m.addAction("Fade text (-)", lambda: self._alpha(-0.05))
        m.addAction("Fade text (+)", lambda: self._alpha(0.05))
        m.addSeparator()
        m.addAction("Quit (Esc)", self.close)
        m.exec(self._lab.mapToGlobal(pos))

    def _load(self, path: str):
        if not os.path.exists(path):
            return
        with open(path, encoding="utf-8") as f:
            self._lines = [ln.strip() for ln in f if ln.strip()]
        self._line = 0
        self._off = 0
        self._mode = "read"
        self._path = path
        self._show()

    def _open(self):
        p, _ = QFileDialog.getOpenFileName(self, "Open", "", "Text Files (*.txt);;All Files (*)")
        if p:
            self._load(p)
            self._restore(p)

    def _copy(self):
        if self._lines:
            QApplication.clipboard().setText(self._disp())

    def _h(self, d: int):
        if not self._lines: return
        mx = max(0, len(self._disp()) - self._n)
        self._off = max(0, min(self._off + d, mx))
        self._show()
        self._save()

    def _v(self, d: int):
        if not self._lines: return
        self._line = (self._line + d) % len(self._lines)
        self._off = 0
        self._mode = "read"
        self._show()
        self._save()

    def _cur(self) -> str:
        return self._lines[self._line]

    def _disp(self) -> str:
        if self._mode == "trans":
            return self._trans.get(self._cur(), self._cur())
        return self._cur()

    def _show(self):
        if not self._lines:
            self._lab.setText("(no text - right-click  ->  open file)")
            return
        c = self._disp()
        vis = c[self._off:self._off + self._n]
        self._lab.setText(vis)

    def _toggle(self):
        if not self._lines: return
        if self._mode == "read":
            src = self._cur()
            if src not in self._trans:
                self._lab.setText("Translating...")
                QApplication.processEvents()
                self._trans[src] = self._translate(src)
            self._mode = "trans"
        else:
            self._mode = "read"
        self._show()

    def _translate(self, text: str) -> str:
        if not API_KEY:
            return "(Missing API key)"
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
        return result

    def _adjust(self, d: int):
        self._n = max(5, self._n + d)
        if self._lines:
            self._off = min(self._off, len(self._disp()) - self._n)
        self._show()

    def _alpha(self, d: float):
        self._op = max(0.15, min(1.0, self._op + d))
        self.setWindowOpacity(self._op)

    def _save(self):
        if self._path:
            self._save_state(self._path)

    def _state_path(self, path: str):
        return os.path.splitext(path)[0] + "_state.json"

    def _save_state(self, path: str):
        data = {"line": self._line, "offset": self._off}
        sp = self._state_path(path)
        with open(sp, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def _restore(self, path: str):
        sp = self._state_path(path)
        if not os.path.exists(sp):
            return
        try:
            with open(sp, encoding="utf-8") as f:
                data = json.load(f)
            line = data.get("line", 0)
            offset = data.get("offset", 0)
            if 0 <= line < len(self._lines):
                self._line = line
                self._off = min(offset, max(0, len(self._cur()) - self._n))

        except Exception:
            pass

    def keyPressEvent(self, e):
        k, m = e.key(), e.modifiers()
        ct = m & Qt.ControlModifier

        if k in (Qt.Key_Left, Qt.Key_A):
            self._h(-20 if ct else -20)
        elif k in (Qt.Key_Right, Qt.Key_D):
            self._h(20 if ct else 20)
        elif k in (Qt.Key_Up, Qt.Key_W):
            self._v(-1)
        elif k in (Qt.Key_Down, Qt.Key_S):
            self._v(1)
        elif k == Qt.Key_Tab:
            self._toggle()
        elif k == Qt.Key_Home:
            self._off = 0
            self._show()
            self._save()
        elif k == Qt.Key_End:
            if self._lines:
                self._off = max(0, len(self._disp()) - self._n)
                self._show()
                self._save()
        elif k == Qt.Key_C and ct:
            self._copy()
        elif k in (Qt.Key_Escape, Qt.Key_Space):
            self.close()
        elif k in (Qt.Key_Plus, Qt.Key_Equal) and ct:
            self._adjust(5)
        elif k == Qt.Key_Minus and ct:
            self._adjust(-5)
        else:
            super().keyPressEvent(e)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    r = Reader()
    r.show()
    sys.exit(app.exec())