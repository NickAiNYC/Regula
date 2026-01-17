"""
Regula NYC Building Compliance Engine - Main Streamlit App
ViolationSentinel-style MVP for property managers
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
from datetime import datetime, timedelta
import io

# Page configuration
st.set_page_config(
    page_title="Regula | NYC Building Compliance",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for professional look
st.markdown("""
    <style>
    .main {
        background-color: #f8f9fa;
    }
    .stApp {
        max-width: 1400px;
    }
    h1 {
        color: #1e3a8a;
        font-weight: 700;
    }
    h2, h3 {
        color: #334155;
    }
    .metric-card {
        background: white;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin: 10px 0;
    }
    .high-risk {
        color: #dc2626;
        font-weight: bold;
    }
    .medium-risk {
        color: #f59e0b;
        font-weight: bold;
    }
    .low-risk {
        color: #10b981;
        font-weight: bold;
    }
    .stButton>button {
        background-color: #2563eb;
        color: white;
        font-weight: 600;
        border-radius: 8px;
        padding: 0.5rem 2rem;
        border: none;
    }
    .stButton>button:hover {
        background-color: #1e40af;
    }
    .upgrade-button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 15px 30px;
        border-radius: 10px;
        font-size: 18px;
        font-weight: bold;
        border: none;
        cursor: pointer;
        text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)

# Mock API endpoint (replace with actual backend)
API_BASE_URL = "http://localhost:8000"

def get_risk_color(score):
    """Return color based on risk score"""
    if score >= 70:
        return "🔴", "high-risk"
    elif score >= 40:
        return "🟡", "medium-risk"
    else:
        return "🟢", "low-risk"

