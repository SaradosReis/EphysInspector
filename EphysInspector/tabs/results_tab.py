"""
Tab 4 – Results
Aggregates Quantification Excel files across animals, filters by selected
channels, groups by genotype, and generates publication-ready figures:
  1. PSTH – all sounds, grouped by genotype
  2. PSTH – per frequency, grouped by genotype
  3. Bar graphs dF/F – all sounds + per frequency
  4. Population heatmap

Metadata (Genotype, Animal#) can be freely edited in the inline table
before generating graphs – no separate dialog needed.
"""
import os

import numpy as np
import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QFileDialog, QGroupBox, QHBoxLayout,
    QLabel, QMessageBox, QPushButton, QSizePolicy, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

# matplotlib inside PySide6
import matplotlib
matplotlib.use("Agg")           # off-screen, thread-safe
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas


FREQ_LABELS = ["8Hz", "12Hz", "16Hz", "20Hz", "24Hz", "28Hz", "WN", "WNcrescendo"]

# Table column indices
COL_FILE    = 0
COL_CHAN    = 1
COL_GENO   = 2
COL_ANIMAL = 3
COLUMNS    = ["File", "Channel", "Genotype", "Animal #"]


class ResultsTab(QWidget):
    def __init__(self, app_state):
        super().__init__()
        self.app_state  = app_state
        self._raw_data  = pd.DataFrame()   # one row per file×frequency combo
        self._fig_dir   = None
        self.setup_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def setup_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)

        # ── File loading & metadata table ────────────────────────────────────
        load_group = QGroupBox("Load Quantification Files  "
                               "(double-click Genotype / Animal # to edit)")
        load_layout = QVBoxLayout(load_group)

        btn_row = QHBoxLayout()
        self.btn_add   = QPushButton("➕  Add files…")
        self.btn_add.clicked.connect(self.add_files)
        self.btn_clear = QPushButton("🗑  Clear all")
        self.btn_clear.clicked.connect(self.clear_files)
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_clear)
        btn_row.addStretch()
        load_layout.addLayout(btn_row)

        # Editable metadata table
        self.meta_table = QTableWidget(0, len(COLUMNS))
        self.meta_table.setHorizontalHeaderLabels(COLUMNS)
        self.meta_table.horizontalHeader().setStretchLastSection(False)
        self.meta_table.setColumnWidth(COL_FILE,   320)
        self.meta_table.setColumnWidth(COL_CHAN,    65)
        self.meta_table.setColumnWidth(COL_GENO,   100)
        self.meta_table.setColumnWidth(COL_ANIMAL,  80)
        self.meta_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.meta_table.setMaximumHeight(180)
        # Only Genotype (col 2) and Animal# (col 3) are editable;
        # File and Channel will be set as non-editable
        self.meta_table.itemChanged.connect(self._on_meta_changed)
        load_layout.addWidget(self.meta_table)

        self.lbl_info = QLabel("No files loaded.")
        self.lbl_info.setStyleSheet("color: gray; font-style: italic;")
        load_layout.addWidget(self.lbl_info)

        root.addWidget(load_group)

        # ── Graph selector ───────────────────────────────────────────────────
        graph_group  = QGroupBox("Choose Graphs to Generate")
        graph_layout = QVBoxLayout(graph_group)

        self.chk_psth_all  = QCheckBox("PSTH – all sounds (ΔRate by genotype)")
        self.chk_psth_freq = QCheckBox("PSTH – per frequency (ΔRate by genotype)")
        self.chk_bar_all   = QCheckBox("Bar graph – dF/F all sounds")
        self.chk_bar_freq  = QCheckBox("Bar graph – dF/F per frequency")
        self.chk_heatmap   = QCheckBox("Population heatmap (channels × genotype)")

        for chk in (self.chk_psth_all, self.chk_psth_freq,
                    self.chk_bar_all, self.chk_bar_freq, self.chk_heatmap):
            chk.setChecked(True)
            graph_layout.addWidget(chk)

        root.addWidget(graph_group)

        # ── Generate button ──────────────────────────────────────────────────
        gen_row = QHBoxLayout()
        gen_row.addStretch()
        self.btn_gen = QPushButton("📊  Generate Graphs")
        self.btn_gen.setMinimumWidth(220)
        self.btn_gen.setMinimumHeight(44)
        self.btn_gen.setStyleSheet("font-weight: bold; font-size: 13px;")
        self.btn_gen.clicked.connect(self.generate_graphs)
        gen_row.addWidget(self.btn_gen)
        root.addLayout(gen_row)

        # ── Status ───────────────────────────────────────────────────────────
        self.lbl_status = QLabel("")
        self.lbl_status.setWordWrap(True)
        root.addWidget(self.lbl_status)

        # ── Preview canvas ───────────────────────────────────────────────────
        self.fig, self.ax = plt.subplots(figsize=(8, 4))
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setMinimumHeight(300)
        root.addWidget(self.canvas, 1)

    # ── File management ───────────────────────────────────────────────────────

    def add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Open Quantification Excel files", "",
            "Excel Files (*.xlsx *.xls)")
        if not paths:
            return

        self.meta_table.itemChanged.disconnect(self._on_meta_changed)

        for p in paths:
            try:
                df_glob = pd.read_excel(p, sheet_name="GlobalMetrics")
                df_freq = pd.read_excel(p, sheet_name="PerFrequency")

                # Channel number from filename e.g. "Ch5_Quantification.xlsx"
                base     = os.path.basename(p)
                chan_num = int("".join(filter(str.isdigit, base.split("_")[0])))

                # Auto-guess metadata (user can override in the table)
                genotype   = self._guess_genotype(p)
                animal_num = self._guess_animal(p)

                # Add a row to the metadata table
                row = self.meta_table.rowCount()
                self.meta_table.insertRow(row)

                # File (read-only)
                file_item = QTableWidgetItem(os.path.basename(p))
                file_item.setFlags(file_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                file_item.setToolTip(p)
                file_item.setData(Qt.ItemDataRole.UserRole, p)   # store full path
                self.meta_table.setItem(row, COL_FILE, file_item)

                # Channel (read-only)
                chan_item = QTableWidgetItem(str(chan_num))
                chan_item.setFlags(chan_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                chan_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.meta_table.setItem(row, COL_CHAN, chan_item)

                # Genotype (editable)
                geno_item = QTableWidgetItem(genotype)
                geno_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.meta_table.setItem(row, COL_GENO, geno_item)

                # Animal # (editable)
                anim_item = QTableWidgetItem(str(animal_num))
                anim_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.meta_table.setItem(row, COL_ANIMAL, anim_item)

                # Store raw data internally (keyed by full path)
                self._store_file_data(p, chan_num, genotype, animal_num,
                                      df_glob, df_freq)

            except Exception as exc:
                QMessageBox.warning(self, "Warning",
                                    f"Could not load {p}:\n{exc}")

        self.meta_table.itemChanged.connect(self._on_meta_changed)
        self._refresh_info()

    def _store_file_data(self, path, chan_num, genotype, animal_num,
                         df_glob, df_freq):
        """Add per-frequency rows plus AllSounds row to _raw_data."""
        new_rows = []

        for _, row in df_freq.iterrows():
            new_rows.append({
                "File":         path,
                "Channel":      chan_num,
                "Genotype":     genotype,
                "AnimalNum":    animal_num,
                "Frequency":    row.get("Frequency", "Unknown"),
                "DeltaRate_Hz": row.get("DeltaRate_Hz", np.nan),
                "FiringRate_Hz": row.get("FiringRate_Hz", np.nan),
                "Amplitude_uV": row.get("Amplitude_uV", np.nan),
            })

        # AllSounds row from GlobalMetrics
        delta_all = df_glob["DeltaRate_Hz"].values[0] \
            if "DeltaRate_Hz" in df_glob.columns else np.nan
        fr_cols = df_glob.filter(like="FiringRate")
        amp_cols = df_glob.filter(like="Amplitude")
        new_rows.append({
            "File":         path,
            "Channel":      chan_num,
            "Genotype":     genotype,
            "AnimalNum":    animal_num,
            "Frequency":    "AllSounds",
            "DeltaRate_Hz": delta_all,
            "FiringRate_Hz": fr_cols.values[0, 0] if not fr_cols.empty else np.nan,
            "Amplitude_uV": amp_cols.values[0, 0] if not amp_cols.empty else np.nan,
        })

        self._raw_data = pd.concat(
            [self._raw_data, pd.DataFrame(new_rows)], ignore_index=True)

    def _on_meta_changed(self, item: QTableWidgetItem):
        """When the user edits Genotype or Animal# in the table, update _raw_data."""
        row = item.column()
        if row not in (COL_GENO, COL_ANIMAL):
            return

        table_row = item.row()
        file_item = self.meta_table.item(table_row, COL_FILE)
        if file_item is None:
            return
        full_path  = file_item.data(Qt.ItemDataRole.UserRole)
        new_value  = item.text().strip()

        if item.column() == COL_GENO:
            self._raw_data.loc[self._raw_data["File"] == full_path,
                               "Genotype"] = new_value
        elif item.column() == COL_ANIMAL:
            self._raw_data.loc[self._raw_data["File"] == full_path,
                               "AnimalNum"] = new_value

        self._refresh_info()

    def clear_files(self):
        self._raw_data = pd.DataFrame()
        self.meta_table.setRowCount(0)
        self._set_status("", "gray")
        self._refresh_info()

    def _refresh_info(self):
        if self._raw_data.empty:
            self.lbl_info.setText("No files loaded.")
            self.lbl_info.setStyleSheet("color: gray; font-style: italic;")
        else:
            n_files = self._raw_data["File"].nunique()
            genos   = sorted(self._raw_data["Genotype"].unique())
            self.lbl_info.setText(
                f"{n_files} file(s) loaded — "
                f"genotypes: {', '.join(genos)}")
            self.lbl_info.setStyleSheet("color: green;")

    # ── Metadata inference helpers ─────────────────────────────────────────────

    def _guess_genotype(self, path: str) -> str:
        gt = self.app_state.get("genotype", "")
        if gt:
            return gt
        for token in path.replace("\\", "/").split("/"):
            upper = token.upper()
            for label in ("WT", "KO", "HET", "HOMO", "CTRL", "CONTROL"):
                if label in upper:
                    return label
        return "Unknown"

    def _guess_animal(self, path: str) -> str:
        an = self.app_state.get("animal_num", "")
        return an if an else "?"

    # ── Graph generation ──────────────────────────────────────────────────────

    def generate_graphs(self):
        if self._raw_data.empty:
            self._set_status("⚠  No data loaded — add Quantification files first.",
                             "orange")
            return

        # Re-sync metadata from table (in case of edits not yet propagated)
        self._sync_metadata_from_table()

        # Apply channel filter from Tab 3
        selected = self.app_state.get("selected_channels", {})
        if selected:
            df = self._raw_data[
                self._raw_data["Channel"].isin(selected.keys())].copy()
        else:
            df = self._raw_data.copy()

        if df.empty:
            self._set_status("⚠  No data left after channel filtering.", "orange")
            return

        # Output directory
        fig_dir = self.app_state.get("figures_dir")
        if not fig_dir:
            fig_dir = QFileDialog.getExistingDirectory(
                self, "Choose output folder for result figures")
            if not fig_dir:
                return
        results_dir = os.path.join(fig_dir, "ResultsGraphs")
        os.makedirs(results_dir, exist_ok=True)
        self._fig_dir = results_dir

        saved = []

        if self.chk_psth_all.isChecked():
            p = self._plot_psth_all(df, results_dir)
            if p: saved.append(p)

        if self.chk_psth_freq.isChecked():
            p = self._plot_psth_freq(df, results_dir)
            if p: saved.append(p)

        if self.chk_bar_all.isChecked():
            p = self._plot_bar_all(df, results_dir)
            if p: saved.append(p)

        if self.chk_bar_freq.isChecked():
            p = self._plot_bar_freq(df, results_dir)
            if p: saved.append(p)

        if self.chk_heatmap.isChecked():
            p = self._plot_heatmap(df, results_dir)
            if p: saved.append(p)

        self._set_status(
            f"✓  {len(saved)} graph(s) saved to:\n{results_dir}", "green")

        if saved:
            preview_fig = plt.figure()
            img = plt.imread(saved[-1])
            plt.imshow(img)
            plt.axis("off")
            self._update_canvas(preview_fig)
            plt.close(preview_fig)

    def _sync_metadata_from_table(self):
        """Read every editable row in the table and patch _raw_data accordingly."""
        for r in range(self.meta_table.rowCount()):
            file_item  = self.meta_table.item(r, COL_FILE)
            geno_item  = self.meta_table.item(r, COL_GENO)
            anim_item  = self.meta_table.item(r, COL_ANIMAL)
            if file_item is None:
                continue
            full_path  = file_item.data(Qt.ItemDataRole.UserRole)
            genotype   = geno_item.text().strip()  if geno_item  else "Unknown"
            animal_num = anim_item.text().strip()  if anim_item  else "?"
            mask = self._raw_data["File"] == full_path
            self._raw_data.loc[mask, "Genotype"]  = genotype
            self._raw_data.loc[mask, "AnimalNum"] = animal_num

    # ── Individual plots ──────────────────────────────────────────────────────

    def _genotype_colors(self, genotypes):
        palette = ["#4C72B0", "#DD8452", "#55A868", "#C44E52",
                   "#8172B3", "#937860", "#DA8BC3", "#8C8C8C"]
        return {g: palette[i % len(palette)] for i, g in enumerate(sorted(genotypes))}

    def _plot_psth_all(self, df: pd.DataFrame, out_dir: str) -> str:
        sub   = df[df["Frequency"] == "AllSounds"]
        genos = sorted(sub["Genotype"].unique())
        colors = self._genotype_colors(genos)
        means = [sub[sub["Genotype"] == g]["DeltaRate_Hz"].mean() for g in genos]
        sems  = [sub[sub["Genotype"] == g]["DeltaRate_Hz"].sem()  for g in genos]

        fig, ax = plt.subplots(figsize=(max(4, len(genos) * 1.5), 4))
        ax.bar(genos, means, yerr=sems, capsize=5,
               color=[colors[g] for g in genos], edgecolor="k", linewidth=0.8)
        for g in genos:
            pts = sub[sub["Genotype"] == g]["DeltaRate_Hz"].dropna().values
            ax.scatter([g] * len(pts), pts, color="k", s=20, zorder=3, alpha=0.6)
        ax.axhline(0, color="k", linewidth=0.8, linestyle="--")
        ax.set_ylabel("ΔFiring Rate (Hz)", fontsize=11)
        ax.set_title("PSTH – All Sounds by Genotype", fontsize=12)
        ax.set_xlabel("Genotype", fontsize=11)
        plt.tight_layout()
        out = os.path.join(out_dir, "psth_all_sounds.png")
        fig.savefig(out, dpi=150)
        self._update_canvas(fig)
        plt.close(fig)
        return out

    def _plot_psth_freq(self, df: pd.DataFrame, out_dir: str) -> str:
        freqs = [f for f in FREQ_LABELS if f in df["Frequency"].values]
        if not freqs:
            return ""
        genos  = sorted(df["Genotype"].unique())
        colors = self._genotype_colors(genos)
        n_freq = len(freqs)
        fig, axes = plt.subplots(1, n_freq, figsize=(3 * n_freq, 4), sharey=True)
        if n_freq == 1:
            axes = [axes]
        for ax, freq in zip(axes, freqs):
            sub   = df[df["Frequency"] == freq]
            means = [sub[sub["Genotype"] == g]["DeltaRate_Hz"].mean() for g in genos]
            sems  = [sub[sub["Genotype"] == g]["DeltaRate_Hz"].sem()  for g in genos]
            ax.bar(range(len(genos)), means, yerr=sems, capsize=4,
                   color=[colors[g] for g in genos], edgecolor="k", linewidth=0.7)
            for i, g in enumerate(genos):
                pts = sub[sub["Genotype"] == g]["DeltaRate_Hz"].dropna().values
                ax.scatter([i] * len(pts), pts, color="k", s=14, zorder=3, alpha=0.6)
            ax.axhline(0, color="k", linewidth=0.8, linestyle="--")
            ax.set_title(freq, fontsize=9)
            ax.set_xticks(range(len(genos)))
            ax.set_xticklabels(genos, rotation=30, ha="right", fontsize=8)
        axes[0].set_ylabel("ΔFiring Rate (Hz)", fontsize=10)
        fig.suptitle("PSTH by Frequency & Genotype", fontsize=12)
        plt.tight_layout()
        out = os.path.join(out_dir, "psth_per_frequency.png")
        fig.savefig(out, dpi=150)
        self._update_canvas(fig)
        plt.close(fig)
        return out

    def _plot_bar_all(self, df: pd.DataFrame, out_dir: str) -> str:
        sub    = df[df["Frequency"] == "AllSounds"]
        genos  = sorted(sub["Genotype"].unique())
        colors = self._genotype_colors(genos)
        fig, ax = plt.subplots(figsize=(max(4, len(genos) * 1.5), 4))
        for i, g in enumerate(genos):
            pts  = sub[sub["Genotype"] == g]["DeltaRate_Hz"].dropna().values
            mean = pts.mean() if len(pts) else 0
            sem  = pts.std() / np.sqrt(len(pts)) if len(pts) > 1 else 0
            ax.bar(i, mean, yerr=sem, capsize=5,
                   color=colors[g], edgecolor="k", linewidth=0.8, label=g)
            ax.scatter([i] * len(pts), pts, color="k", s=20, zorder=3, alpha=0.65)
        ax.axhline(0, color="k", linewidth=0.8, linestyle="--")
        ax.set_xticks(range(len(genos)))
        ax.set_xticklabels(genos, fontsize=11)
        ax.set_ylabel("ΔFiring Rate (Hz)", fontsize=11)
        ax.set_title("dF/F – All Sounds by Genotype", fontsize=12)
        plt.tight_layout()
        out = os.path.join(out_dir, "bar_dff_all_sounds.png")
        fig.savefig(out, dpi=150)
        self._update_canvas(fig)
        plt.close(fig)
        return out

    def _plot_bar_freq(self, df: pd.DataFrame, out_dir: str) -> str:
        freqs = [f for f in FREQ_LABELS if f in df["Frequency"].values]
        if not freqs:
            return ""
        genos  = sorted(df["Genotype"].unique())
        colors = self._genotype_colors(genos)
        n_freq = len(freqs)
        fig, axes = plt.subplots(1, n_freq, figsize=(3 * n_freq, 4), sharey=True)
        if n_freq == 1:
            axes = [axes]
        for ax, freq in zip(axes, freqs):
            sub = df[df["Frequency"] == freq]
            for i, g in enumerate(genos):
                pts  = sub[sub["Genotype"] == g]["DeltaRate_Hz"].dropna().values
                mean = pts.mean() if len(pts) else 0
                sem  = pts.std() / np.sqrt(len(pts)) if len(pts) > 1 else 0
                ax.bar(i, mean, yerr=sem, capsize=4,
                       color=colors[g], edgecolor="k", linewidth=0.7)
                ax.scatter([i] * len(pts), pts,
                           color="k", s=14, zorder=3, alpha=0.6)
            ax.axhline(0, color="k", linewidth=0.8, linestyle="--")
            ax.set_title(freq, fontsize=9)
            ax.set_xticks(range(len(genos)))
            ax.set_xticklabels(genos, rotation=30, ha="right", fontsize=8)
        axes[0].set_ylabel("ΔFiring Rate (Hz)", fontsize=10)
        fig.suptitle("dF/F by Frequency & Genotype", fontsize=12)
        plt.tight_layout()
        out = os.path.join(out_dir, "bar_dff_per_frequency.png")
        fig.savefig(out, dpi=150)
        self._update_canvas(fig)
        plt.close(fig)
        return out

    def _plot_heatmap(self, df: pd.DataFrame, out_dir: str) -> str:
        genos = sorted(df["Genotype"].unique())
        freqs = ["AllSounds"] + [f for f in FREQ_LABELS if f in df["Frequency"].values]
        chans = sorted(df["Channel"].unique())
        if not chans or not freqs:
            return ""
        n_geno = len(genos)
        fig, axes = plt.subplots(
            1, n_geno,
            figsize=(len(freqs) * 0.8 * n_geno + 1, len(chans) * 0.35 + 2),
            sharey=True)
        if n_geno == 1:
            axes = [axes]
        vmin = df["DeltaRate_Hz"].quantile(0.05)
        vmax = df["DeltaRate_Hz"].quantile(0.95)
        for ax, g in zip(axes, genos):
            sub = df[df["Genotype"] == g]
            mat = np.full((len(chans), len(freqs)), np.nan)
            for ci, ch in enumerate(chans):
                for fi, freq in enumerate(freqs):
                    cell = sub[(sub["Channel"] == ch) &
                               (sub["Frequency"] == freq)]["DeltaRate_Hz"]
                    if not cell.empty:
                        mat[ci, fi] = cell.mean()
            im = ax.imshow(mat, aspect="auto", cmap="RdBu_r",
                           vmin=vmin, vmax=vmax, interpolation="nearest")
            ax.set_title(g, fontsize=10)
            ax.set_xticks(range(len(freqs)))
            ax.set_xticklabels(freqs, rotation=45, ha="right", fontsize=7)
            ax.set_yticks(range(len(chans)))
            ax.set_yticklabels([f"Ch{c}" for c in chans], fontsize=7)
        fig.colorbar(im, ax=axes[-1], label="ΔRate (Hz)", fraction=0.046, pad=0.04)
        fig.suptitle("Population Heatmap – ΔFiring Rate", fontsize=12)
        plt.tight_layout()
        out = os.path.join(out_dir, "population_heatmap.png")
        fig.savefig(out, dpi=150)
        self._update_canvas(fig)
        plt.close(fig)
        return out

    # ── Canvas update ─────────────────────────────────────────────────────────

    def _update_canvas(self, fig):
        self.fig = fig
        self.canvas.figure = fig
        fig.canvas = self.canvas
        self.canvas.draw()

    # ── Status ────────────────────────────────────────────────────────────────

    def _set_status(self, msg: str, color: str):
        self.lbl_status.setText(msg)
        self.lbl_status.setStyleSheet(
            f"color: {color}; padding: 4px; font-style: italic;")
