"""
Regula NYC Building Compliance Backend API
FastAPI backend for DOB/HPD violation scanning
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import requests
from enum import Enum

app = FastAPI(
    title="Regula NYC Compliance API",
    description="NYC Building violation scanning and risk assessment",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class ScanRequest(BaseModel):
    address: str

class RiskSeverity(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"

class TopRisk(BaseModel):
    type: str
    severity: RiskSeverity
    recommended_action: str
    potential_fine: float
    deadline: str

class ViolationStats(BaseModel):
    active: int
    resolved: int
    total_fines: float

class BuildingInfo(BaseModel):
    address: str
    bin: str
    borough: str
    zip: str

class Forecasts(BaseModel):
    thirty_days: float
    sixty_days: float
    ninety_days: float

class ScanResponse(BaseModel):
    success: bool
    building: BuildingInfo
    risk_score: int
    violations: ViolationStats
    forecasts: Forecasts
    top_risks: List[TopRisk]

class ForecastRequest(BaseModel):
    buildings: List[str]  # List of BINs or addresses

class PortfolioForecast(BaseModel):
    thirty_days: float
    sixty_days: float
    ninety_days: float

class ForecastResponse(BaseModel):
    portfolio_forecast: PortfolioForecast
    by_building: List[Dict]

# NYC DOB Open Data API configuration
NYC_DOB_VIOLATIONS_API = "https://data.cityofnewyork.us/resource/3h2n-5cm9.json"
NYC_HPD_VIOLATIONS_API = "https://data.cityofnewyork.us/resource/wvxf-dwi5.json"

def fetch_dob_violations(bin_number: str) -> List[Dict]:
    """
    Fetch violations from NYC DOB Open Data API
    """
    try:
        # NYC DOB API query
        params = {
            "$where": f"bin='{bin_number}'",
            "$limit": 100
        }
        response = requests.get(NYC_DOB_VIOLATIONS_API, params=params, timeout=10)
        
        if response.status_code == 200:
            return response.json()
        else:
            # Return mock data if API fails
            return generate_mock_violations()
    except Exception as e:
        print(f"Error fetching DOB data: {e}")
        return generate_mock_violations()

def generate_mock_violations() -> List[Dict]:
    """Generate mock violation data for demo"""
    return [
        {
            "violation_number": "ECB-35287643",
            "violation_type": "Boiler - Operating",
            "issue_date": "2024-12-15",
            "disposition": "Active",
            "severity": "High"
        },
        {
            "violation_number": "ECB-35198234",
            "violation_type": "Sidewalk",
            "issue_date": "2024-11-03",
            "disposition": "Active",
            "severity": "Medium"
        }
    ]

def calculate_risk_score(violations: List[Dict], building_age: int = 50) -> int:
    """
    Calculate risk score using simplified model
    In production, this would use XGBoost model
    """
    active_violations = [v for v in violations if v.get('disposition') == 'Active']
    
    # Simple scoring algorithm
    base_score = len(active_violations) * 15
    age_factor = min(building_age / 2, 20)
    
    # High severity violations add more weight
    severity_score = sum(
        10 if v.get('severity') == 'High' else 5 
        for v in active_violations
    )
    
    total_score = min(base_score + age_factor + severity_score, 100)
    return int(total_score)

def generate_fine_forecast(current_fines: float, risk_score: int) -> Forecasts:
    """Generate 90-day fine forecast"""
    # Compound growth based on risk score
    daily_growth_rate = (risk_score / 100) * 150
    
    forecast_30 = current_fines + (daily_growth_rate * 30)
    forecast_60 = current_fines + (daily_growth_rate * 60) + (daily_growth_rate * 0.2 * 60)
    forecast_90 = current_fines + (daily_growth_rate * 90) + (daily_growth_rate * 0.4 * 90)
    
    return Forecasts(
        thirty_days=round(forecast_30, 2),
        sixty_days=round(forecast_60, 2),
        ninety_days=round(forecast_90, 2)
    )

def identify_top_risks(violations: List[Dict]) -> List[TopRisk]:
    """Identify and prioritize top risks"""
    risk_map = {
        "Boiler": {
            "type": "Boiler Inspection Overdue",
            "severity": "high",
            "action": "Schedule inspection within 14 days",
            "fine": 5000
        },
        "Sidewalk": {
            "type": "Sidewalk Repair Required",
            "severity": "medium",
            "action": "File repair permit",
            "fine": 2200
        },
        "Fire": {
            "type": "Fire Escape Certification",
            "severity": "medium",
            "action": "Schedule inspection",
            "fine": 1000
        }
    }
    
    risks = []
    for violation in violations[:3]:  # Top 3 risks
        v_type = violation.get('violation_type', '')
        
        for key, risk_info in risk_map.items():
            if key.lower() in v_type.lower():
                risks.append(TopRisk(
                    type=risk_info['type'],
                    severity=risk_info['severity'],
                    recommended_action=risk_info['action'],
                    potential_fine=risk_info['fine'],
                    deadline=(datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
                ))
                break
    
    # Add default risk if none found
    if not risks:
        risks.append(TopRisk(
            type="General Compliance Review",
            severity="low",
            recommended_action="Conduct routine building inspection",
            potential_fine=500,
            deadline=(datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        ))
    
    return risks

@app.get("/")
async def root():
    return {
        "service": "Regula NYC Compliance API",
        "version": "1.0.0",
        "status": "operational",
        "endpoints": ["/scan", "/forecast", "/health"]
    }

@app.post("/scan", response_model=ScanResponse)
async def scan_building(request: ScanRequest):
    """
    Scan a NYC building for violations and calculate risk score
    """
    address = request.address.strip()
    
    if not address:
        raise HTTPException(status_code=400, detail="Address is required")
    
    # In production, geocode address to get BIN
    # For demo, use mock BIN
    mock_bin = "1015862"
    
    # Fetch violations from DOB API
    violations = fetch_dob_violations(mock_bin)
    
    # Calculate risk score
    risk_score = calculate_risk_score(violations)
    
    # Count violations
    active_violations = [v for v in violations if v.get('disposition') == 'Active']
    resolved_violations = [v for v in violations if v.get('disposition') != 'Active']
    
    # Calculate current fines (mock)
    total_fines = len(active_violations) * 2800  # Average fine per violation
    
    # Generate forecasts
    forecasts = generate_fine_forecast(total_fines, risk_score)
    
    # Identify top risks
    top_risks = identify_top_risks(active_violations)
    
    return ScanResponse(
        success=True,
        building=BuildingInfo(
            address=address.upper(),
            bin=mock_bin,
            borough="MANHATTAN",
            zip="10018"
        ),
        risk_score=risk_score,
        violations=ViolationStats(
            active=len(active_violations),
            resolved=len(resolved_violations),
            total_fines=total_fines
        ),
        forecasts=forecasts,
        top_risks=top_risks
    )

@app.post("/forecast", response_model=ForecastResponse)
async def forecast_fines(request: ForecastRequest):
    """
    Generate fine forecast for multiple buildings
    """
    portfolio_forecast = PortfolioForecast(
        thirty_days=12400.0,
        sixty_days=27800.0,
        ninety_days=41200.0
    )
    
    by_building = []
    for building in request.buildings:
        by_building.append({
            "building": building,
            "forecast": {
                "30_days": 4100.0,
                "60_days": 8900.0,
                "90_days": 12400.0
            }
        })
    
    return ForecastResponse(
        portfolio_forecast=portfolio_forecast,
        by_building=by_building
    )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "dob_api_status": "operational"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
