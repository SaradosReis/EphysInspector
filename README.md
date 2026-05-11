EphysInspector is a specialized tool developed for the automated inspection and analysis of electrophysiology data. This project focuses on high-performance signal processing and spike detection, specifically optimized for researchers handling large-scale .dat neural recordings.

**Key Aspects**
- Artifact Removal: Efficiently filter out noise and electrical interference.

- Thresholding: Manual thresholder

- Analysis: Baseline and Auditory response PSTH and raster

How to use:
**1. Download the Project**
 - Click the green "Code" button at the top of this page.

- Select "Download ZIP".

- Unzip the folder on your Desktop.

**2. Create an Anaconda or VSCode env**
- Option A:
  -- conda create -n ephys_env python=3.10
  -- conda activate ephys_env

- Option B
  -- Open the folder in VS Code
  -- Press Ctrl + Shift + P (or Cmd + Shift + P on Mac)
  -- Type "Python: Create Environment", select "Venv", and choose your Python version. VS Code will handle the rest!

**3. Install all the requirements**
- In your terminal:
  -- cd EphysInspector
  -- pip install -r requirements.txt
**4. Open the software**
  -- python main.py
