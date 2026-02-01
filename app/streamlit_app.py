"""
Phased Array Systems - Interactive Demo

A Streamlit application showcasing the phased-array-systems Python package
for antenna system design, optimization, and performance visualization.
"""

import streamlit as st

st.set_page_config(
    page_title="Phased Array Systems",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Main page content
st.title("📡 Phased Array Systems")
st.markdown("### Interactive Design & Analysis Tools")

st.markdown("""
Welcome to the **phased-array-systems** interactive demo! This application
showcases the capabilities of the Python package for phased array antenna
system design, optimization, and performance visualization.

---
""")

# Feature cards
col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    #### Key Features

    - **Model-Based Workflow**: MBSE/MDAO approach from requirements through optimized designs
    - **Requirements-Driven**: Every evaluation produces pass/fail with margins and traceability
    - **Trade-Space Exploration**: DOE generation and Pareto analysis for systematic design exploration
    - **Dual Application**: Supports both communications link budgets and radar detection scenarios
    """)

with col2:
    st.markdown("""
    #### Core Models

    - **Antenna**: Phased array gain, beamwidth, sidelobes, scan loss
    - **Communications**: Link budget, EIRP, path loss, SNR margins
    - **Radar**: Range equation, detection probability, integration gain
    - **RF Cascade**: Noise figure, IIP3, SFDR, MDS calculations
    """)

st.divider()

# Demo pages
st.markdown("## Demo Pages")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown("""
    ### 🎛️ Single Case

    Interactive calculator for evaluating a single phased array configuration.

    - Array size and spacing
    - TX power and efficiency
    - Link budget metrics
    - Pass/fail indicators
    """)

with col2:
    st.markdown("""
    ### 📊 Trade Study

    Design of Experiments (DOE) with Pareto optimization.

    - Define design space
    - LHS/Grid/Random sampling
    - Interactive Pareto plots
    - Export results
    """)

with col3:
    st.markdown("""
    ### 🔗 RF Cascade

    Cascaded RF chain performance analyzer.

    - Multi-stage RF chains
    - Friis noise figure
    - IIP3/OIP3 cascade
    - SFDR and MDS
    """)

with col4:
    st.markdown("""
    ### 🎯 Radar Detection

    Radar equation and detection analysis.

    - SNR calculation
    - Detection probability
    - Integration gain
    - Range curves
    """)

st.divider()

# Quick links
st.markdown("## Resources")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
    **Documentation**
    - [Getting Started](https://jman4162.github.io/phased-array-systems/getting-started/quickstart/)
    - [User Guide](https://jman4162.github.io/phased-array-systems/user-guide/)
    - [API Reference](https://jman4162.github.io/phased-array-systems/api/)
    """)

with col2:
    st.markdown("""
    **Code & Examples**
    - [GitHub Repository](https://github.com/jman4162/phased-array-systems)
    - [Example Scripts](https://github.com/jman4162/phased-array-systems/tree/main/examples)
    - [Tutorial Notebook](https://colab.research.google.com/github/jman4162/phased-array-systems/blob/main/notebooks/tutorial_phased_array_trade_study.ipynb)
    """)

with col3:
    st.markdown("""
    **Installation**
    ```bash
    pip install phased-array-systems
    ```

    **With Visualization**
    ```bash
    pip install phased-array-systems[plotting]
    ```
    """)

# Footer
st.divider()
st.markdown("""
<div style='text-align: center; color: gray;'>
    <small>
        phased-array-systems v0.4.0 |
        <a href="https://github.com/jman4162/phased-array-systems">GitHub</a> |
        MIT License
    </small>
</div>
""", unsafe_allow_html=True)
