"""
Regula - Live DOB Violation Scanner
Real-time violation lookup for NYC buildings
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import requests

st.set_page_config(page_title="DOB Scanner | Regula", page_icon="🔍", layout="wide")

st.title("🔍 Live DOB Violation Scanner")
st.markdown("Real-time violation lookup from NYC Department of Buildings database")

# Input section
col1, col2 = st.columns([3, 1])

with col1:
    search_term = st.text_input(
        "Search by Address or BIN",
        placeholder="347 West 36th Street or BIN: 1015862",
        help="Enter building address or Building Identification Number"
    )

with col2:
    search_btn = st.button("🔍 Search DOB", type="primary")

if search_btn and search_term:
    with st.spinner("Querying NYC DOB database..."):
        # Mock data - replace with actual DOB API call
        violations_data = [
            {
                "number": "ECB-35287643",
                "type": "Boiler - Operating",
                "issued_date": "2024-12-15",
                "status": "Active",
                "severity": "High",
                "fine": 5000,
                "description": "Failed annual boiler inspection"
            },
            {
                "number": "ECB-35198234",
                "type": "Sidewalk",
                "issued_date": "2024-11-03",
                "status": "Active",
                "severity": "Medium",
                "fine": 2200,
                "description": "Sidewalk repair required"
            },
            {
                "number": "ECB-34987621",
                "type": "Fire Escape",
                "issued_date": "2024-10-22",
                "status": "Resolved",
                "severity": "Medium",
                "fine": 0,
                "description": "Fire escape certification required"
            }
        ]
        
        df = pd.DataFrame(violations_data)
        
        st.success(f"Found {len(df)} violations for {search_term}")
        
        # Summary metrics
        col1, col2, col3 = st.columns(3)
        active_count = len(df[df['status'] == 'Active'])
        resolved_count = len(df[df['status'] == 'Resolved'])
        total_fines = df[df['status'] == 'Active']['fine'].sum()
        
        with col1:
            st.metric("Active Violations", active_count, delta=f"{active_count-resolved_count}")
        with col2:
            st.metric("Resolved Violations", resolved_count)
        with col3:
            st.metric("Total Active Fines", f"${total_fines:,}")
        
        st.markdown("---")
        
        # Violations table
        st.subheader("Violation Details")
        
        def color_status(val):
            color = '#dc2626' if val == 'Active' else '#10b981'
            return f'background-color: {color}20; color: {color}; font-weight: bold'
        
        styled_df = df.style.applymap(color_status, subset=['status'])
        st.dataframe(styled_df, use_container_width=True)
        
        # Violation timeline
        st.subheader("Violation Timeline")
        
        fig = go.Figure()
        
        for idx, row in df.iterrows():
            fig.add_trace(go.Scatter(
                x=[row['issued_date']],
                y=[row['type']],
                mode='markers',
                marker=dict(
                    size=20,
                    color='red' if row['status'] == 'Active' else 'green'
                ),
                name=row['type'],
                text=f"{row['number']}<br>{row['description']}",
                hoverinfo='text'
            ))
        
        fig.update_layout(
            showlegend=False,
            xaxis_title="Issue Date",
            yaxis_title="Violation Type",
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)

else:
    st.info("👆 Enter a building address or BIN to search DOB violations")
    
    st.markdown("""
    ### What you'll get:
    - ✅ All active DOB violations
    - ✅ Historical violation records
    - ✅ ECB hearing information
    - ✅ Open permit status
    - ✅ Certificate of Occupancy details
    """)
