# Product Requirements Document (PRD): Ephys Analysis Platform

## 1. Project Overview
The software is evolving from a lightweight visual diagnostic tool (EphysInspector) into a comprehensive Ephys Analysis Platform. It provides a multi-tab workstation for ground-truth visual validation of spike-sorting results, experimental data analysis, quality inspection of analyzed data, and automated generation of publication-ready graphs (replacing Graphpad). 

## 2. Target Data Architecture
*   **Source:** In vivo electrophysiology (Anesthetized mice).
*   **Region:** Tail of Striatum.
*   **File Types:**
    *   `.dat`: Raw continuous binary data (int16/float32).
    *   `.prm`: JRCLUST parameter file.
    *   `res.m` / `res.mat`: Spike detection results from Tab 1.
    *   Metadata: TTL timestamps for sound presentations (e.g., 400ms sounds, 600ms ISI).

## 3. Multi-Tab Architecture and Functional Requirements

### Tab 1: Ephys Inspector (Spike Detection)
*   **Functionality:** Interactive workstation for manual spike detection via thresholding.
*   **Input:** Raw `.dat` files and `.prm` files.
*   **Outputs:** Detected spikes and thresholds saved as `res.m` (or `res.mat`), which feed directly into Tab 2.
*   **Key Features:** Raw trace viewer, interactive threshold lines, signal highlighting.

### Tab 2: Run Analysis
*   **Functionality:** Process thresholded data based on the experimental protocol. Outputs are saved into a "Figures" folder structure within the respective `.dat` folder.
*   **Protocols:**
    *   **Auditory Protocol (e.g., `SR_MUA_TS_TTLperAudio_2.m`):**
        *   **Inputs:** Genotype, Animal Number.
        *   **Editable Parameters:** 
            *   Sound time analysis window (e.g., 400ms, 200ms, 100ms).
            *   Baseline period duration (e.g., 3 minutes or 1 minute before the first TTL).
        *   **Quantification:** dF/F signal changes comparing the chosen sound analysis window to the equivalent time window immediately preceding the sound.
    *   **Baseline Protocol (e.g., `SR_MUA_TS_Time_PSTH`):**
        *   **Functionality:** Generates Peristimulus Time Histograms (PSTH).
        *   **Data Handling:** Can handle varying recording lengths, including specific 1-minute recordings (immediately post-drug injection) and 30-minute recordings (30 mins post-drug).
        *   **Output:** Generates Excel data sheets for these recordings.

### Tab 3: Analysis Inspection (Channel Selection)
*   **Functionality:** Quality control visualizer for the analyzed data, channel by channel.
*   **Visualizations:** For each channel, displays:
    1.  Raw Data Trace
    2.  Raster Plots
    3.  PSTH
*   **User Action:** The user selectively marks which channels exhibit good physiological responses to be included in the final population analysis.
*   **Output:** Saves an Excel file in the "Figures" folder documenting the selected channels for future reference and for Tab 4 filtering.

### Tab 4: Results (Graphing & Visualization)
*   **Functionality:** Aggregates data across animals and generates statistical figures, replacing the need for GraphPad Prism.
*   **Data Ingestion:** Loads analyzed metafiles and filters the dataset using the selected channels from Tab 3. Sorts animals by genotype.
*   **Graph Types:**
    1.  **PSTH Graphs (All Sounds):** Change from baseline across different genotypes for all sounds combined.
    2.  **PSTH Graphs (By Frequency):** Similar to above, but separated by sound frequencies.
    3.  **Bar Graphs (dF/F):** dF/F for each channel per genotype. Includes an "All Sounds" aggregate graph and frequency-specific graphs.
    4.  **Population Graphs:** Heatmaps demonstrating population-level activity across channels/animals, or other population density representations.

## 4. Technical Specifications
*   **Language:** Python 3.9+.
*   **GUI Framework:** PyQt6/PySide6 (multi-tab support) or similar.
*   **Data Processing:** Pandas (for Excel exporting and metadata management), NumPy (fast matrix operations).
*   **Visualization:** PyQtGraph (for fast scrolling raw data/rasters), Matplotlib/Seaborn (for static publication graphs in Tab 4).

## 5. Success Criteria
*   Seamless data flow from Tab 1 to Tab 4 without requiring external file manipulation by the user.
*   Accurate reproduction of MATLAB script logic (`SR_MUA_TS_TTLperAudio_2.m` and `SR_MUA_TS_Time_PSTH`).
*   Clear differentiation of data structures in the output folders (e.g., "Figures").
*   Robust channel filtering resulting in clean, publication-ready graphs in the Results tab.
