import os
import sys
import threading

# Ensure EphysInspector root is importable from tabs/
_PARENT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QComboBox, QLineEdit, QSpinBox, QPushButton,
                               QGroupBox, QFormLayout, QDoubleSpinBox, QFileDialog)
from PySide6.QtCore import Qt, QMetaObject, Q_ARG, Slot


class AnalysisTab(QWidget):
    def __init__(self, app_state):
        super().__init__()
        self.app_state = app_state
        self.seq_path = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # ── Subject Info ──────────────────────────────────────────────────────
        info_group = QGroupBox("Subject Information")
        info_layout = QFormLayout()

        self.input_genotype = QLineEdit()
        self.input_genotype.setPlaceholderText("e.g. WT, KO")
        info_layout.addRow("Genotype:", self.input_genotype)

        self.input_animal_num = QLineEdit()
        self.input_animal_num.setPlaceholderText("e.g. 1, 2, 3")
        info_layout.addRow("Animal Number:", self.input_animal_num)

        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # ── Protocol Configuration ────────────────────────────────────────────
        proto_group = QGroupBox("Protocol Configuration")
        proto_layout = QFormLayout()

        self.combo_protocol = QComboBox()
        self.combo_protocol.addItems(["Auditory Protocol", "Baseline Protocol"])
        self.combo_protocol.currentIndexChanged.connect(self.on_protocol_changed)
        proto_layout.addRow("Protocol:", self.combo_protocol)

        self.spin_window = QSpinBox()
        self.spin_window.setRange(10, 2000)
        self.spin_window.setValue(400)
        self.spin_window.setSuffix(" ms")
        proto_layout.addRow("Sound Analysis Window:", self.spin_window)

        self.spin_baseline = QDoubleSpinBox()
        self.spin_baseline.setRange(0.1, 60.0)
        self.spin_baseline.setValue(3.0)
        self.spin_baseline.setSuffix(" min")
        proto_layout.addRow("Baseline Period (before 1st TTL):", self.spin_baseline)

        # Frequency sequence CSV
        seq_row = QHBoxLayout()
        self.btn_load_seq = QPushButton("Browse…")
        self.btn_load_seq.setFixedWidth(80)
        self.btn_load_seq.clicked.connect(self.load_sequence_file)
        self.seq_file_label = QLabel("No file loaded")
        seq_row.addWidget(self.btn_load_seq)
        seq_row.addWidget(self.seq_file_label, 1)
        proto_layout.addRow("random_sequence.csv:", seq_row)

        proto_group.setLayout(proto_layout)
        layout.addWidget(proto_group)

        # ── Status label ──────────────────────────────────────────────────────
        self.status_label = QLabel("Ready. Load data in Tab 1 first, then run analysis here.")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: gray; font-style: italic; padding: 4px;")
        layout.addWidget(self.status_label)

        # ── Run button ────────────────────────────────────────────────────────
        action_layout = QHBoxLayout()
        action_layout.addStretch()
        self.btn_run = QPushButton("▶  Run Analysis")
        self.btn_run.setMinimumWidth(220)
        self.btn_run.setMinimumHeight(44)
        self.btn_run.setStyleSheet("font-weight: bold; font-size: 13px;")
        self.btn_run.clicked.connect(self.run_analysis)
        action_layout.addWidget(self.btn_run)
        layout.addLayout(action_layout)

        layout.addStretch()
        self.on_protocol_changed()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def load_sequence_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open random_sequence.csv", "", "CSV Files (*.csv)")
        if path:
            self.seq_path = path
            self.seq_file_label.setText(os.path.basename(path))

    def on_protocol_changed(self):
        is_auditory = self.combo_protocol.currentText() == "Auditory Protocol"
        self.spin_window.setEnabled(is_auditory)
        self.btn_load_seq.setEnabled(is_auditory)
        self.spin_baseline.setEnabled(is_auditory)

    # ── Status helpers (thread-safe) ──────────────────────────────────────────

    def _set_status_safe(self, msg: str, color: str):
        """Thread-safe: update status label from any thread."""
        self._pending_msg = msg
        self._pending_color = color
        QMetaObject.invokeMethod(self, "_do_set_status",
                                 Qt.ConnectionType.QueuedConnection)

    @Slot()
    def _do_set_status(self):
        self.status_label.setText(getattr(self, "_pending_msg", ""))
        color = getattr(self, "_pending_color", "gray")
        self.status_label.setStyleSheet(
            f"color: {color}; font-style: italic; padding: 4px;")

    def _set_btn_enabled_safe(self, enabled: bool):
        self._pending_btn_enabled = enabled
        QMetaObject.invokeMethod(self, "_do_set_btn_enabled",
                                 Qt.ConnectionType.QueuedConnection)

    @Slot()
    def _do_set_btn_enabled(self):
        self.btn_run.setEnabled(getattr(self, "_pending_btn_enabled", True))

    # ── Analysis runner ───────────────────────────────────────────────────────

    def run_analysis(self):
        from analysis_engine import AnalysisEngine

        genotype   = self.input_genotype.text().strip()
        animal_num = self.input_animal_num.text().strip()
        protocol   = self.combo_protocol.currentText()
        window_ms  = self.spin_window.value()
        bl_min     = self.spin_baseline.value()

        # Guards
        if not self.app_state.get("dat_path"):
            self._set_status_safe(
                "⚠  No .dat file found — load data in Tab 1 first.", "orange")
            return
        if not self.app_state.get("res_mat_path"):
            self._set_status_safe(
                "⚠  No _res.mat found — complete spike detection in Tab 1 first.", "orange")
            return
        if protocol == "Auditory Protocol" and not self.app_state.get("npy_ttl_path"):
            self._set_status_safe(
                "⚠  No TTL (.npy) file loaded — load TTLs in Tab 1 first.", "orange")
            return

        self.btn_run.setEnabled(False)
        self._set_status_safe(f"⏳  Running {protocol} … please wait.", "steelblue")

        def worker():
            try:
                engine = AnalysisEngine(self.app_state)

                def progress_cb(current, total, chan):
                    self._set_status_safe(
                        f"⏳  Channel {current}/{total} (Ch {chan}) — "
                        f"quantification + figures…", "steelblue")

                if protocol == "Auditory Protocol":
                    engine.run_auditory_protocol(
                        genotype=genotype,
                        animal_num=animal_num,
                        window_ms=window_ms,
                        baseline_min=bl_min,
                        seq_csv_path=self.seq_path,
                        progress_cb=progress_cb,
                    )
                else:
                    engine.run_baseline_protocol(
                        genotype=genotype,
                        animal_num=animal_num,
                    )
                fig_dir = engine.get_figures_dir()
                # Persist for Tab 3
                self.app_state["figures_dir"]   = fig_dir
                self.app_state["genotype"]      = genotype
                self.app_state["animal_num"]    = animal_num
                self._set_status_safe(
                    f"✓  {protocol} complete!\nResults → {fig_dir}", "green")
            except Exception as exc:
                self._set_status_safe(f"✗  Error: {exc}", "red")
            finally:
                self._set_btn_enabled_safe(True)

        threading.Thread(target=worker, daemon=True).start()
