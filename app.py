import streamlit as st
import pandas as pd
import re
from io import StringIO

# --- CONFIGURATION & STYLING (Elon Musk Edition: Crimson Fury) ---
st.set_page_config(page_title="Grok Parity | xAI-Powered BH Compliance", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #000000; color: #ffffff; }
    .stApp { background: linear-gradient(to bottom, #000000, #111111); }
    h1, h2, h3 { font-family: 'Orbitron', sans-serif; color: #ff0000; text-shadow: 0 0 10px #ff0000; }
    .stMetric { background-color: #1e1e1e; padding: 20px; border-radius: 15px; border: 2px solid #ff0000; box-shadow: 0 0 20px rgba(255,0,0,0.5); }
    .compliance-box { padding: 30px; border-radius: 15px; background-color: #111111; border-left: 10px solid #ff0000; box-shadow: 0 0 30px rgba(255,0,0,0.7); }
    .underpaid { color: #ff0000; font-weight: bold; font-size: 1.5em; }
    .compliant { color: #00ff00; font-weight: bold; font-size: 1.5em; }
    .stButton>button { background-color: #ff0000; color: white; font-weight: bold; border-radius: 10px; }
    .stDownloadButton>button { background-color: #000000; border: 2px solid #ff0000; color: #ff0000; }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@700&display=swap" rel="stylesheet">', unsafe_allow_html=True)

# --- RATE DATABASE (2026 NY Medicaid Parity Floor - NYC Metro) ---
RATE_DATABASE = {
    "90837": 158.00,  # Psychotherapy 60 min
    "90834": 110.00,  # Psychotherapy 45 min
    "90791": 175.00,  # Psychiatric Diagnostic Evaluation
    # Expand as needed
}

CITATION_TEXT = """
**Regulatory Basis for Violation (2026 Enforcement):**
1. **NY Insurance Law §3221(l)(8) & Part AA Ch.57 Laws 2024:** Commercial insurers MUST reimburse BH services at NO LESS than Medicaid rate.
2. **MHPAEA (Federal) - Strengthened 2024 Rules (Effective 2026):** Prohibits discriminatory NQTLs; requires parity in reimbursement.
3. **NY Public Health Law & OMH Guidance:** Mandate lag violations trigger immediate appeals and potential fines.
4. **Truth-Seeking Addendum:** Insurers hiding behind outdated rates? Not on our watch. Maximize recovery.
"""

# --- ROBUST PARSING FUNCTION (Multi-Line SVC Support) ---
def parse_835_content(raw_text):
    """
    ROBUST EDI 835 Parser:
    - Handles multiple Service Lines (SVC) per Claim (CLP).
    - Flattens data (1 row per CPT code).
    - Handles missing/malformed segments safely.
    """
    claims_data = []
    segments = re.split(r'~|\n', raw_text)
   
    current_clp_id = ""
    current_payer = ""
    current_total_paid = 0.0
    current_dos = ""
   
    for seg in segments:
        seg = seg.strip()
        if not seg: continue
       
        parts = seg.split('*')
        seg_id = parts[0] if parts else ""
       
        # 1. Claim Header (CLP)
        if seg_id == 'CLP':
            try:
                current_clp_id = parts[1] if len(parts) > 1 else ""
                current_total_paid = float(parts[4]) if len(parts) > 4 else 0.0
                current_payer = parts[7] if len(parts) > 7 else "Unknown Payer"
            except (ValueError, IndexError):
                continue
       
        # 2. Service Line (SVC) - THIS IS WHERE WE WRITE THE ROW
        elif seg_id == 'SVC':
            try:
                cpt_raw = parts[1] if len(parts) > 1 else ""
                cpt_code = cpt_raw.split(':')[-1] if ':' in cpt_raw else cpt_raw
               
                line_paid = float(parts[3]) if len(parts) > 3 else 0.0
               
                row = {
                    "Claim ID": current_clp_id,
                    "Payer": current_payer,
                    "DOS": current_dos,
                    "CPT": cpt_code,
                    "Paid Amount": line_paid
                }
                claims_data.append(row)
               
            except (ValueError, IndexError):
                continue

        # 3. Date (DTM) - Capture service/statement date
        elif seg_id == 'DTM' and len(parts) > 1:
            try:
                date_qual = parts[1]
                date_val = parts[2]
                if date_qual in ['150', '232', '011'] and len(date_val) >= 8:
                    formatted_date = f"{date_val[:4]}-{date_val[4:6]}-{date_val[6:]}"
                    current_dos = formatted_date
            except IndexError:
                continue
               
    return pd.DataFrame(claims_data)

# --- UI LAYOUT ---
with st.sidebar:
    st.image("https://x.ai/_next/static/media/xai-logo.0f9e62c9.png", width=200)
    st.title("🚀 Grok Parity")
    st.subheader("xAI-Powered Truth in BH Reimbursement")
    st.markdown("---")
    st.markdown("**Mission:** Expose insurer lag. Recover what’s yours. No compromise.")
    st.info("**HIPAA NOTICE:** Demo only. Use de-identified data.")
    
    if st.button("Generate Sample EDI Data (2026)"):
        sample_edi = """
ISA*00*          *00*          *ZZ*SUBMITTER    *ZZ*RECEIVER     *260101*1200*U*00401*000000001*0*P*:~
GS*HP*SUBMITTER*RECEIVER*20260101*1200*1*X*004010X091A1~
ST*835*0001~
CLP*CLAIM2026*1*300.00*130.00**MC*123456789~ 
SVC*HC:90837*300.00*130.00~
DTM*232*20260115~
SVC*HC:90834*150.00*80.00~
DTM*232*20260115~
CLP*CLAIM2027*1*250.00*90.00**MC*987654321~
SVC*HC:90837*250.00*90.00~
DTM*232*20260120~
SE*10*0001~
GE*1*1~
IEA*1*000000001~
"""
        st.session_state['sample_data'] = sample_edi
        st.success("Sample 2026 multi-line data loaded! 🚀")

# Main Header
st.title("🔴 GROK PARITY: Behavioral Health Mandate Lag Destroyer")
st.markdown("#### Powered by xAI | 2026 NY Parity Enforcement | Insurers Can Run, But They Can't Hide")

# File Upload
uploaded_file = st.file_uploader("Upload 835 ERA File (.txt, .edi, .dat)", type=['txt', 'edi', 'dat'])
input_data = None
if uploaded_file:
    input_data = StringIO(uploaded_file.getvalue().decode("utf-8")).read()
elif 'sample_data' in st.session_state:
    input_data = st.session_state['sample_data']

if input_data:
    df = parse_835_content(input_data)
    
    if not df.empty:
        # Parity Analysis
        df['Medicaid Parity Floor (2026)'] = df['CPT'].map(RATE_DATABASE).fillna(0)
        df['Shadow Delta'] = df['Paid Amount'] - df['Medicaid Parity Floor (2026)']
        df['Status'] = df['Shadow Delta'].apply(lambda x: "🔥 UNDERPAID - APPEAL NOW" if x < -0.01 else "🟢 Compliant")
        
        # Key Metrics
        underpaid_df = df[df['Shadow Delta'] < 0]
        underpaid_count = len(underpaid_df)
        total_leakage = abs(underpaid_df['Shadow Delta'].sum())
        avg_underpayment = abs(underpaid_df['Shadow Delta'].mean()) if underpaid_count > 0 else 0.0

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Service Lines Parsed", len(df))
        col2.metric("Violations Detected", underpaid_count, delta=f"{underpaid_count/len(df)*100:.1f}%")
        col3.metric("Total Recovery Opportunity", f"${total_leakage:,.2f}")
        col4.metric("Avg Underpayment Per Claim", f"${avg_underpayment:,.2f}", delta="Data-Driven Insight")

        st.markdown("---")
        
        # Results Table
        st.subheader("🛡️ Extracted Claim Intelligence - Line-Level Truth")
        
        def color_delta(val):
            return 'color: #ff0000' if val < 0 else 'color: #00ff00'
        
        styled_df = df.style.applymap(color_delta, subset=['Shadow Delta']) \
                           .format({"Paid Amount": "${:.2f}", 
                                    "Medicaid Parity Floor (2026)": "${:.2f}", 
                                    "Shadow Delta": "${:.2f}"})
        st.dataframe(styled_df, use_container_width=True)
        
        # Violation Alert
        if underpaid_count > 0:
            st.error("🚨 SYSTEMIC REGULATORY VIOLATIONS DETECTED")
            with st.container():
                st.markdown(f"""
                <div class="compliance-box">
                    {CITATION_TEXT}
                    <br>
                    <strong>ACTION:</strong> {underpaid_count} service lines underpaid by a total of ${total_leakage:,.2f}.
                    <br>Average loss per claim: ${avg_underpayment:,.2f} — this is not random. This is policy.
                    <br><strong>Grok Says:</strong> Time to appeal. Hard.
                </div>
                """, unsafe_allow_html=True)
                
                st.download_button(
                    label="🚀 Download Grok Parity Report (CSV)",
                    data=df.to_csv(index=False),
                    file_name="grok_parity_2026_line_level_report.csv",
                    mime="text/csv"
                )
    else:
        st.warning("No valid service lines (SVC segments) found. Check file format.")
else:
    st.info("Upload an 835 file or generate sample data to activate Grok Parity. 🚀")
    st.balloons()
