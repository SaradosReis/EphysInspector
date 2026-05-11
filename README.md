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
  
  -- Type "Python: Create Environment", select "Venv", and choose your Python 3.11

**3. Install all the requirements**
- In your terminal:
  -- cd EphysInspector
  -- pip install -r requirements.txt
  
**4. Open the software**
  -- python main.py

**Ephys Inpsctor**

  <img width="2386" height="1658" alt="image" src="https://github.com/user-attachments/assets/edad1209-f054-4e75-99f1-2cb2d2a4b25d" />
  

  ** Example of thresholding a signal**
  
  <img width="2368" height="1638" alt="image" src="https://github.com/user-attachments/assets/9f9cddc9-cdd8-46cd-ac48-4c3e2aafd4c2" />

  **Run Analysis**

  This part will give you the .m file for the spike detection

  <img width="2378" height="1648" alt="image" src="https://github.com/user-attachments/assets/89d031a8-eeff-4472-a15d-659385c2ac0e" />


  **Analysis Inspection - Data visualization**
  Example of the graphs (PSTH and raster)

  <img width="2338" height="864" alt="image" src="https://github.com/user-attachments/assets/732d6a1a-a716-4323-b4dd-158f50d8bba9" />



 

