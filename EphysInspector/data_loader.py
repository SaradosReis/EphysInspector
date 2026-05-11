import re
import numpy as np
import scipy.io

class DataLoader:
    def __init__(self):
        self.prm_data = {}
        self.raw_data = None
        self.spikes = {}
        self.ttls = None

    def parse_prm(self, prm_path):
        """Parse JRCLUST .prm file for essential parameters."""
        prm_dict = {}
        with open(prm_path, 'r') as f:
            content = f.read()

        # Extract sampleRate
        match = re.search(r'sampleRate\s*=\s*([\d\.]+);', content)
        if match:
            prm_dict['sampleRate'] = float(match.group(1))

        # Extract nChans
        match = re.search(r'nChans\s*=\s*(\d+);', content)
        if match:
            prm_dict['nChans'] = int(match.group(1))

        # Extract bitScaling
        match = re.search(r'bitScaling\s*=\s*([\d\.]+);', content)
        if match:
            prm_dict['bitScaling'] = float(match.group(1))

        # Extract siteMap
        match = re.search(r'siteMap\s*=\s*\[(.*?)\];', content)
        if match:
            site_map_str = match.group(1)
            site_map = [int(x.strip()) for x in site_map_str.split(',') if x.strip()]
            prm_dict['siteMap'] = site_map

        # Extract shankMap
        match = re.search(r'shankMap\s*=\s*\[(.*?)\];', content)
        if match:
            shank_map_str = match.group(1)
            shank_map = [int(x.strip()) for x in shank_map_str.split(',') if x.strip()]
            prm_dict['shankMap'] = shank_map

        self.prm_data = prm_dict
        return prm_dict

    def load_dat(self, dat_path, n_chans):
        """Load continuous .dat file using memory mapping."""
        # Load the raw memmap
        raw_memmap = np.memmap(dat_path, dtype='int16', mode='r')
        
        # Reshape to (samples, n_chans) and transpose to (n_chans, samples)
        self.raw_data = raw_memmap.reshape(-1, n_chans).T
        return self.raw_data

    def load_spikes(self, res_mat_path):
        """Load JRCLUST _res.mat file."""
        try:
            mat = scipy.io.loadmat(res_mat_path)
            # Flatten arrays for easier indexing later
            self.spikes['spikeTimes'] = mat['spikeTimes'].flatten() if 'spikeTimes' in mat else np.array([])
            self.spikes['spikeSites'] = mat['spikeSites'].flatten() if 'spikeSites' in mat else np.array([])
            self.spikes['spikeAmps'] = mat['spikeAmps'].flatten() if 'spikeAmps' in mat else np.array([])
            return self.spikes
        except NotImplementedError:
            # Fallback for MATLAB v7.3 files
            try:
                import h5py
                with h5py.File(res_mat_path, 'r') as f:
                    self.spikes['spikeTimes'] = np.array(f['spikeTimes']).flatten() if 'spikeTimes' in f else np.array([])
                    self.spikes['spikeSites'] = np.array(f['spikeSites']).flatten() if 'spikeSites' in f else np.array([])
                    self.spikes['spikeAmps'] = np.array(f['spikeAmps']).flatten() if 'spikeAmps' in f else np.array([])
                return self.spikes
            except ImportError:
                print("Error: The _res.mat file is in v7.3 format. Please install h5py (pip install h5py) to load it.")
                return {}
            except Exception as e:
                print(f"Error loading spikes with h5py: {e}")
                return {}
        except Exception as e:
            print(f"Error loading spikes: {e}")
            return {}

    def load_ttls(self, npy_path):
        """Load TTL timestamps from .npy file."""
        try:
            ttls = np.load(npy_path)
            # Typically taking every other TTL to get ON events
            self.ttls = ttls[0::2]
            return self.ttls
        except Exception as e:
            print(f"Error loading TTLs: {e}")
            return None
