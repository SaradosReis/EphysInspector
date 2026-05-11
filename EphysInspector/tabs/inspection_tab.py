"""
Tab 3 – Analysis Inspection
Lets the researcher review, channel by channel:
  • Raw trace (scrollable time window from the loaded .dat)
  • Raster plot (spikes aligned to each TTL)
  • PSTH (mean ± SEM, 10-ms bins)
Then the user ticks which channels to keep, and saves the selection to Excel.
"""
import os
import sys

# Ensure the parent EphysInspector directory is on the path so sibling modules
# (processor.py, data_loader.py, etc.) can be imported from inside tabs/
_PARENT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

import numpy as np
import pandas as pd
import pyqtgraph as pg
from PySide6.QtCore import Qt, QMetaObject, Slot
from PySide6.QtWidgets import (
    QCheckBox, QFileDialog, QGroupBox, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QScrollArea, QSplitter, QVBoxLayout, QWidget,
)


class InspectionTab(QWidget):
    def __init__(self, app_state):
        super().__init__()
        self.app_state   = app_state
        self._spike_times  = np.array([])
        self._spike_sites  = np.array([])
        self._spike_amps   = np.array([])
        self._ttls_sec     = np.array([])
        self._raw_data     = None
        self._sample_rate  = 30000.0
        self._site_map     = []
        self._selected     = {}   # chan -> bool
        self.setup_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def setup_ui(self):
        root = QVBoxLayout(self)

        # Top bar
        top_bar = QHBoxLayout()
        self.btn_load = QPushButton("🔄  Load from Tab 1 / 2")
        self.btn_load.clicked.connect(self.load_data)
        top_bar.addWidget(self.btn_load)

        self.lbl_info = QLabel("No data loaded.")
        self.lbl_info.setStyleSheet("color: gray; font-style: italic;")
        top_bar.addWidget(self.lbl_info, 1)

        self.btn_save_sel = QPushButton("💾  Save Channel Selection")
        self.btn_save_sel.clicked.connect(self.save_selection)
        self.btn_save_sel.setEnabled(False)
        top_bar.addWidget(self.btn_save_sel)

        root.addLayout(top_bar)

        # Main splitter: channel list | plots
        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: channel list with checkboxes
        left_pane = QWidget()
        left_layout = QVBoxLayout(left_pane)
        left_layout.addWidget(QLabel("Channels"))
        self.chan_list = QListWidget()
        self.chan_list.currentRowChanged.connect(self.on_channel_changed)
        left_layout.addWidget(self.chan_list, 1)

        sel_all_row = QHBoxLayout()
        btn_all   = QPushButton("All")
        btn_all.clicked.connect(lambda: self._toggle_all(True))
        btn_none  = QPushButton("None")
        btn_none.clicked.connect(lambda: self._toggle_all(False))
        sel_all_row.addWidget(btn_all)
        sel_all_row.addWidget(btn_none)
        left_layout.addLayout(sel_all_row)
        left_pane.setMaximumWidth(160)
        self.splitter.addWidget(left_pane)

        # Right: three stacked plot widgets
        right_pane  = QWidget()
        right_layout = QVBoxLayout(right_pane)

        pg.setConfigOptions(antialias=True)

        self.plot_raw    = pg.PlotWidget(title="Raw Trace (filtered)")
        self.plot_raster = pg.PlotWidget(title="Raster (aligned to TTL)")
        self.plot_psth   = pg.PlotWidget(title="PSTH (mean ± SEM)")

        for pw in (self.plot_raw, self.plot_raster, self.plot_psth):
            right_layout.addWidget(pw, 1)

        self.splitter.addWidget(right_pane)
        self.splitter.setStretchFactor(1, 4)

        root.addWidget(self.splitter, 1)

    # ── Load data ─────────────────────────────────────────────────────────────

    def load_data(self):
        """Pull everything from app_state (set by Tabs 1 & 2)."""
        from data_loader import DataLoader
        from processor  import Processor

        self.chan_list.clear()
        self._selected = {}

        res_path = self.app_state.get("res_mat_path")
        dat_path = self.app_state.get("dat_path")
        npy_path = self.app_state.get("npy_ttl_path")
        site_map = self.app_state.get("site_map", [])
        sr       = self.app_state.get("sample_rate", 30000.0)

        if not res_path or not dat_path:
            QMessageBox.warning(self, "Missing data",
                                "Please load .dat and complete spike detection in Tab 1 first.")
            return

        try:
            loader = DataLoader()
            spikes = loader.load_spikes(res_path)
            self._spike_times = spikes.get("spikeTimes", np.array([])).flatten().astype(float)
            self._spike_sites = spikes.get("spikeSites", np.array([])).flatten().astype(int)
            self._spike_amps  = spikes.get("spikeAmps",  np.array([])).flatten().astype(float)

            n_chans = self.app_state.get("n_chans", 1)
            self._raw_data = loader.load_dat(dat_path, n_chans)

            if npy_path and os.path.exists(npy_path):
                ttls = np.load(npy_path).flatten()
                self._ttls_sec = (ttls[::2] / sr) if len(ttls) > 1 else (ttls / sr)
            else:
                self._ttls_sec = np.array([])

            self._sample_rate = sr
            self._site_map    = site_map if site_map else list(range(1, n_chans + 1))
            self._processor   = Processor()

            # Populate channel list
            for i, ch in enumerate(self._site_map):
                item = QListWidgetItem(f"Ch {ch}")
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked)
                self.chan_list.addItem(item)
                self._selected[ch] = True

            self.lbl_info.setText(
                f"{len(self._site_map)} channels | "
                f"{len(self._ttls_sec)} TTLs | "
                f"{len(self._spike_times)} spikes")
            self.lbl_info.setStyleSheet("color: green;")
            self.btn_save_sel.setEnabled(True)

            if self.chan_list.count() > 0:
                self.chan_list.setCurrentRow(0)

        except Exception as exc:
            QMessageBox.critical(self, "Error loading data", str(exc))

    # ── Channel changed ───────────────────────────────────────────────────────

    def on_channel_changed(self, row):
        if row < 0 or row >= len(self._site_map):
            return
        self._update_plots(row)

    def _update_plots(self, row: int):
        # Use the Processor instance created during load_data
        proc = getattr(self, '_processor', None)

        site_idx  = row          # 1-based in spikeSites
        real_chan  = self._site_map[row]
        sr         = self._sample_rate

        # ---- extract spikes for this site ----
        mask       = (self._spike_sites == (site_idx + 1))
        sp_times   = self._spike_times[mask]          # samples
        sp_sec     = sp_times / sr
        sp_amps    = self._spike_amps[mask]

        # ================================================================
        # 1. Raw trace: first 2 s of data for this channel, filtered
        # ================================================================
        self.plot_raw.clear()
        if self._raw_data is not None:
            phys_row = real_chan - 1
            if 0 <= phys_row < self._raw_data.shape[0]:
                n_disp     = int(min(2.0 * sr, self._raw_data.shape[1]))
                chunk      = self._raw_data[phys_row, :n_disp].astype(np.float32)
                chunk     -= chunk.mean()
                t_axis     = np.arange(n_disp) / sr
                if proc is None:
                    from processor import Processor
                    proc = Processor()
                filt       = proc.bandpass_filter(
                    chunk[np.newaxis, :], sr, 300, 3000)[0]
                self.plot_raw.plot(t_axis, filt,
                                   pen=pg.mkPen((150, 180, 255), width=1))
                self.plot_raw.setLabel("bottom", "Time (s)")
                self.plot_raw.setLabel("left", "Amplitude (a.u.)")
                # Overlay TTL markers
                for ttl_s in self._ttls_sec:
                    if 0 <= ttl_s <= 2.0:
                        vline = pg.InfiniteLine(pos=ttl_s, angle=90,
                                                pen=pg.mkPen("g", width=1.5,
                                                              style=Qt.PenStyle.DashLine))
                        self.plot_raw.addItem(vline)

        # ================================================================
        # 2. Raster
        # ================================================================
        self.plot_raster.clear()
        WIN_BEF, WIN_AFT = 1.0, 1.0   # seconds

        if len(self._ttls_sec) > 0 and len(sp_sec) > 0:
            all_rel, all_trial = [], []
            for trial_i, t0 in enumerate(self._ttls_sec[2:], start=1):
                mask_w = (sp_sec >= t0 - WIN_BEF) & (sp_sec <= t0 + WIN_AFT)
                rel = sp_sec[mask_w] - t0
                all_rel.extend(rel)
                all_trial.extend([trial_i] * len(rel))

            if all_rel:
                scatter = pg.ScatterPlotItem(
                    x=all_rel, y=all_trial,
                    size=3, pen=pg.mkPen(None),
                    brush=pg.mkBrush(50, 50, 50, 220))
                self.plot_raster.addItem(scatter)

        vline_r = pg.InfiniteLine(pos=0, angle=90,
                                  pen=pg.mkPen("r", width=1.5,
                                               style=Qt.PenStyle.DashLine))
        self.plot_raster.addItem(vline_r)
        self.plot_raster.setLabel("bottom", "Time re TTL (s)")
        self.plot_raster.setLabel("left", "Trial #")
        self.plot_raster.setXRange(-WIN_BEF, WIN_AFT, padding=0)

        # ================================================================
        # 3. PSTH
        # ================================================================
        self.plot_psth.clear()
        BIN_S   = 0.010   # 10 ms
        HALF_W  = 1.0     # ± 1 s

        if len(self._ttls_sec) > 2 and len(sp_sec) > 0:
            edges       = np.arange(-HALF_W, HALF_W + BIN_S, BIN_S)
            bin_centers = edges[:-1] + BIN_S / 2
            n_trials    = max(len(self._ttls_sec) - 2, 1)
            M           = np.zeros((n_trials, len(bin_centers)))

            for ti, t0 in enumerate(self._ttls_sec[2:]):
                in_w  = (sp_sec >= t0 - HALF_W) & (sp_sec <= t0 + HALF_W)
                rel   = sp_sec[in_w] - t0
                cnts, _ = np.histogram(rel, bins=edges)
                M[ti] = cnts / BIN_S

            # Baseline-subtract per trial
            bl_mask = bin_centers < 0
            M = M - M[:, bl_mask].mean(axis=1, keepdims=True)

            mean_psth = M.mean(axis=0)
            sem_psth  = M.std(axis=0) / np.sqrt(n_trials)

            # Smooth (Gaussian, σ=2 bins)
            from scipy.ndimage import gaussian_filter1d
            mean_sm = gaussian_filter1d(mean_psth, sigma=2)
            sem_sm  = gaussian_filter1d(sem_psth,  sigma=2)

            # Shaded SEM
            x_fill = np.concatenate([bin_centers, bin_centers[::-1]])
            y_fill = np.concatenate([mean_sm - sem_sm, (mean_sm + sem_sm)[::-1]])
            fill = pg.PlotDataItem(x_fill, y_fill,
                                   fillLevel=0,
                                   brush=pg.mkBrush(100, 149, 237, 80),
                                   pen=pg.mkPen(None))
            self.plot_psth.addItem(fill)
            self.plot_psth.plot(bin_centers, mean_sm,
                                pen=pg.mkPen((60, 90, 200), width=2))

        vline_p = pg.InfiniteLine(pos=0, angle=90,
                                  pen=pg.mkPen("r", width=1.5,
                                               style=Qt.PenStyle.DashLine))
        self.plot_psth.addItem(vline_p)
        self.plot_psth.setLabel("bottom", "Time re TTL (s)")
        self.plot_psth.setLabel("left", "ΔRate (Hz)")
        self.plot_psth.setXRange(-HALF_W, HALF_W, padding=0)

    # ── Toggle all checkboxes ─────────────────────────────────────────────────

    def _toggle_all(self, state: bool):
        check = Qt.CheckState.Checked if state else Qt.CheckState.Unchecked
        for i in range(self.chan_list.count()):
            self.chan_list.item(i).setCheckState(check)
            ch = self._site_map[i]
            self._selected[ch] = state

    # ── Save selection ────────────────────────────────────────────────────────

    def save_selection(self):
        # Read current checkbox states
        for i in range(self.chan_list.count()):
            item = self.chan_list.item(i)
            ch   = self._site_map[i]
            self._selected[ch] = (item.checkState() == Qt.CheckState.Checked)

        # Persist to app_state for Tab 4
        self.app_state["selected_channels"] = {
            ch: sel for ch, sel in self._selected.items() if sel}

        # Save Excel
        fig_dir = self.app_state.get("figures_dir")
        if not fig_dir:
            dat_path = self.app_state.get("dat_path", "")
            fig_dir  = os.path.join(os.path.dirname(dat_path), "Figures")
            os.makedirs(fig_dir, exist_ok=True)

        rows = []
        for i in range(self.chan_list.count()):
            ch  = self._site_map[i]
            sel = self.chan_list.item(i).checkState() == Qt.CheckState.Checked
            rows.append({"Channel": ch, "Selected": "Yes" if sel else "No"})

        df = pd.DataFrame(rows)
        out_path = os.path.join(fig_dir, "SelectedChannels.xlsx")
        df.to_excel(out_path, index=False)

        QMessageBox.information(
            self, "Saved",
            f"Channel selection saved to:\n{out_path}")
