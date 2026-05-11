import numpy as np
from scipy.signal import butter, sosfiltfilt

class Processor:
    def __init__(self):
        pass

    @staticmethod
    def bandpass_filter(data, sample_rate, lowcut=300.0, highcut=3000.0, order=4):
        """
        Apply a Butterworth bandpass filter to the data.
        data: shape (n_channels, n_samples)
        """
        nyq = 0.5 * sample_rate
        low = lowcut / nyq
        high = highcut / nyq
        sos = butter(order, [low, high], btype='band', output='sos')
        
        # Apply filter using sosfiltfilt (forward and backward to avoid phase shift)
        # axis=1 because data shape is (n_channels, n_samples)
        filtered_data = sosfiltfilt(sos, data, axis=1)
        return filtered_data

    @staticmethod
    def extract_waveform(raw_data, spike_time_sample, window_samples=60):
        """
        Extract a window of raw data around the spike time for a single channel.
        raw_data: 1D numpy array of the specific channel's raw data
        spike_time_sample: The index of the spike peak
        window_samples: Total number of samples to extract around the peak (e.g., 60 samples is 2ms at 30kHz)
        """
        half_window = window_samples // 2
        start_idx = spike_time_sample - half_window
        end_idx = spike_time_sample + half_window
        
        # Handle boundaries
        if start_idx < 0:
            start_idx = 0
            end_idx = window_samples
        if end_idx > len(raw_data):
            end_idx = len(raw_data)
            start_idx = end_idx - window_samples
            
        return raw_data[start_idx:end_idx]

    def detect_spikes(self, raw_data, sample_rate, bit_scaling, site_map, phys_thresholds, lowcut, highcut):
        from scipy.signal import find_peaks
        import numpy as np
        
        all_spike_times = []
        all_spike_sites = []
        all_spike_amps = []
        
        n_chans, n_samples = raw_data.shape
        chunk_len = int(sample_rate * 60) # 1 minute chunks
        overlap = int(sample_rate * 0.1) # 100 ms overlap to avoid missing edge spikes
        
        for start_idx in range(0, n_samples, chunk_len):
            end_idx = min(start_idx + chunk_len + overlap, n_samples)
            print(f"Processing chunk {start_idx/sample_rate:.1f}s to {end_idx/sample_rate:.1f}s ...")
            
            # CRITICAL: Slice the contiguous axis first (transpose back, slice, transpose again)
            # This prevents massive disk thrashing when reading from the memmap
            chunk = raw_data.T[start_idx:end_idx, :].T.astype(np.float32)
            chunk *= bit_scaling
            
            # Detrend
            chunk_mean = np.mean(chunk, axis=1, keepdims=True)
            chunk -= chunk_mean
            
            # Filter
            filtered_chunk = self.bandpass_filter(chunk, sample_rate, lowcut, highcut)
            
            # Find spikes per channel
            for site_idx, phys_chan in enumerate(site_map):
                if phys_chan not in phys_thresholds:
                    continue
                
                phys_row = phys_chan - 1
                if phys_row >= n_chans: continue
                
                trace = filtered_chunk[phys_row, :]
                thresh = phys_thresholds[phys_chan]
                
                # We assume negative spikes if thresh is negative
                if thresh < 0:
                    peaks, properties = find_peaks(-trace, height=-thresh, distance=int(sample_rate * 0.001)) # 1ms refractory
                    peak_amps = -properties['peak_heights']
                else:
                    peaks, properties = find_peaks(trace, height=thresh, distance=int(sample_rate * 0.001))
                    peak_amps = properties['peak_heights']
                    
                # Adjust for chunk offset
                global_peaks = peaks + start_idx
                
                # Remove spikes in the overlap region (unless it's the last chunk)
                if end_idx < n_samples:
                    valid_mask = peaks < chunk_len
                    global_peaks = global_peaks[valid_mask]
                    peak_amps = peak_amps[valid_mask]
                    
                if len(global_peaks) > 0:
                    all_spike_times.extend(global_peaks)
                    all_spike_sites.extend([site_idx + 1] * len(global_peaks)) # 1-indexed site_id
                    all_spike_amps.extend(peak_amps)
                    
        # Sort by time
        if len(all_spike_times) > 0:
            sort_idx = np.argsort(all_spike_times)
            sorted_times = np.array(all_spike_times, dtype=np.uint64)[sort_idx]
            sorted_sites = np.array(all_spike_sites, dtype=np.uint32)[sort_idx]
            sorted_amps = np.array(all_spike_amps, dtype=np.float32)[sort_idx]
        else:
            sorted_times = np.array([], dtype=np.uint64)
            sorted_sites = np.array([], dtype=np.uint32)
            sorted_amps = np.array([], dtype=np.float32)
            
        # Format for JRClust _res.mat (column vectors)
        res_dict = {
            'spikeTimes': np.expand_dims(sorted_times, axis=1),
            'spikeSites': np.expand_dims(sorted_sites, axis=1),
            'spikeAmps': np.expand_dims(sorted_amps, axis=1)
        }
        
        return res_dict
