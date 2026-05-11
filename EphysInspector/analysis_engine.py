import os
import sys
import numpy as np
import pandas as pd
import scipy.io

# Ensure sibling modules are importable when engine is called from tabs/
_PARENT = os.path.dirname(os.path.abspath(__file__))
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

class AnalysisEngine:
    def __init__(self, app_state):
        self.app_state = app_state
        self.samp_freq = app_state.get('sample_rate', 30000.0)
        self.site_map = app_state.get('site_map', [])
        
    def _load_mat(self, res_mat: str) -> dict:
        """Load _res.mat with h5py fallback for MATLAB v7.3 format."""
        try:
            return scipy.io.loadmat(res_mat)
        except NotImplementedError:
            try:
                import h5py
                out = {}
                with h5py.File(res_mat, 'r') as f:
                    for key in ('spikeTimes', 'spikeSites', 'spikeAmps'):
                        if key in f:
                            out[key] = np.array(f[key]).flatten()
                return out
            except ImportError:
                raise Exception(
                    "This _res.mat is MATLAB v7.3 format. "
                    "Install h5py (`pip install h5py`) to load it.")

    def _load_data(self):
        res_mat = self.app_state.get('res_mat_path')
        if not res_mat or not os.path.exists(res_mat):
            raise Exception("No spike detection results (_res.mat) loaded.")

        spikes     = self._load_mat(res_mat)
        spike_times = np.array(spikes.get('spikeTimes', [])).flatten()
        spike_sites = np.array(spikes.get('spikeSites', [])).flatten()
        spike_amps  = np.array(spikes.get('spikeAmps',  [])).flatten()

        # Load TTLs
        ttls_path = self.app_state.get('npy_ttl_path')
        if not ttls_path or not os.path.exists(ttls_path):
            ttls_data = np.array([])
        else:
            ttls_data = np.load(ttls_path).flatten()

        return spike_times, spike_sites, spike_amps, ttls_data

    def get_figures_dir(self):
        dat_path = self.app_state.get('dat_path')
        if not dat_path:
            raise Exception("No .dat file path in app state to determine Figures directory.")
        base_dir = os.path.dirname(dat_path)
        fig_dir = os.path.join(base_dir, 'Figures')
        os.makedirs(fig_dir, exist_ok=True)
        return fig_dir

    def run_auditory_protocol(self, genotype, animal_num, window_ms, baseline_min,
                               seq_csv_path, progress_cb=None):
        spike_times, spike_sites, spike_amps, ttls_data = self._load_data()
        
        if len(ttls_data) == 0:
            raise Exception("No TTLs found for Auditory Protocol.")
            
        # MATLAB script ignores first 2 TTLs typically
        if len(ttls_data) > 2:
            events_ttl_on = ttls_data[::2] # assuming interleaved ON/OFF or similar?
            # Actually, the python ttl loader usually just gets the timestamps. We'll use all loaded ttls for now.
            ttls_sec = ttls_data / self.samp_freq
        else:
            ttls_sec = ttls_data / self.samp_freq

        fig_dir = self.get_figures_dir()
        quant_dir = os.path.join(fig_dir, f'Quantification_{window_ms}ms')
        os.makedirs(quant_dir, exist_ok=True)

        stim_window_s = window_ms / 1000.0
        pre_window_s = stim_window_s
        baseline_window_s = baseline_min * 60.0

        freq_code = []
        if seq_csv_path and os.path.exists(seq_csv_path):
            try:
                # Load flat CSV
                freq_code = pd.read_csv(seq_csv_path, header=None).values.flatten()
            except Exception as e:
                print(f"Failed to load seq csv: {e}")
        
        freq_labels = ['8Hz','12Hz','16Hz','20Hz','24Hz','28Hz','WN','WNcrescendo']
        freq_values = np.arange(2, 10)
        
        # Limit TTLs to the length of freq_codes if needed (like MATLAB)
        if len(freq_code) > 0:
            n_ttls = min(len(ttls_sec), len(freq_code))
            ttls_sec = ttls_sec[:n_ttls]
            freq_code = freq_code[:n_ttls]
            
        n_trials = len(ttls_sec)

        # Process each channel
        for i, site_id in enumerate(self.site_map):
            # site_id is 1-indexed in MATLAB, we assume spike_sites is 1-indexed too if coming from JRCLUST
            # Actually if we generate it in Python, we might be using 1-indexed for compatibility
            real_chan = site_id
            
            mask = (spike_sites == (i + 1))
            sp_times_sec = spike_times[mask] / self.samp_freq
            sp_amps_ch = spike_amps[mask]
            
            # 1. Global Metrics
            # Baseline before 1st TTL
            if n_trials > 0:
                base_start = ttls_sec[0] - baseline_window_s
                base_end = ttls_sec[0]
                base_mask = (sp_times_sec >= base_start) & (sp_times_sec < base_end)
                base_count = np.sum(base_mask)
                base_rate = base_count / baseline_window_s if baseline_window_s > 0 else 0
                base_amp = np.nanmean(np.abs(sp_amps_ch[base_mask])) if base_count > 0 else np.nan
                
                stim_count = 0
                pre_count = 0
                all_stim_amps = []
                
                for t0 in ttls_sec:
                    in_stim = (sp_times_sec >= t0) & (sp_times_sec < t0 + stim_window_s)
                    in_pre = (sp_times_sec >= (t0 - pre_window_s)) & (sp_times_sec < t0)
                    
                    stim_count += np.sum(in_stim)
                    pre_count += np.sum(in_pre)
                    if np.any(in_stim):
                        all_stim_amps.extend(np.abs(sp_amps_ch[in_stim]))
                        
                total_stim_time = n_trials * stim_window_s
                total_pre_time = n_trials * pre_window_s
                
                stim_rate = stim_count / total_stim_time if total_stim_time > 0 else 0
                pre_rate = pre_count / total_pre_time if total_pre_time > 0 else 0
                stim_amp = np.nanmean(all_stim_amps) if len(all_stim_amps) > 0 else np.nan
                delta_rate = stim_rate - pre_rate
                
                global_df = pd.DataFrame([{
                    'BaselineSpikeCount': base_count,
                    'BaselineFiringRate_Hz': base_rate,
                    'BaselineAmplitude_uV': base_amp,
                    f'Stim{window_ms}ms_SpikeCount': stim_count,
                    f'Stim{window_ms}ms_FiringRate_Hz': stim_rate,
                    f'Stim{window_ms}ms_Amplitude_uV': stim_amp,
                    'DeltaRate_Hz': delta_rate
                }])
                
                # 2. Per Frequency Metrics
                freq_results = []
                if len(freq_code) > 0:
                    for f_val, f_lbl in zip(freq_values, freq_labels):
                        trial_idx = np.where(freq_code == f_val)[0]
                        if len(trial_idx) == 0:
                            continue
                            
                        f_stim_count = 0
                        f_pre_count = 0
                        f_stim_amps = []
                        
                        for t in trial_idx:
                            t0 = ttls_sec[t]
                            in_stim = (sp_times_sec >= t0) & (sp_times_sec < t0 + stim_window_s)
                            in_pre = (sp_times_sec >= (t0 - pre_window_s)) & (sp_times_sec < t0)
                            
                            f_stim_count += np.sum(in_stim)
                            f_pre_count += np.sum(in_pre)
                            if np.any(in_stim):
                                f_stim_amps.extend(np.abs(sp_amps_ch[in_stim]))
                                
                        f_total_stim_time = len(trial_idx) * stim_window_s
                        f_total_pre_time = len(trial_idx) * pre_window_s
                        
                        f_stim_rate = f_stim_count / f_total_stim_time if f_total_stim_time > 0 else 0
                        f_pre_rate = f_pre_count / f_total_pre_time if f_total_pre_time > 0 else 0
                        f_stim_amp = np.nanmean(f_stim_amps) if len(f_stim_amps) > 0 else np.nan
                        f_delta = f_stim_rate - f_pre_rate
                        
                        freq_results.append({
                            'Frequency': f_lbl,
                            'SpikeCount': f_stim_count,
                            'FiringRate_Hz': f_stim_rate,
                            'Amplitude_uV': f_stim_amp,
                            'DeltaRate_Hz': f_delta
                        })
                
                freq_df = pd.DataFrame(freq_results)
                
                # Write to Excel
                out_path = os.path.join(quant_dir, f'Ch{real_chan}_Quantification.xlsx')
                with pd.ExcelWriter(out_path) as writer:
                    global_df.to_excel(writer, sheet_name='GlobalMetrics', index=False)
                    if not freq_df.empty:
                        freq_df.to_excel(writer, sheet_name='PerFrequency', index=False)
        
        # ── Save raster / PSTH figures ──────────────────────────────────────
        self._save_figures_auditory(
            spike_times=spike_times,
            spike_sites=spike_sites,
            ttls_sec=ttls_sec,
            freq_code=freq_code,
            freq_labels=freq_labels,
            freq_values=freq_values,
            fig_dir=fig_dir,
            progress_cb=progress_cb,
        )
                        
        print(f"Auditory Protocol Analysis complete. Results saved in {fig_dir}")

    # ────────────────────────────────────────────────────────────────────────
    # Figure generation  (matches MATLAB SR_MUA_TS_TTLperAudio_2.m structure)
    # ────────────────────────────────────────────────────────────────────────

    def _save_figures_auditory(self, spike_times, spike_sites, ttls_sec,
                               freq_code, freq_labels, freq_values,
                               fig_dir, progress_cb=None):
        """
        Generate and save all raster / PSTH figures to the Figures/ folder,
        reproducing the exact directory structure of the MATLAB script.

        Folder layout created:
          Figures/
            raster/                            raster_chan{N}.png
            PSTH/                              psth_chan{N}.png
            frequencies/
              raster_frequencies/              raster_chan{N}_freq{code}.png
              psth_frequencies/                psth_chan{N}_freq{code}.png
              Freq_rasters/                    raster_Frequency_chan{N}.png
              raster_heatmap_firingrate/       raster_FR_heatmap_chan{N}.png
        """
        import matplotlib
        matplotlib.use('Agg')          # non-interactive backend for threading
        import matplotlib.pyplot as plt
        from scipy.ndimage import gaussian_filter1d

        n_chans = len(self.site_map)
        sr      = self.samp_freq

        # ── PSTH parameters (matching MATLAB) ─────────────────────────────
        WIN_S       = 1.0    # ± 1 s window
        BIN_S       = 0.010  # 10 ms bins
        SMOOTH_MS   = 25.0   # Gaussian σ in ms  → σ in bins = 25/10 = 2.5
        sigma_bins  = SMOOTH_MS / (BIN_S * 1000.0)
        bin_edges   = np.arange(-WIN_S, WIN_S + BIN_S, BIN_S)
        bin_centers = bin_edges[:-1] + BIN_S / 2.0
        n_bins      = len(bin_centers)
        bl_mask     = bin_centers < 0          # pre-stimulus bins

        # TTLs: skip first 2 like MATLAB (for synchronisation marks)
        valid_ttls = ttls_sec[2:] if len(ttls_sec) > 2 else ttls_sec
        n_trials   = len(valid_ttls)

        has_freq = len(freq_code) > 0

        # ── Create all subdirectories ─────────────────────────────────────
        raster_dir   = os.path.join(fig_dir, 'raster')
        psth_dir     = os.path.join(fig_dir, 'PSTH')
        freq_dir     = os.path.join(fig_dir, 'frequencies')
        rf_dir       = os.path.join(freq_dir, 'raster_frequencies')
        pf_dir       = os.path.join(freq_dir, 'psth_frequencies')
        fr_dir       = os.path.join(freq_dir, 'Freq_rasters')
        hm_dir       = os.path.join(freq_dir, 'raster_heatmap_firingrate')

        for d in [raster_dir, psth_dir]:
            os.makedirs(d, exist_ok=True)
        if has_freq:
            for d in [rf_dir, pf_dir, fr_dir, hm_dir]:
                os.makedirs(d, exist_ok=True)

        # ── Helper: build per-channel spike-time array ────────────────────
        def ch_sp_sec(site_idx):
            mask = (spike_sites == (site_idx + 1))   # 1-based JRCLUST index
            return spike_times[mask] / sr

        # ── Helper: compute PSTH matrix (trials × bins) ───────────────────
        def build_psth_matrix(sp_sec, ttl_subset):
            """Returns (n_trials, n_bins) rate matrix, baseline-subtracted."""
            n = len(ttl_subset)
            if n == 0 or len(sp_sec) == 0:
                return np.zeros((max(n, 1), n_bins))
            M = np.zeros((n, n_bins))
            for ti, t0 in enumerate(ttl_subset):
                in_w = (sp_sec >= t0 - WIN_S) & (sp_sec <= t0 + WIN_S)
                if not np.any(in_w):
                    continue
                rel = sp_sec[in_w] - t0
                cnts, _ = np.histogram(rel, bins=bin_edges)
                M[ti]   = cnts / BIN_S           # convert to Hz
            # per-trial baseline subtraction
            if np.any(bl_mask):
                M = M - M[:, bl_mask].mean(axis=1, keepdims=True)
            return M

        # ── Helper: smooth + SEM → PSTH plot ─────────────────────────────
        def plot_psth(ax, M, title_str):
            mean_r = M.mean(axis=0)
            sem_r  = M.std(axis=0) / np.sqrt(max(M.shape[0], 1))
            mean_sm = gaussian_filter1d(mean_r, sigma=sigma_bins)
            sem_sm  = gaussian_filter1d(sem_r,  sigma=sigma_bins)
            ax.fill_between(bin_centers,
                            mean_sm - sem_sm, mean_sm + sem_sm,
                            color=(0.8, 0.8, 1.0), alpha=0.4, linewidth=0)
            ax.plot(bin_centers, mean_sm, color=(0, 0, 0.5), linewidth=1.5)
            ax.axvline(0, color='r', linestyle='--', linewidth=1)
            ax.set_title(title_str, fontsize=9)
            ax.set_xlabel('Time (s)', fontsize=8)
            ax.set_ylabel('ΔRate (Hz)', fontsize=8)
            ax.set_xlim(bin_edges[0], bin_edges[-1])

        # ─────────────────────────────────────────────────────────────────
        # MAIN LOOP over channels
        # ─────────────────────────────────────────────────────────────────
        for i, real_chan in enumerate(self.site_map):
            if progress_cb:
                progress_cb(i + 1, n_chans, real_chan)

            sp_sec = ch_sp_sec(i)

            # ===========================================================
            # 1.  RASTER – all TTLs combined
            # ===========================================================
            fig, ax = plt.subplots(figsize=(6, max(3, n_trials * 0.05 + 2)))
            for tri, t0 in enumerate(valid_ttls, start=1):
                in_w = (sp_sec >= t0 - WIN_S) & (sp_sec <= t0 + WIN_S)
                rel  = sp_sec[in_w] - t0
                if len(rel):
                    ax.scatter(rel, [tri] * len(rel),
                               marker='s', color='k', s=4, linewidths=0)
            ax.axvline(0, color='r', linestyle='--', linewidth=1)
            ax.set_xlim(-WIN_S, WIN_S)
            ax.set_ylim(0, n_trials + 1)
            ax.set_title(f'Raster – Channel {real_chan}', fontsize=10)
            ax.set_xlabel('Time (s)')
            ax.set_ylabel('Trial')
            fig.tight_layout()
            fig.savefig(os.path.join(raster_dir, f'raster_chan{real_chan}.png'), dpi=120)
            plt.close(fig)

            # ===========================================================
            # 2.  PSTH – all TTLs combined
            # ===========================================================
            if n_trials > 0:
                M   = build_psth_matrix(sp_sec, valid_ttls)
                fig, ax = plt.subplots(figsize=(5, 2.5))
                plot_psth(ax, M, f'PSTH – Ch {real_chan}')
                fig.tight_layout()
                fig.savefig(os.path.join(psth_dir, f'psth_chan{real_chan}.png'), dpi=120)
                plt.close(fig)

            # ===========================================================
            # 3–6.  Frequency-resolved figures (only if random_sequence loaded)
            # ===========================================================
            if not has_freq:
                continue

            # aligned TTLs for freq analysis (no skip-first-2 needed here
            # because freq_code already maps 1-to-1 with trimmed ttls_sec)
            ttls_freq = ttls_sec[:len(freq_code)]

            # ── 3. Per-frequency rasters + PSTHs ────────────────────────
            for f_val, f_lbl in zip(freq_values, freq_labels):
                trial_idx = np.where(freq_code == f_val)[0]
                if len(trial_idx) == 0:
                    continue
                ttls_f   = ttls_freq[trial_idx]
                n_trials_f = len(ttls_f)

                # Raster
                fig, ax = plt.subplots(figsize=(6, max(3, n_trials_f * 0.08 + 2)))
                for tri, t0 in enumerate(ttls_f, start=1):
                    in_w = (sp_sec >= t0 - WIN_S) & (sp_sec <= t0 + WIN_S)
                    rel  = sp_sec[in_w] - t0
                    if len(rel):
                        ax.scatter(rel, [tri] * len(rel),
                                   marker='.', color='k', s=5, linewidths=0)
                ax.axvline(0, color='r', linestyle='--', linewidth=1)
                ax.set_xlim(-WIN_S, WIN_S)
                ax.set_ylim(0.5, n_trials_f + 0.5)
                ax.set_title(f'Raster – {f_lbl} – Ch {real_chan}', fontsize=9)
                ax.set_xlabel('Time (s)')
                ax.set_ylabel('Trial')
                fig.tight_layout()
                fig.savefig(os.path.join(rf_dir,
                    f'raster_chan{real_chan}_freq{f_val}.png'), dpi=120)
                plt.close(fig)

                # PSTH
                M_f = build_psth_matrix(sp_sec, ttls_f)
                fig, ax = plt.subplots(figsize=(5, 2.5))
                plot_psth(ax, M_f, f'PSTH – {f_lbl} – Ch {real_chan}')
                fig.tight_layout()
                fig.savefig(os.path.join(pf_dir,
                    f'psth_chan{real_chan}_freq{f_val}.png'), dpi=120)
                plt.close(fig)

            # ── 4. Combined frequency raster (all freqs, stacked) ────────
            fig, ax = plt.subplots(figsize=(7, 9))
            trial_counter = 1
            ytick_pos, ytick_lab, sep_lines = [], [], []

            for f_val, f_lbl in zip(freq_values, freq_labels):
                trial_idx  = np.where(freq_code == f_val)[0]
                if len(trial_idx) == 0:
                    continue
                ttls_f     = ttls_freq[trial_idx]
                start_row  = trial_counter

                for t0 in ttls_f:
                    in_w = (sp_sec >= t0 - WIN_S) & (sp_sec <= t0 + WIN_S)
                    rel  = sp_sec[in_w] - t0
                    if len(rel):
                        ax.scatter(rel, [trial_counter] * len(rel),
                                   marker='.', color='k', s=3, linewidths=0)
                    trial_counter += 1

                mid = (start_row + trial_counter - 1) / 2.0
                ytick_pos.append(mid)
                ytick_lab.append(f_lbl)
                sep_lines.append(trial_counter - 0.5)

            for yl in sep_lines[:-1]:
                ax.axhline(yl, color='gray', linewidth=0.5)
            ax.axvline(0, color='r', linestyle='--', linewidth=1)
            ax.set_xlim(-WIN_S, WIN_S)
            ax.set_ylim(0.5, trial_counter - 0.5)
            ax.set_xlabel('Time (s)')
            ax.set_ylabel('Trial')
            ax.set_title(f'Frequency Raster – Ch {real_chan}', fontsize=10)

            ax2 = ax.twinx()
            ax2.set_ylim(ax.get_ylim())
            ax2.set_yticks(ytick_pos)
            ax2.set_yticklabels(ytick_lab, fontsize=7)
            ax2.set_ylabel('Frequency')

            fig.tight_layout()
            fig.savefig(os.path.join(fr_dir,
                f'raster_Frequency_chan{real_chan}.png'), dpi=120)
            plt.close(fig)

            # ── 5. Firing-rate heatmap (trials × time bins) ──────────────
            HM_BIN_S = 0.1   # 100 ms bins for heatmap
            hm_edges   = np.arange(-WIN_S, WIN_S + HM_BIN_S, HM_BIN_S)
            hm_centers = hm_edges[:-1] + HM_BIN_S / 2.0

            hm_rows, hm_freq_ids = [], []
            trial_counter = 1
            ytick_pos, ytick_lab, sep_lines = [], [], []

            for fi, (f_val, f_lbl) in enumerate(zip(freq_values, freq_labels)):
                trial_idx = np.where(freq_code == f_val)[0]
                if len(trial_idx) == 0:
                    continue
                ttls_f    = ttls_freq[trial_idx]
                start_row = trial_counter

                for t0 in ttls_f:
                    in_w = (sp_sec >= t0 - WIN_S) & (sp_sec <= t0 + WIN_S)
                    rel  = sp_sec[in_w] - t0
                    cnts, _ = np.histogram(rel, bins=hm_edges)
                    hm_rows.append(cnts / HM_BIN_S)
                    hm_freq_ids.append(fi)
                    trial_counter += 1

                mid = (start_row + trial_counter - 1) / 2.0
                ytick_pos.append(mid)
                ytick_lab.append(f_lbl)
                sep_lines.append(trial_counter - 0.5)

            if hm_rows:
                mat = np.array(hm_rows)
                fig, ax = plt.subplots(figsize=(7, 9))
                im = ax.imshow(mat, aspect='auto', cmap='hot_r',
                               extent=[hm_centers[0], hm_centers[-1],
                                       mat.shape[0] + 0.5, 0.5],
                               interpolation='nearest')
                plt.colorbar(im, ax=ax, label='Firing rate (Hz)')
                ax.axvline(0, color='cyan', linestyle='--', linewidth=1)
                for yl in sep_lines[:-1]:
                    ax.axhline(yl, color='white', linewidth=0.8)
                ax.set_xlabel('Time (s)')
                ax.set_ylabel('Trial')
                ax.set_title(f'Firing Rate Heatmap – Ch {real_chan}', fontsize=10)

                ax2 = ax.twinx()
                ax2.set_ylim(ax.get_ylim())
                ax2.set_yticks(ytick_pos)
                ax2.set_yticklabels(ytick_lab, fontsize=7)
                ax2.set_ylabel('Frequency')

                fig.tight_layout()
                fig.savefig(os.path.join(hm_dir,
                    f'raster_FR_heatmap_chan{real_chan}.png'), dpi=120)
                plt.close(fig)

        print(f"✓ Figures saved to {fig_dir}")

    def run_baseline_protocol(self, genotype, animal_num):
        spike_times, spike_sites, spike_amps, _ = self._load_data()
        
        # Determine total duration (if we have dat_path we can get exact length, else use max spike time)
        duration_s = 0
        dat_path = self.app_state.get('dat_path')
        if dat_path and os.path.exists(dat_path):
            file_size = os.path.getsize(dat_path)
            n_chans = self.app_state.get('n_chans', 1)
            samples = file_size / 2 / n_chans
            duration_s = samples / self.samp_freq
        elif len(spike_times) > 0:
            duration_s = np.max(spike_times) / self.samp_freq
            
        is_short_rec = duration_s < 300 # e.g. 5 mins

        fig_dir = self.get_figures_dir()
        csv_dir = os.path.join(fig_dir, 'IntervalBins_csv')
        os.makedirs(csv_dir, exist_ok=True)

        bin_size_s = 60.0 # 1 minute bins
        
        # We define a single interval from 0 to duration
        t0 = 0
        t1 = duration_s
        edges = np.arange(t0, t1 + bin_size_s, bin_size_s)
        if edges[-1] > t1:
            edges[-1] = t1
            
        bin_centers = (edges[:-1] + edges[1:]) / 2.0
        bin_durations = np.diff(edges)

        summary_rows = []

        for i, site_id in enumerate(self.site_map):
            real_chan = site_id
            mask = (spike_sites == (i + 1))
            sp_times_sec = spike_times[mask] / self.samp_freq
            sp_amps_ch = spike_amps[mask]
            
            counts, _ = np.histogram(sp_times_sec, bins=edges)
            rates = counts / bin_durations
            
            # Optional baseline subtraction? In MATLAB baseline was 0 to 5 mins.
            # If recording is 1min, we don't really have a baseline.
            bl_center = 0
            if not is_short_rec and duration_s >= 300:
                bl_mask = (bin_centers < 300)
                if np.any(bl_mask):
                    bl_center = np.mean(rates[bl_mask])
            else:
                bl_center = np.mean(rates) # Just use overall mean for short recs
                
            delta = rates - bl_center
            
            df = pd.DataFrame({
                'Time_s': bin_centers,
                'Value': rates,
                'Interval': ['recording'] * len(rates),
                'Channel': [real_chan] * len(rates),
                'OutputKind': ['rate'] * len(rates),
                'DeltaFromBL': delta
            })
            
            out_file = os.path.join(csv_dir, f'interval_bins_rate_chan{real_chan}.csv')
            df.to_csv(out_file, index=False)
            
            # Calculate summary (first 5 min vs last 5 min)
            if not is_short_rec:
                in_first5 = sp_times_sec < 300
                in_last5 = sp_times_sec >= (duration_s - 300)
                
                fr_f5 = np.sum(in_first5) / 300.0
                fr_l5 = np.sum(in_last5) / 300.0
                amp_f5 = np.nanmean(np.abs(sp_amps_ch[in_first5])) if np.any(in_first5) else np.nan
                amp_l5 = np.nanmean(np.abs(sp_amps_ch[in_last5])) if np.any(in_last5) else np.nan
            else:
                fr_f5 = np.sum(sp_times_sec) / duration_s
                fr_l5 = fr_f5
                amp_f5 = np.nanmean(np.abs(sp_amps_ch)) if len(sp_amps_ch) > 0 else np.nan
                amp_l5 = amp_f5
                
            summary_rows.append({
                'Channel': real_chan,
                'FR_first5min_Hz': fr_f5,
                'FR_last5min_Hz': fr_l5,
                'Amp_first5min': amp_f5,
                'Amp_last5min': amp_l5
            })

        if summary_rows:
            sum_df = pd.DataFrame(summary_rows)
            sum_df.to_csv(os.path.join(csv_dir, 'summary_5min_FiringRates.csv'), index=False)
            
        print(f"Baseline Protocol Analysis complete. Results saved in {csv_dir}")
