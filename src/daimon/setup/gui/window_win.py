"""Windows onboarding window (PySide6).

Windows has no TCC permission gate, so onboarding is mostly about wiring Daimon
into the detected AI clients and reminding the user to set the hands ceiling
deliberately (the only guardrail, since the OS imposes none). The pure client
registry + deploy are reused as-is.
"""

from __future__ import annotations


class OnboardingController:
    def __init__(self, backend=None) -> None:
        if backend is None:
            from ..permissions import WindowsBackend
            backend = WindowsBackend()
        self._backend = backend
        self._win = None

    def show(self) -> None:
        from PySide6 import QtWidgets

        from ...setup.clients.registry import default_adapters, detected

        w = QtWidgets.QWidget()
        w.setWindowTitle("Daimon — Setup")
        layout = QtWidgets.QVBoxLayout(w)

        layout.addWidget(QtWidgets.QLabel(
            "<b>Daimon</b> — give any AI eyes, hands, and a face on your PC."))
        layout.addWidget(QtWidgets.QLabel(
            "Windows needs no OS permission grant (no TCC). The hands ceiling is\n"
            "the guardrail — set it deliberately in the tray menu (default L0)."))

        clients = detected(default_adapters())
        if clients:
            layout.addWidget(QtWidgets.QLabel(
                f"Detected AI clients: {', '.join(c.name for c in clients)}"))
            btn = QtWidgets.QPushButton("Register Daimon into all detected clients")

            def _register():
                from ...setup.deploy import install_all
                try:
                    install_all()
                    btn.setText("Registered ✓ — restart your AI client")
                    btn.setEnabled(False)
                except Exception:
                    from ...applog import log_exception
                    log_exception("onboard/install_all")
                    btn.setText("Registration failed — see logs")

            btn.clicked.connect(_register)
            layout.addWidget(btn)
        else:
            layout.addWidget(QtWidgets.QLabel("No AI clients detected yet."))

        done = QtWidgets.QPushButton("Done")
        done.clicked.connect(w.close)
        layout.addWidget(done)

        w.resize(460, 220)
        w.show()
        self._win = w  # keep a reference


def run() -> int:
    from PySide6 import QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    controller = OnboardingController()
    controller.show()
    app.exec()
    return 0
