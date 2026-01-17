"""
Regula - Portfolio Dashboard
Multi-building compliance management
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Portfolio | Regula", page_icon="📁", layout="wide")

st.title("📁 Portfolio Compliance Dashboard")
st.markdown("Manage all your buildings in one centralized view")

# Mock portfolio data
portfolio_data = pd.DataFrame({
    "Address": [
        "347 West 36th Street",
        "123 Broadway",
        "456 Park Avenue",
        "789 Madison Avenue",
        "321 Lexington Avenue"
    ],
    "BIN": ["1015862", "1087234", "1098345", "1076543", "1065432"],
    "Borough": ["Manhattan", "Manhattan", "Manhattan", "Manhattan", "Manhattan"],
    "Risk Score": [76, 42, 89, 34, 61],
    "Active Violations": [3, 1, 5, 0, 2],
    "Total Fines": [8200, 1200, 14500, 0, 3400],
    "Units": [48, 72, 156, 24, 88]
})

# Top metrics
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Buildings", len(portfolio_data))
with col2:
    avg_risk = portfolio_data['Risk Score'].mean()
    st.metric("Average Risk Score", f"{avg_risk:.0f}/100")
with col3:
    total_violations = portfolio_data['Active Violations'].sum()
    st.metric("Active Violations", total_violations)
with col4:
    total_fines = portfolio_data['Total Fines'].sum()
    st.metric("Total Fines", f"${total_fines:,}")

st.markdown("---")

# Risk distribution chart
col1, col2 = st.columns(2)

with col1:
    st.subheader("Risk Score Distribution")
    
    fig = px.histogram(
        portfolio_data,
        x='Risk Score',
        nbins=10,
        title="Building Risk Scores",
        color_discrete_sequence=['#2563eb']
    )
    fig.update_layout(
        xaxis_title="Risk Score",
        yaxis_title="Number of Buildings",
        showlegend=False
    )
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("Portfolio Health")
    
    health_data = pd.DataFrame({
        "Status": ["High Risk", "Medium Risk", "Low Risk"],
        "Count": [
            len(portfolio_data[portfolio_data['Risk Score'] >= 70]),
            len(portfolio_data[(portfolio_data['Risk Score'] >= 40) & (portfolio_data['Risk Score'] < 70)]),
            len(portfolio_data[portfolio_data['Risk Score'] < 40])
        ]
    })
    
    fig2 = px.pie(
        health_data,
        values='Count',
        names='Status',
        title="Buildings by Risk Level",
        color='Status',
        color_discrete_map={
            'High Risk': '#dc2626',
            'Medium Risk': '#f59e0b',
            'Low Risk': '#10b981'
        }
    )
    st.plotly_chart(fig2, use_container_width=True)

# Portfolio table
st.subheader("📋 Building Details")

def highlight_risk(row):
    if row['Risk Score'] >= 70:
        return ['background-color: #fee2e2'] * len(row)
    elif row['Risk Score'] >= 40:
        return ['background-color: #fef3c7'] * len(row)
    else:
        return ['background-color: #d1fae5'] * len(row)

styled_df = portfolio_data.style.apply(highlight_risk, axis=1)
st.dataframe(styled_df, use_container_width=True)

# Export options
st.markdown("---")
col1, col2, col3 = st.columns(3)

with col1:
    csv = portfolio_data.to_csv(index=False)
    st.download_button(
        label="📥 Export CSV",
        data=csv,
        file_name=f"portfolio_report_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv"
    )

with col2:
    st.download_button(
        label="📄 Generate PDF Report",
        data="PDF generation coming soon",
        file_name="portfolio_report.pdf",
        disabled=True
    )

with col3:
    if st.button("📧 Email Report"):
        st.info("Email functionality coming soon")
