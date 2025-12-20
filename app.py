import streamlit as st
import pandas as pd
import re
from io import StringIO

# --- CONFIGURATION & STYLING ---
st.set_page_config(page_title="Regula Health | Compliance MVP", layout="wide")

# Custom CSS for a professional look
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #e0e0e0; }
    .compliance-box { padding: 20px; border-radius: 10px; background-color: #f0f2f6; border-left: 5px solid #007bff; }
    .underpaid { color: #d9534f; font-weight: bold; }
    .compliant { color: #5cb85c; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- RATE DATABASE (DEMO) ---
# Hard-coded for NYC 2025 post-COLA/Geo Adjustment
RATE_DATABASE = {
    "90837": 154.29,  # NYC Psychotherapy 60 min
    "90834": 105.50,  # NYC Psychotherapy 45 min
    "90791": 172.10,  # Psychiatric Diagnostic Evaluation
}

CITATION_TEXT = """
**Regulatory Basis for Violation:**
1. **NY Public Health Law §2807-v(2)(b):** Mandates reimbursement at no less than the 2025 Medicaid Floor.
2. **MHPAEA (Federal):** 29 CFR §2590.712 - Prohibits discriminatory financial requirements for BH services.
3. **NY Insurance Law §3221(l)(8):** Requires strict adherence to parity benchmarks in commercial plans.
"""

# --- PARSING LOGIC ---
def parse_835_content(raw_text):
    """
    Simplistic EDI 835 Parser for Demo purposes.
    Extracts CLP (Claim) and SVC (Service) segments.
    """
    claims = []
    # EDI segments are usually delimited by ~ or newlines
    segments = raw_text.replace('\n', '').split('~')
    
    current_claim = None
    
    for seg in segments:
        parts = seg.split('*')
        seg_id = parts[0]
        
        # CLP Segment: Claim ID and Total Paid
        if seg_id == 'CLP':
            current_claim = {
                "Claim ID": parts[1],
                "Total Paid": float(parts[4]),
                "Payer": "Sample Payer NY", # Simplified for MVP
            }
        
        # SVC Segment: CPT Code and Line Item Paid
        elif seg_id == 'SVC' and current_claim:
            # Format usually: SVC*HC:90837*300*125.50...
            cpt_part = parts[1]
            cpt_code = cpt_part.split(':')[-1] if ':' in cpt_part else cpt_part
            current_claim["CPT"] = cpt_code
            current_claim["Paid Amount"] = float(parts[3])
            
        # DTM Segment: Date of Service
        elif seg_id == 'DTM' and parts[1] == '232' and current_claim:
            current_claim["DOS"] = f"{parts[2][:4]}-{parts[2][4:6]}-{parts[2][6:]}"
            claims.append(current_claim.copy())
            current_claim = None

    return pd.DataFrame(claims)

# --- UI LAYOUT ---

# Sidebar - Branding
with st.sidebar:
    st.title("🛡️ Regula Health")
    st.subheader("Compliance Infrastructure")
    st.markdown("---")
    st.info("**HIPAA NOTICE:** This MVP is for demonstration only. Ensure all uploaded files are de-identified or synthetic.")
    
    st.markdown("### Demo Tools")
    if st.button("Generate Sample EDI Data"):
        sample_edi = "ISA*00*...~GS*HP*...~ST*835*...~CLP*CLAIM123*1*250*125.50*...~SVC*HC:90837*250*125.50~DTM*232*20250115~CLP*CLAIM456*1*200*95.00*...~SVC*HC:90837*200*95.00~DTM*232*20250120~"
        st.session_state['sample_data'] = sample_edi
        st.success("Sample data loaded!")

# Main Header
st.title("Behavioral Health Mandate Lag Analysis")
st.markdown("#### Regula Health: Analyzing L.2024 c.57 §2 Compliance")

# File Upload
uploaded_file = st.file_uploader("Upload 835 ERA File (.txt, .edi, .dat)", type=['txt', 'edi', 'dat'])

input_data = None
if uploaded_file:
    stringio = StringIO(uploaded_file.getvalue().decode("utf-8"))
    input_data = stringio.read()
elif 'sample_data' in st.session_state:
    input_data = st.session_state['sample_data']

if input_data:
    df = parse_835_content(input_data)
    
    if not df.empty:
        # Calculate Shadow Delta
        df['Medicaid Floor'] = df['CPT'].map(RATE_DATABASE).fillna(0)
        df['Shadow Delta'] = df['Paid Amount'] - df['Medicaid Floor']
        df['Status'] = df['Shadow Delta'].apply(lambda x: "⚠️ Underpaid" if x < -0.01 else "✅ Compliant")

        # Top Level Metrics
        m1, m2, m3 = st.columns(3)
        underpaid_count = len(df[df['Shadow Delta'] < 0])
        total_leakage = df[df['Shadow Delta'] < 0]['Shadow Delta'].sum()
        
        m1.metric("Total Claims Parsed", len(df))
        m2.metric("Non-Compliant Claims", underpaid_count, delta=f"{underpaid_count/len(df)*100:.0f}%", delta_color="inverse")
        m3.metric("Total Recovery Opportunity", f"${abs(total_leakage):,.2f}", delta="Action Required", delta_color="off")

        st.markdown("---")
        
        # Results Table
        st.subheader("Extracted Claim Intelligence")
        
        def color_delta(val):
            color = 'red' if val < 0 else 'green'
            return f'color: {color}'

        styled_df = df.style.applymap(color_delta, subset=['Shadow Delta'])
        st.dataframe(styled_df, use_container_width=True)

        # Regulatory Citation Section
        if underpaid_count > 0:
            st.error("### 🛑 Regulatory Violations Detected")
            with st.container():
                st.markdown(f"""
                <div class="compliance-box">
                    {CITATION_TEXT}
                    <br>
                    <strong>Action:</strong> {underpaid_count} claims qualify for an immediate parity appeal.
                </div>
                """, unsafe_allow_html=True)
                
                st.download_button(
                    label="Download Compliance Report (CSV)",
                    data=df.to_csv(index=False),
                    file_name="regula_health_parity_report.csv",
                    mime="text/csv"
                )
    else:
        st.warning("No claim data (CLP/SVC segments) found in the provided file.")

else:
    st.info("Upload an 835 file or click 'Generate Sample EDI Data' in the sidebar to begin.")
