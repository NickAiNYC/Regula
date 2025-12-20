# Regula Health: NY Medicaid Rate Compliance Engine ⚖️

The industry-standard engine for identifying systemic behavioral health underpayments 
in New York State, updated for the **2025 2.84% COLA** mandate.

## 🚀 Key Features
- **Real-time Rate Engine**: Geographic adjustment for NYC (1.065), LI (1.025), and Upstate.
- **HIPAA-Compliant Parser**: Streaming EDI 835 processing with PHI hashing.
- **Violation Detector**: Identifies "Shadow Deltas" using the L.2024 c.57 framework.
- **Regulatory Factory**: Auto-generates DFS demand letters with statutory citations.

## 🛠 Tech Stack
- **Backend**: FastAPI (Python 3.12)
- **Data**: PostgreSQL (TimescaleDB) + Redis
- **UI**: Streamlit
- **Infra**: Docker + AWS Fargate

## 🧪 Quick Start
```bash
# Clone the repo
git clone [https://github.com/your-org/regula-health-engine.git](https://github.com/your-org/regula-health-engine.git)

# Spin up the local environment
docker-compose up --build
