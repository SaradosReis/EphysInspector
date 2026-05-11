import sys
import os
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                               QPushButton, QFileDialog, QLabel, QSlider, QComboBox, 
                               QSpinBox, QDoubleSpinBox, QGroupBox, QRadioButton)
from PySide6.QtCore import Qt, Signal
import pyqtgraph as pg
import numpy as np

from data_loader import DataLoader
from processor import Processor

class CustomViewBox(pg.ViewBox):
    def __init__(self, *args, **kwds):
        super().__init__(*args, **kwds)
        
    def wheelEvent(self, ev, axis=None):
        # Explicitly ignore scroll wheel events to prevent accidental zooming
        pass

class EphysViewer(QWidget):
    detection_finished = Signal()
    
    def __init__(self, app_state):
        super().__init__()
        self.app_state = app_state

        self.data_loader = DataLoader()
        self.processor = Processor()

        # Data state
        self.sample_rate = 30000.0
        self.n_chans = 1
        self.bit_scaling = 1.0
        self.site_map = []
        self.shank_map = []
        self.dat_path = None
        self.raw_data = None
        self.spikes = {}
        self.ttls = None
        self.total_samples = 0
        
        self.y_offset_step = 1000  # uV offset between channels
        self.current_time_s = 0.0

        # Spike detection state
        self.thresholds_enabled = False
        self.manual_thresholds = {}  # Map of site_idx -> threshold (in raw uV, relative to 0)
        self.threshold_lines = {}    # Map of site_idx -> pg.InfiniteLine

        self.detection_finished.connect(self.finish_detection)

        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Controls Layout
        controls_layout = QHBoxLayout()
        
        # File Loading Group
        file_group = QGroupBox("Load Data")
        file_layout = QVBoxLayout()
        
        btn_load_dat = QPushButton("Load .dat")
        btn_load_dat.clicked.connect(self.load_dat_file)
        btn_load_prm = QPushButton("Load .prm")
        btn_load_prm.clicked.connect(self.load_prm_file)
        btn_load_mat = QPushButton("Load _res.mat (Spikes)")
        btn_load_mat.clicked.connect(self.load_mat_file)
        btn_load_npy = QPushButton("Load TTLs (.npy)")
        btn_load_npy.clicked.connect(self.load_npy_file)
        
        file_layout.addWidget(btn_load_dat)
        file_layout.addWidget(btn_load_prm)
        file_layout.addWidget(btn_load_mat)
        file_layout.addWidget(btn_load_npy)
        file_group.setLayout(file_layout)
        controls_layout.addWidget(file_group)

        # View Controls Group
        view_group = QGroupBox("Window of Analysis")
        view_layout = QVBoxLayout()
        
        # Time Window Setup
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("Start Time (s):"))
        self.spin_start = QDoubleSpinBox()
        self.spin_start.setRange(0, 1000000.0)
        self.spin_start.setValue(10.0)
        self.spin_start.setSingleStep(1.0)
        time_layout.addWidget(self.spin_start)
        
        time_layout.addWidget(QLabel("End Time (s):"))
        self.spin_end = QDoubleSpinBox()
        self.spin_end.setRange(0.1, 1000000.0)
        self.spin_end.setValue(60.0)
        self.spin_end.setSingleStep(1.0)
        time_layout.addWidget(self.spin_end)
        
        view_layout.addLayout(time_layout)
        
        btn_update = QPushButton("Update Plot")
        btn_update.clicked.connect(self.update_plot)
        view_layout.addWidget(btn_update)
        
        chan_layout = QHBoxLayout()
        chan_layout.addWidget(QLabel("Channel:"))
        
        self.btn_prev_chan = QPushButton("<")
        self.btn_prev_chan.setFixedWidth(30)
        self.btn_prev_chan.clicked.connect(self.prev_channel)
        chan_layout.addWidget(self.btn_prev_chan)
        
        self.combo_channel = QComboBox()
        self.combo_channel.addItem("All Channels")
        self.combo_channel.currentIndexChanged.connect(self.update_plot)
        chan_layout.addWidget(self.combo_channel)
        
        self.btn_next_chan = QPushButton(">")
        self.btn_next_chan.setFixedWidth(30)
        self.btn_next_chan.clicked.connect(self.next_channel)
        chan_layout.addWidget(self.btn_next_chan)
        
        chan_layout.addWidget(QLabel("Spacing (uV):"))
        self.spin_spacing = QSpinBox()
        self.spin_spacing.setRange(10, 5000)
        self.spin_spacing.setValue(200)
        self.spin_spacing.setSingleStep(50)
        self.spin_spacing.valueChanged.connect(self.update_plot)
        chan_layout.addWidget(self.spin_spacing)
        
        view_layout.addLayout(chan_layout)
        
        view_group.setLayout(view_layout)
        controls_layout.addWidget(view_group)

        # Filter Controls Group
        filter_group = QGroupBox("Filter (Hz)")
        filter_layout = QVBoxLayout()
        
        low_layout = QHBoxLayout()
        low_layout.addWidget(QLabel("Low cut:"))
        self.spin_lowcut = QDoubleSpinBox()
        self.spin_lowcut.setRange(1.0, 10000.0)
        self.spin_lowcut.setValue(300.0)
        low_layout.addWidget(self.spin_lowcut)
        filter_layout.addLayout(low_layout)

        high_layout = QHBoxLayout()
        high_layout.addWidget(QLabel("High cut:"))
        self.spin_highcut = QDoubleSpinBox()
        self.spin_highcut.setRange(1.0, 15000.0)
        self.spin_highcut.setValue(3000.0)
        high_layout.addWidget(self.spin_highcut)
        filter_layout.addLayout(high_layout)
        
        filter_group.setLayout(filter_layout)
        controls_layout.addWidget(filter_group)

        # Mouse Mode Group
        mouse_group = QGroupBox("Mouse Tools")
        mouse_layout = QVBoxLayout()
        
        self.btn_pan = QRadioButton("Hand (Pan)")
        self.btn_pan.setChecked(True)
        self.btn_pan.toggled.connect(self.update_mouse_mode)
        
        self.btn_zoom = QRadioButton("Magnifier (Zoom)")
        self.btn_zoom.toggled.connect(self.update_mouse_mode)
        
        mouse_layout.addWidget(self.btn_pan)
        mouse_layout.addWidget(self.btn_zoom)
        mouse_group.setLayout(mouse_layout)
        controls_layout.addWidget(mouse_group)

        # Spike Detection Group
        detect_group = QGroupBox("Spike Detection")
        detect_layout = QVBoxLayout()
        
        self.btn_toggle_thresh = QPushButton("Enable Thresholds")
        self.btn_toggle_thresh.setCheckable(True)
        self.btn_toggle_thresh.toggled.connect(self.toggle_thresholds)
        
        self.btn_run_detect = QPushButton("Run Detection & Save")
        self.btn_run_detect.clicked.connect(self.run_detection)
        self.btn_run_detect.setEnabled(False)  # Enabled when thresholds are active
        
        detect_layout.addWidget(self.btn_toggle_thresh)
        detect_layout.addWidget(self.btn_run_detect)
        detect_group.setLayout(detect_layout)
        controls_layout.addWidget(detect_group)

        layout.addLayout(controls_layout)

        # Plot Widget
        pg.setConfigOptions(antialias=True)
        custom_vb = CustomViewBox()
        self.plot_widget = pg.PlotWidget(viewBox=custom_vb)
        self.plot_widget.setLabel('bottom', "Time", units='s')
        self.plot_widget.setLabel('left', "Amplitude", units='uV')
        
        # Enable mouse interactions explicitly
        self.plot_widget.getViewBox().setMouseEnabled(x=True, y=True)
        self.plot_widget.getViewBox().setMouseMode(pg.ViewBox.PanMode)
        
        layout.addWidget(self.plot_widget)

    def prev_channel(self):
        idx = self.combo_channel.currentIndex()
        if idx > 0:
            self.combo_channel.setCurrentIndex(idx - 1)

    def next_channel(self):
        idx = self.combo_channel.currentIndex()
        if idx < self.combo_channel.count() - 1:
            self.combo_channel.setCurrentIndex(idx + 1)

    def update_mouse_mode(self):
        if self.btn_pan.isChecked():
            self.plot_widget.getViewBox().setMouseMode(pg.ViewBox.PanMode)
        else:
            self.plot_widget.getViewBox().setMouseMode(pg.ViewBox.RectMode)

    def toggle_thresholds(self, checked):
        self.thresholds_enabled = checked
        self.btn_run_detect.setEnabled(checked)
        if checked and len(self.manual_thresholds) == 0:
            # Initialize default thresholds (e.g., -50 uV) for all sites
            for i in range(len(self.site_map)):
                self.manual_thresholds[i] = -50.0
        self.update_plot()

    def run_detection(self):
        if self.raw_data is None:
            print("No data loaded!")
            return
            
        print("Running full spike detection...")
        self.btn_run_detect.setText("Processing...")
        self.btn_run_detect.setEnabled(False)
        self.btn_toggle_thresh.setEnabled(False)
        
        # We need to pass the raw data, thresholds, and filter settings to the processor
        import threading
        
        # Convert manual_thresholds from site_idx -> threshold to physical_chan -> threshold
        phys_thresholds = {}
        for site_idx, thresh in self.manual_thresholds.items():
            phys_chan = self.site_map[site_idx]
            phys_thresholds[phys_chan] = thresh
            
        # Run in background to avoid freezing UI
        def detect_worker():
            try:
                res_dict = self.processor.detect_spikes(
                    raw_data=self.raw_data,
                    sample_rate=self.sample_rate,
                    bit_scaling=self.bit_scaling,
                    site_map=self.site_map,
                    phys_thresholds=phys_thresholds,
                    lowcut=self.spin_lowcut.value(),
                    highcut=self.spin_highcut.value()
                )
                
                # Save to mat file
                import scipy.io
                # The _res.mat file should be in the same dir as the dat file
                if self.dat_path:
                    save_path = os.path.join(os.path.dirname(self.dat_path), "manual_detected_res.mat")
                else:
                    save_path = "manual_detected_res.mat"
                    
                scipy.io.savemat(save_path, res_dict)
                print(f"Done! Saved {len(res_dict['spikeTimes'])} spikes to {save_path}")
                
                # Automatically load the newly detected spikes
                self.spikes = res_dict
                self.app_state['res_mat_path'] = save_path
            except Exception as e:
                print(f"Error during detection: {e}")
            finally:
                # Use thread-safe Signal to update the UI
                self.detection_finished.emit()
                
        threading.Thread(target=detect_worker, daemon=True).start()

    def finish_detection(self):
        self.btn_run_detect.setText("Run Detection & Save")
        self.btn_run_detect.setEnabled(True)
        self.btn_toggle_thresh.setEnabled(True)
        self.update_plot()

    def load_prm_file(self):
        prm_path, _ = QFileDialog.getOpenFileName(self, "Open .prm File", "", "PRM Files (*.prm)")
        if prm_path:
            prm_dict = self.data_loader.parse_prm(prm_path)
            self.sample_rate = prm_dict.get('sampleRate', 30000.0)
            self.n_chans = prm_dict.get('nChans', 1)
            self.bit_scaling = prm_dict.get('bitScaling', 1.0)
            self.site_map = prm_dict.get('siteMap', list(range(1, self.n_chans + 1)))
            self.shank_map = prm_dict.get('shankMap', [1] * len(self.site_map))
            
            self.app_state['prm_path'] = prm_path
            self.app_state['sample_rate'] = self.sample_rate
            self.app_state['n_chans'] = self.n_chans
            self.app_state['site_map'] = self.site_map
            
            # Update channel combo box
            self.combo_channel.clear()
            self.combo_channel.addItem("All Channels")
            for ch in self.site_map:
                self.combo_channel.addItem(f"Channel {ch}")
                
            print(f"Loaded PRM: {self.n_chans} channels, {self.sample_rate} Hz")

    def load_dat_file(self):
        if self.n_chans <= 1 and len(self.site_map) == 0:
            print("Please load the .prm file first to get nChans.")
            return

        dat_path, _ = QFileDialog.getOpenFileName(self, "Open .dat File", "", "DAT Files (*.dat)")
        if dat_path:
            self.dat_path = dat_path
            self.app_state['dat_path'] = dat_path
            self.raw_data = self.data_loader.load_dat(dat_path, self.n_chans)
            self.total_samples = self.raw_data.shape[1]
            duration_s = self.total_samples / self.sample_rate
            
            self.spin_end.setRange(0.1, duration_s)
            self.spin_start.setRange(0, duration_s)
            
            print(f"Loaded DAT: {self.total_samples} samples, {duration_s:.2f} seconds")
            self.update_plot()

    def load_mat_file(self):
        mat_path, _ = QFileDialog.getOpenFileName(self, "Open _res.mat File", "", "MAT Files (*.mat)")
        if mat_path:
            self.spikes = self.data_loader.load_spikes(mat_path)
            self.app_state['res_mat_path'] = mat_path
            print(f"Loaded Spikes: {len(self.spikes.get('spikeTimes', []))} spikes")
            self.update_plot()

    def load_npy_file(self):
        npy_path, _ = QFileDialog.getOpenFileName(self, "Open TTLs .npy File", "", "NPY Files (*.npy)")
        if npy_path:
            self.ttls = self.data_loader.load_ttls(npy_path)
            self.app_state['npy_ttl_path'] = npy_path
            print(f"Loaded TTLs: {len(self.ttls)} events")
            self.update_plot()

    def update_plot(self):
        if self.raw_data is None:
            return

        self.plot_widget.clear()

        # Determine window from user inputs
        start_s = self.spin_start.value()
        end_s = self.spin_end.value()
        if start_s >= end_s: 
            return

        # Read slightly larger chunk to avoid edge filter artifacts (ringing)
        pad_s = 0.5
        load_start_s = max(0, start_s - pad_s)
        load_end_s = end_s + pad_s
        
        load_start_sample = int(load_start_s * self.sample_rate)
        load_end_sample = int(load_end_s * self.sample_rate)
        
        if load_end_sample > self.total_samples: 
            load_end_sample = self.total_samples
        if load_start_sample >= load_end_sample: 
            return

        # Get the padded chunk
        chunk = self.raw_data[:, load_start_sample:load_end_sample].astype(np.float32)
        
        # Apply scaling
        chunk *= self.bit_scaling

        # Detrend the chunk to avoid huge step filter artifacts
        chunk_mean = np.mean(chunk, axis=1, keepdims=True)
        chunk -= chunk_mean

        # Apply filtering
        lowcut = self.spin_lowcut.value()
        highcut = self.spin_highcut.value()
        filtered_chunk = self.processor.bandpass_filter(chunk, self.sample_rate, lowcut, highcut)

        # Slice off the padding to match exactly the user requested window
        plot_start_sample = int(start_s * self.sample_rate)
        plot_end_sample = int(end_s * self.sample_rate)
        if plot_end_sample > self.total_samples: plot_end_sample = self.total_samples

        slice_start = plot_start_sample - load_start_sample
        slice_end = plot_end_sample - load_start_sample
        
        if slice_start < 0: slice_start = 0
        if slice_end > filtered_chunk.shape[1]: slice_end = filtered_chunk.shape[1]

        final_chunk = filtered_chunk[:, slice_start:slice_end]
        n_samples = final_chunk.shape[1]
        
        full_time_axis = np.linspace(plot_start_sample / self.sample_rate, plot_end_sample / self.sample_rate, n_samples)
        full_chunk = final_chunk
        
        # Pre-downsample for performance
        max_display_points = 20000
        if n_samples > max_display_points * 2:
            chunk_size = n_samples // (max_display_points // 2)
            n_chunks = n_samples // chunk_size
            
            fc_trunc = final_chunk[:, :n_chunks * chunk_size]
            ta_trunc = full_time_axis[:n_chunks * chunk_size]
            
            fc_reshaped = fc_trunc.reshape(final_chunk.shape[0], n_chunks, chunk_size)
            mins = fc_reshaped.min(axis=2)
            maxs = fc_reshaped.max(axis=2)
            
            new_chunk = np.empty((final_chunk.shape[0], n_chunks * 2), dtype=final_chunk.dtype)
            new_chunk[:, 0::2] = mins
            new_chunk[:, 1::2] = maxs
            final_chunk = new_chunk
            
            ta_reshaped = ta_trunc.reshape(n_chunks, chunk_size)
            time_axis = np.empty(n_chunks * 2, dtype=full_time_axis.dtype)
            time_axis[0::2] = ta_reshaped[:, 0]
            time_axis[1::2] = ta_reshaped[:, -1]
        else:
            time_axis = full_time_axis

        # Which sites to plot
        sel_idx = self.combo_channel.currentIndex()
        if sel_idx == 0:
            sites_to_plot = range(len(self.site_map))
        else:
            sites_to_plot = [sel_idx - 1] # -1 because 0 is "All Channels"

        y_offset = 0
        
        # Collect spikes for scatter plot
        spike_times_visible = []
        spike_amps_visible = []
        spike_data_visible = []

        self.current_lines = []

        for site_idx in sites_to_plot:
            physical_chan = self.site_map[site_idx]
            physical_row = physical_chan - 1 # 0-indexed row in raw_data
            
            if physical_row >= final_chunk.shape[0]:
                continue
                
            trace = final_chunk[physical_row, :] + y_offset
            self.plot_widget.plot(time_axis, trace, pen=pg.mkPen(color=(150, 150, 200), width=1))
            
            # Label
            text = pg.TextItem(f"Ch {physical_chan}", color=(200, 200, 200))
            self.plot_widget.addItem(text)
            if len(time_axis) > 0:
                text.setPos(time_axis[-1], y_offset)

            # Draw threshold line if enabled
            if self.thresholds_enabled:
                thresh_val = self.manual_thresholds.get(site_idx, -50.0)
                line = pg.InfiniteLine(angle=0, movable=True, pos=y_offset + thresh_val, 
                                       pen=pg.mkPen(color=(255, 100, 100), style=Qt.DashLine))
                self.plot_widget.addItem(line)
                self.current_lines.append((line, site_idx, y_offset))
                
            # Check for spikes in this exact window
            if 'spikeTimes' in self.spikes and 'spikeSites' in self.spikes:
                s_times = self.spikes['spikeTimes']
                s_sites = self.spikes['spikeSites']
                
                # In JRCLUST, spikeSites are 1-indexed. The ID corresponds directly to the siteMap index!
                site_id = site_idx + 1
                
                # Mask for current window and site
                mask = (s_times >= plot_start_sample) & (s_times < plot_end_sample) & (s_sites == site_id)
                visible_s_times = s_times[mask]
                
                for st in visible_s_times:
                    st_sec = st / self.sample_rate
                    idx_in_full_chunk = int(st - plot_start_sample)
                    
                    if 0 <= idx_in_full_chunk < full_chunk.shape[1]:
                        amp = full_chunk[physical_row, idx_in_full_chunk] + y_offset
                        spike_times_visible.append(st_sec)
                        spike_amps_visible.append(amp)
                        spike_data_visible.append((st, physical_row, physical_chan))

            if sel_idx == 0:
                y_offset -= self.spin_spacing.value()

        # Connect threshold lines together so they move in unison per shank
        if self.thresholds_enabled:
            for line, site_idx, base_y in self.current_lines:
                def create_callback(s_idx, b_y, l_ref):
                    def on_dragged(l):
                        new_thresh = l.value() - b_y
                        target_shank = self.shank_map[s_idx] if s_idx < len(self.shank_map) else 1
                        
                        # Update all thresholds on the same shank
                        for site in list(self.manual_thresholds.keys()):
                            site_shank = self.shank_map[site] if site < len(self.shank_map) else 1
                            if site_shank == target_shank:
                                self.manual_thresholds[site] = new_thresh
                                
                        # Update all other lines visually
                        for other_line, other_s_idx, other_base_y in self.current_lines:
                            other_shank = self.shank_map[other_s_idx] if other_s_idx < len(self.shank_map) else 1
                            if other_line != l_ref and other_shank == target_shank:
                                other_line.setValue(other_base_y + new_thresh)
                    return on_dragged
                line.sigDragged.connect(create_callback(site_idx, base_y, line))

        # Plot Spikes
        if spike_times_visible:
            scatter = pg.ScatterPlotItem(x=spike_times_visible, y=spike_amps_visible, size=8, pen=pg.mkPen(None), brush=pg.mkBrush(255, 0, 0, 200), data=spike_data_visible)
            scatter.sigClicked.connect(self.on_spike_clicked)
            self.plot_widget.addItem(scatter)

        # Plot TTLs
        if self.ttls is not None:
            for ttl in self.ttls:
                if plot_start_sample <= ttl < plot_end_sample:
                    ttl_sec = ttl / self.sample_rate
                    vLine = pg.InfiniteLine(angle=90, movable=False, pos=ttl_sec, pen=pg.mkPen('g', width=2, style=Qt.DashLine))
                    self.plot_widget.addItem(vLine)

        # Adjust view limits automatically
        if len(time_axis) > 0:
            self.plot_widget.setXRange(time_axis[0], time_axis[-1], padding=0)
            
            # Set fixed Y range to prevent bouncing/auto-minimizing
            spacing = self.spin_spacing.value()
            if sel_idx == 0:
                y_min = -spacing * (self.n_chans - 0.5)
                y_max = spacing * 0.5
            else:
                y_min = -spacing * 0.5
                y_max = spacing * 0.5
            self.plot_widget.setYRange(y_min, y_max, padding=0)

    def on_spike_clicked(self, plot, points):
        if not points: return
        point = points[0]
        st_sample, physical_row, physical_chan = point.data()
        
        raw_ch_data = self.raw_data[physical_row, :]
        waveform = self.processor.extract_waveform(raw_ch_data, int(st_sample), window_samples=60)
        
        # Apply scaling
        waveform = waveform.astype(np.float32) * self.bit_scaling
        
        self.popup = pg.plot(waveform, title=f"Mean Waveform window (Ch {physical_chan})")
        self.popup.setLabel('bottom', "Samples")
        self.popup.setLabel('left', "Amplitude", units='uV')
        self.popup.resize(400, 300)
