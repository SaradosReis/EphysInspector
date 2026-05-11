from PySide6.QtWidgets import QMainWindow, QTabWidget, QVBoxLayout, QWidget

from viewer import EphysViewer
from tabs.analysis_tab import AnalysisTab
from tabs.inspection_tab import InspectionTab
from tabs.results_tab import ResultsTab

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ephys Analysis Platform")
        self.resize(1200, 800)

        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # Application State for cross-tab communication
        self.app_state = {
            'dat_path': None,
            'prm_path': None,
            'res_mat_path': None,
            'npy_ttl_path': None,
            'sample_rate': 30000.0,
            'n_chans': 1,
            'site_map': []
        }

        # Initialize Tab Widget
        self.tabs = QTabWidget()
        
        # 1. Tab 1: Ephys Inspector (Spike Detection)
        self.viewer_tab = EphysViewer(self.app_state)
        self.tabs.addTab(self.viewer_tab, "1. Spike Detection")

        # 2. Tab 2: Run Analysis
        self.analysis_tab = AnalysisTab(self.app_state)
        self.tabs.addTab(self.analysis_tab, "2. Run Analysis")

        # 3. Tab 3: Analysis Inspection
        self.inspection_tab = InspectionTab(self.app_state)
        self.tabs.addTab(self.inspection_tab, "3. Analysis Inspection")

        # 4. Tab 4: Results
        self.results_tab = ResultsTab(self.app_state)
        self.tabs.addTab(self.results_tab, "4. Results")

        layout.addWidget(self.tabs)