def fetch_building_data(address):
    """Fetch building violation data from backend API"""
    # Mock data for demo purposes
    # In production, this would call: requests.post(f"{API_BASE_URL}/scan", json={"address": address})
    
    mock_data = {
        "success": True,
        "building": {
            "address": address.upper(),
            "bin": "1015862",
            "borough": "MANHATTAN",
            "zip": "10018"
        },
        "risk_score": 76,
        "violations": {
            "active": 3,
            "resolved": 47,
            "total_fines": 8200.00
        },
        "forecasts": {
            "30_days": 4100.00,
            "60_days": 8900.00,
            "90_days": 12400.00
        },
        "top_risks": [
            {
                "type": "Boiler Inspection Overdue",
                "severity": "high",
                "recommended_action": "Schedule inspection within 14 days",
                "potential_fine": 5000,
                "deadline": (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
            },
            {
                "type": "Sidewalk Repair Required",
                "severity": "medium",
                "recommended_action": "File repair permit",
                "potential_fine": 2200,
                "deadline": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
            },
            {
                "type": "Fire Escape Certification",
                "severity": "medium",
                "recommended_action": "Schedule inspection",
                "potential_fine": 1000,
                "deadline": (datetime.now() + timedelta(days=45)).strftime("%Y-%m-%d")
            }
        ],
        "violation_history": [
            {"month": "Jul", "violations": 2, "fines": 1200},
            {"month": "Aug", "violations": 1, "fines": 800},
            {"month": "Sep", "violations": 0, "fines": 0},
            {"month": "Oct", "violations": 3, "fines": 2400},
            {"month": "Nov", "violations": 1, "fines": 600},
            {"month": "Dec", "violations": 2, "fines": 1100},
            {"month": "Jan", "violations": 3, "fines": 2100}
        ]
    }
    
    return mock_data

def process_csv_upload(csv_file):
    """Process CSV file with multiple addresses"""
    df = pd.read_csv(csv_file)
    
    # Expected columns: Address, Borough, Zip (flexible)
    if 'address' in df.columns or 'Address' in df.columns:
        address_col = 'address' if 'address' in df.columns else 'Address'
    else:
        st.error("CSV must contain an 'Address' column")
        return None
    
    results = []
    progress_bar = st.progress(0)
    
    for idx, row in df.iterrows():
        address = row[address_col]
        data = fetch_building_data(address)
        
        if data["success"]:
            results.append({
                "Address": data["building"]["address"],
                "BIN": data["building"]["bin"],
                "Risk Score": data["risk_score"],
                "Active Violations": data["violations"]["active"],
                "Total Fines": f"${data['violations']['total_fines']:,.0f}",
                "90-Day Forecast": f"${data['forecasts']['90_days']:,.0f}"
            })
        
        progress_bar.progress((idx + 1) / len(df))
    
    return pd.DataFrame(results)

# Sidebar
with st.sidebar:
    st.image("https://via.placeholder.com/200x60/2563eb/ffffff?text=Regula", use_container_width=True)
    st.title("🏢 Regula NYC")
    st.markdown("**Building Compliance Engine**")
    st.markdown("---")
    
    # Account tier badge
    tier = st.session_state.get('tier', 'Free')
    if tier == 'Free':
        st.info("**Free Tier** (3 buildings max)")
        st.markdown("""
        ### 🚀 Upgrade to Pro
        - Monitor 25 buildings
        - SMS alerts
        - 90-day forecasts
        - Priority support
        
        **$199/month**
        """)
        if st.button("Upgrade Now", key="sidebar_upgrade"):
            st.session_state['show_upgrade'] = True
    else:
        st.success(f"**{tier} Tier Active** ✓")
    
    st.markdown("---")
    
    # Navigation
    st.markdown("### 📍 Navigation")
    page = st.radio(
        "Go to:",
        ["🏠 Dashboard", "🔍 Scanner", "📊 Forecast", "📁 Portfolio"],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    st.markdown("### 📚 Resources")
    st.markdown("- [HPD Violation Guide](https://www1.nyc.gov/site/hpd/index.page)")
    st.markdown("- [DOB Violations FAQ](https://www1.nyc.gov/site/buildings/index.page)")
    st.markdown("- [ECB Hearings](https://www1.nyc.gov/site/oath/hearings/ecb.page)")
    
    st.markdown("---")
    st.caption("© 2025 Regula NYC")

# Main content area
if page == "🏠 Dashboard":
    st.title("🏠 Building Compliance Dashboard")
    st.markdown("Upload building addresses or CSV to get instant risk analysis")
    
    # Input method tabs
    tab1, tab2 = st.tabs(["📝 Single Address", "📄 CSV Upload"])
    
    with tab1:
        st.subheader("Scan Single Building")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            address = st.text_input(
                "Enter NYC Building Address",
                placeholder="347 West 36th Street, New York, NY 10018",
                help="Enter full address including borough"
            )
        with col2:
            scan_button = st.button("🔍 Scan Building", type="primary")
        
        if scan_button and address:
            with st.spinner("Scanning NYC DOB/HPD databases..."):
                data = fetch_building_data(address)
            
            if data["success"]:
                # Building Info Header
                st.markdown(f"### 📍 {data['building']['address']}")
                st.caption(f"BIN: {data['building']['bin']} | Borough: {data['building']['borough']} | Zip: {data['building']['zip']}")
                
                # Risk Score & Key Metrics
                col1, col2, col3, col4 = st.columns(4)
                
                risk_icon, risk_class = get_risk_color(data['risk_score'])
                
                with col1:
                    st.metric(
                        "Risk Score",
                        f"{risk_icon} {data['risk_score']}/100",
                        help="0-39: Low Risk | 40-69: Medium Risk | 70-100: High Risk"
                    )
                
                with col2:
                    st.metric(
                        "Active Violations",
                        data['violations']['active'],
                        delta=f"-{data['violations']['resolved']} resolved",
                        delta_color="normal"
                    )
                
                with col3:
                    st.metric(
                        "Total Fines",
                        f"${data['violations']['total_fines']:,.0f}",
                        delta="Current balance"
                    )
                
                with col4:
                    st.metric(
                        "90-Day Forecast",
                        f"${data['forecasts']['90_days']:,.0f}",
                        delta=f"+${data['forecasts']['90_days'] - data['violations']['total_fines']:,.0f}",
                        delta_color="inverse"
                    )
                
                st.markdown("---")
                
                # Two column layout for details
                col_left, col_right = st.columns([1, 1])
                
                with col_left:
                    st.subheader("🚨 Top Risks")
                    for idx, risk in enumerate(data['top_risks'], 1):
                        severity_colors = {
                            "high": "🔴",
                            "medium": "��",
                            "low": "🟢"
                        }
                        icon = severity_colors.get(risk['severity'], "⚪")
                        
                        with st.expander(f"{icon} {risk['type']}", expanded=(idx == 1)):
                            st.markdown(f"**Potential Fine:** ${risk['potential_fine']:,}")
                            st.markdown(f"**Deadline:** {risk['deadline']}")
                            st.markdown(f"**Recommended Action:**")
                            st.info(risk['recommended_action'])
                
                with col_right:
                    st.subheader("📈 Fine Forecast")
                    
                    forecast_df = pd.DataFrame({
                        "Period": ["Current", "30 Days", "60 Days", "90 Days"],
                        "Projected Fines": [
                            data['violations']['total_fines'],
                            data['forecasts']['30_days'],
                            data['forecasts']['60_days'],
                            data['forecasts']['90_days']
                        ]
                    })
                    
                    fig = px.line(
                        forecast_df,
                        x="Period",
                        y="Projected Fines",
                        markers=True,
                        title="Projected Fine Accumulation"
                    )
                    fig.update_traces(line_color='#dc2626', line_width=3)
                    fig.update_layout(
                        yaxis_title="Total Fines ($)",
                        xaxis_title="",
                        showlegend=False,
                        hovermode='x unified'
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    
                    st.subheader("📊 Violation History")
                    history_df = pd.DataFrame(data['violation_history'])
                    
                    fig2 = go.Figure()
                    fig2.add_trace(go.Bar(
                        x=history_df['month'],
                        y=history_df['violations'],
                        name='Violations',
                        marker_color='#f59e0b'
                    ))
                    fig2.update_layout(
                        yaxis_title="Number of Violations",
                        xaxis_title="Month",
                        showlegend=False
                    )
                    st.plotly_chart(fig2, use_container_width=True)
        
        elif scan_button:
            st.warning("Please enter a valid NYC address")
    
    with tab2:
        st.subheader("Bulk Portfolio Scan")
        st.markdown("Upload a CSV file with building addresses to scan your entire portfolio")
        
        # Sample CSV download
        sample_csv = pd.DataFrame({
            "Address": [
                "347 West 36th Street, New York, NY",
                "123 Broadway, New York, NY",
                "456 Park Avenue, New York, NY"
            ],
            "Borough": ["Manhattan", "Manhattan", "Manhattan"],
            "Zip": ["10018", "10013", "10022"]
        })
        
        st.download_button(
            label="📥 Download Sample CSV",
            data=sample_csv.to_csv(index=False),
            file_name="sample_buildings.csv",
            mime="text/csv"
        )
        
        uploaded_file = st.file_uploader(
            "Upload CSV with building addresses",
            type=['csv'],
            help="CSV should contain an 'Address' column"
        )
        
        if uploaded_file:
            st.info("📊 Processing buildings...")
            results_df = process_csv_upload(uploaded_file)
            
            if results_df is not None:
                st.success(f"✅ Scanned {len(results_df)} buildings")
                
                # Summary metrics
                col1, col2, col3 = st.columns(3)
                with col1:
                    avg_risk = results_df['Risk Score'].mean()
                    st.metric("Average Risk Score", f"{avg_risk:.0f}")
                with col2:
                    total_violations = results_df['Active Violations'].sum()
                    st.metric("Total Active Violations", total_violations)
                with col3:
                    high_risk_count = (results_df['Risk Score'] >= 70).sum()
                    st.metric("High Risk Buildings", high_risk_count)
                
                # Results table
                st.subheader("📋 Portfolio Overview")
                st.dataframe(
                    results_df.style.apply(
                        lambda x: ['background-color: #fee2e2' if v >= 70 else '' for v in results_df['Risk Score']],
                        axis=0,
                        subset=['Risk Score']
                    ),
                    use_container_width=True
                )
                
                # Export button
                csv_export = results_df.to_csv(index=False)
                st.download_button(
                    label="�� Download Results",
                    data=csv_export,
                    file_name=f"regula_scan_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
    
    # Upgrade CTA
    st.markdown("---")
    if st.session_state.get('tier', 'Free') == 'Free':
        st.markdown("""
        <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    padding: 30px; border-radius: 15px; text-align: center; color: white;'>
            <h2>🚀 Unlock Full Power with Pro</h2>
            <p style='font-size: 18px;'>Monitor 25 buildings • SMS Alerts • 90-Day Forecasts • Priority Support</p>
            <p style='font-size: 24px; font-weight: bold;'>$199/month</p>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("🎯 Upgrade to Pro", key="main_upgrade", type="primary"):
            st.session_state['show_upgrade'] = True

elif page == "🔍 Scanner":
    st.title("🔍 Live DOB Violation Scanner")
    st.markdown("Real-time access to NYC Department of Buildings violation database")
    st.info("**Coming Soon:** This page will provide live DOB violation lookup with detailed violation history.")
    
elif page == "📊 Forecast":
    st.title("📊 90-Day Fine Forecast")
    st.markdown("Predict penalty accumulation across your portfolio")
    st.info("**Coming Soon:** Advanced forecasting with ML-powered predictions.")
    
elif page == "📁 Portfolio":
    st.title("📁 Portfolio Dashboard")
    st.markdown("Manage all your buildings in one place")
    st.info("**Coming Soon:** Comprehensive portfolio management with bulk actions.")

# Handle Stripe upgrade modal
if st.session_state.get('show_upgrade'):
    with st.container():
        st.markdown("### 💳 Upgrade to Pro - $199/month")
        st.markdown("""
        **Includes:**
        - ✅ Monitor up to 25 buildings
        - ✅ SMS + Email alerts
        - ✅ 90-day fine forecasts
        - ✅ AI risk scoring
        - ✅ Priority support (4-hour response)
        - ✅ Unlimited CSV uploads
        - ✅ Export reports (PDF/Excel)
        """)
        
        # Stripe integration (mock for now)
        st.markdown("""
        <a href="https://buy.stripe.com/test_mocklink" target="_blank">
            <button class="upgrade-button">
                🔒 Secure Checkout with Stripe
            </button>
        </a>
        """, unsafe_allow_html=True)
        
        if st.button("Cancel"):
            st.session_state['show_upgrade'] = False
            st.rerun()
