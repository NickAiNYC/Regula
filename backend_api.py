"""
Regula Health - FastAPI Backend
Enterprise-grade behavioral health compliance platform
"""

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, date
from decimal import Decimal
import jwt
import hashlib
from passlib.context import CryptContext
from sqlalchemy import create_engine, Column, String, Numeric, Boolean, DateTime, Date, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
import re
from io import StringIO
import asyncio

# Configuration
SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

DATABASE_URL = "postgresql://regula:regula@localhost/regula_db"

# Database setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Security
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Initialize FastAPI
app = FastAPI(
    title="Regula Health API",
    description="NY Medicaid Rate Compliance Engine",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== DATABASE MODELS ====================

class Organization(Base):
    __tablename__ = "organizations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    ein = Column(String(9), unique=True)
    address = Column(JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    providers = relationship("Provider", back_populates="organization")
    users = relationship("User", back_populates="organization")

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"))
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    role = Column(String(50), default="provider")  # admin, provider, analyst
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    organization = relationship("Organization", back_populates="users")

class Provider(Base):
    __tablename__ = "providers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"))
    npi = Column(String(10), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    specialty = Column(String(100))
    geo_region = Column(String(20))  # nyc, longisland, upstate
    created_at = Column(DateTime, default=datetime.utcnow)
    
    organization = relationship("Organization", back_populates="providers")
    claims = relationship("Claim", back_populates="provider")

class Claim(Base):
    __tablename__ = "claims"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("providers.id"))
    claim_id = Column(String(50), nullable=False)
    payer = Column(String(100), nullable=False)
    dos = Column(Date, nullable=False)
    cpt_code = Column(String(10), nullable=False)
    mandate_rate = Column(Numeric(10, 2), nullable=False)
    paid_amount = Column(Numeric(10, 2), nullable=False)
    delta = Column(Numeric(10, 2), nullable=False)
    is_violation = Column(Boolean, nullable=False)
    geo_adjustment_factor = Column(Numeric(5, 3))
    processing_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    provider = relationship("Provider", back_populates="claims")
    appeals = relationship("Appeal", back_populates="claim")

class Appeal(Base):
    __tablename__ = "appeals"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_id = Column(UUID(as_uuid=True), ForeignKey("claims.id"))
    appeal_type = Column(String(50))  # internal, external, dfs_complaint
    filed_date = Column(Date, nullable=False)
    deadline = Column(Date, nullable=False)
    status = Column(String(50), default="pending")  # pending, approved, denied
    recovered_amount = Column(Numeric(10, 2))
    notes = Column(String)
    documents = Column(JSONB)  # Array of S3 URLs
    created_at = Column(DateTime, default=datetime.utcnow)
    
    claim = relationship("Claim", back_populates="appeals")

class RateDatabase(Base):
    __tablename__ = "rate_database"
    
    cpt_code = Column(String(10), primary_key=True)
    description = Column(String, nullable=False)
    category = Column(String(50))
    base_rate_2024 = Column(Numeric(10, 2), nullable=False)
    cola_rate_2025 = Column(Numeric(10, 2), nullable=False)
    effective_date = Column(Date, nullable=False)
    source = Column(String(255))

# Create all tables
Base.metadata.create_all(bind=engine)

# ==================== PYDANTIC MODELS ====================

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class UserCreate(BaseModel):
    email: str
    password: str
    full_name: str
    organization_name: str
    
    @validator('email')
    def email_must_be_valid(cls, v):
        if not re.match(r"[^@]+@[^@]+\.[^@]+", v):
            raise ValueError('Invalid email address')
        return v

class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    org_id: uuid.UUID
    
    class Config:
        orm_mode = True

class ClaimCreate(BaseModel):
    provider_id: uuid.UUID
    claim_id: str
    payer: str
    dos: date
    cpt_code: str
    mandate_rate: Decimal
    paid_amount: Decimal
    delta: Decimal
    is_violation: bool
    geo_adjustment_factor: Optional[Decimal] = None

class ClaimResponse(BaseModel):
    id: uuid.UUID
    provider_id: uuid.UUID
    claim_id: str
    payer: str
    dos: date
    cpt_code: str
    mandate_rate: Decimal
    paid_amount: Decimal
    delta: Decimal
    is_violation: bool
    created_at: datetime
    
    class Config:
        orm_mode = True

class DashboardMetrics(BaseModel):
    total_claims: int
    violations: int
    violation_rate: float
    total_recoverable: Decimal
    avg_underpayment: Decimal
    payer_stats: Dict[str, Any]
    category_stats: Dict[str, Any]
    trend_data: List[Dict[str, Any]]

class AppealCreate(BaseModel):
    claim_id: uuid.UUID
    appeal_type: str
    notes: Optional[str] = None

class AppealResponse(BaseModel):
    id: uuid.UUID
    claim_id: uuid.UUID
    appeal_type: str
    filed_date: date
    deadline: date
    status: str
    created_at: datetime
    
    class Config:
        orm_mode = True

# ==================== UTILITY FUNCTIONS ====================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except jwt.PyJWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.email == token_data.email).first()
    if user is None:
        raise credentials_exception
    return user

# NY Medicaid Rate Database with 2025 COLA (2.84%)
RATE_DATABASE_DATA = {
    "90837": {"base": 158.00, "cola2025": 162.49, "description": "Psychotherapy 60 min", "category": "Therapy"},
    "90834": {"base": 110.00, "cola2025": 113.12, "description": "Psychotherapy 45 min", "category": "Therapy"},
    "90791": {"base": 175.00, "cola2025": 179.97, "description": "Psychiatric Diagnostic Eval", "category": "Assessment"},
    "90832": {"base": 85.00, "cola2025": 87.41, "description": "Psychotherapy 30 min", "category": "Therapy"},
    "90846": {"base": 125.00, "cola2025": 128.55, "description": "Family Therapy w/o patient", "category": "Family"},
    "90847": {"base": 135.00, "cola2025": 138.83, "description": "Family Therapy w/ patient", "category": "Family"},
    "90853": {"base": 95.00, "cola2025": 97.70, "description": "Group Psychotherapy", "category": "Group"},
}

GEO_ADJUSTMENTS = {
    "nyc": 1.065,
    "longisland": 1.025,
    "upstate": 1.000
}

def parse_835_edi(content: str) -> List[Dict[str, Any]]:
    """Parse EDI 835 format and extract claim data"""
    claims_data = []
    segments = re.split(r'~|\n', content)
    
    current_clp_id = ""
    current_payer = ""
    current_dos = ""
    
    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue
        
        parts = seg.split('*')
        seg_id = parts[0] if parts else ""
        
        if seg_id == 'CLP':
            try:
                current_clp_id = parts[1] if len(parts) > 1 else ""
                current_payer = parts[7] if len(parts) > 7 else "Unknown Payer"
            except (ValueError, IndexError):
                continue
        
        elif seg_id == 'SVC':
            try:
                cpt_raw = parts[1] if len(parts) > 1 else ""
                cpt_code = cpt_raw.split(':')[-1] if ':' in cpt_raw else cpt_raw
                line_paid = float(parts[3]) if len(parts) > 3 else 0.0
                
                # Look up mandate rate
                if cpt_code in RATE_DATABASE_DATA:
                    rate_info = RATE_DATABASE_DATA[cpt_code]
                    mandate_rate = rate_info['cola2025']
                    
                    claims_data.append({
                        "claim_id": current_clp_id,
                        "payer": current_payer,
                        "dos": current_dos,
                        "cpt_code": cpt_code,
                        "description": rate_info['description'],
                        "category": rate_info['category'],
                        "mandate_rate": mandate_rate,
                        "paid_amount": line_paid
                    })
            except (ValueError, IndexError):
                continue
        
        elif seg_id == 'DTM' and len(parts) > 1:
            try:
                date_qual = parts[1]
                date_val = parts[2]
                if date_qual in ['150', '232', '011'] and len(date_val) >= 8:
                    current_dos = f"{date_val[:4]}-{date_val[4:6]}-{date_val[6:]}"
            except IndexError:
                continue
    
    return claims_data

# ==================== API ENDPOINTS ====================

@app.get("/")
async def root():
    return {
        "message": "Regula Health API",
        "version": "1.0.0",
        "status": "operational"
    }

@app.post("/api/v1/auth/register", response_model=UserResponse)
async def register(user: UserCreate, db: Session = Depends(get_db)):
    """Register new user and organization"""
    
    # Check if email exists
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create organization
    org = Organization(
        name=user.organization_name,
        ein=None  # Will be collected later
    )
    db.add(org)
    db.flush()
    
    # Create user
    new_user = User(
        org_id=org.id,
        email=user.email,
        hashed_password=get_password_hash(user.password),
        full_name=user.full_name,
        role="admin"  # First user is admin
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return new_user

@app.post("/api/v1/auth/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """OAuth2 compatible token login"""
    user = db.query(User).filter(User.email == form_data.username).first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/v1/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return current_user

@app.post("/api/v1/claims/upload")
async def upload_835_file(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload and parse EDI 835 file"""
    
    # Read file content
    content = await file.read()
    content_str = content.decode('utf-8')
    
    # Parse EDI
    parsed_claims = parse_835_edi(content_str)
    
    # Get provider (for now, use first provider in org)
    provider = db.query(Provider).filter(Provider.org_id == current_user.org_id).first()
    
    if not provider:
        raise HTTPException(status_code=400, detail="No provider found for organization")
    
    # Insert claims
    claims_created = []
    for claim_data in parsed_claims:
        # Calculate violation
        delta = claim_data['paid_amount'] - claim_data['mandate_rate']
        is_violation = delta < -0.01
        
        claim = Claim(
            provider_id=provider.id,
            claim_id=claim_data['claim_id'],
            payer=claim_data['payer'],
            dos=datetime.strptime(claim_data['dos'], '%Y-%m-%d').date() if claim_data['dos'] else datetime.utcnow().date(),
            cpt_code=claim_data['cpt_code'],
            mandate_rate=Decimal(str(claim_data['mandate_rate'])),
            paid_amount=Decimal(str(claim_data['paid_amount'])),
            delta=Decimal(str(delta)),
            is_violation=is_violation,
            geo_adjustment_factor=Decimal('1.065'),  # Default to NYC, should be configurable
            processing_date=datetime.utcnow()
        )
        db.add(claim)
        claims_created.append(claim)
    
    db.commit()
    
    return {
        "message": f"Successfully processed {len(claims_created)} claims",
        "claims_processed": len(claims_created),
        "violations_found": sum(1 for c in claims_created if c.is_violation)
    }

@app.get("/api/v1/claims", response_model=List[ClaimResponse])
async def get_claims(
    payer: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get claims for current user's organization"""
    
    query = db.query(Claim).join(Provider).filter(
        Provider.org_id == current_user.org_id
    )
    
    if payer:
        query = query.filter(Claim.payer == payer)
    
    claims = query.offset(skip).limit(limit).all()
    
    return claims

@app.get("/api/v1/analytics/dashboard", response_model=DashboardMetrics)
async def get_dashboard_metrics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get comprehensive dashboard metrics"""
    
    claims = db.query(Claim).join(Provider).filter(
        Provider.org_id == current_user.org_id
    ).all()
    
    violations = [c for c in claims if c.is_violation]
    
    total_recoverable = sum(abs(c.delta) for c in violations)
    avg_underpayment = total_recoverable / len(violations) if violations else Decimal('0')
    
    # Payer stats
    payer_stats = {}
    for claim in claims:
        if claim.payer not in payer_stats:
            payer_stats[claim.payer] = {"total": 0, "violations": 0, "recoverable": Decimal('0')}
        payer_stats[claim.payer]["total"] += 1
        if claim.is_violation:
            payer_stats[claim.payer]["violations"] += 1
            payer_stats[claim.payer]["recoverable"] += abs(claim.delta)
    
    # Category stats (would need to join with rate database in production)
    category_stats = {}
    
    # Trend data (simplified)
    trend_data = []
    
    return DashboardMetrics(
        total_claims=len(claims),
        violations=len(violations),
        violation_rate=len(violations) / len(claims) * 100 if claims else 0,
        total_recoverable=total_recoverable,
        avg_underpayment=avg_underpayment,
        payer_stats=payer_stats,
        category_stats=category_stats,
        trend_data=trend_data
    )

@app.post("/api/v1/appeals", response_model=AppealResponse)
async def create_appeal(
    appeal: AppealCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create new appeal for a claim"""
    
    # Verify claim belongs to user's org
    claim = db.query(Claim).join(Provider).filter(
        Claim.id == appeal.claim_id,
        Provider.org_id == current_user.org_id
    ).first()
    
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    
    # Calculate deadline (45 days from filing)
    filed_date = datetime.utcnow().date()
    deadline = filed_date + timedelta(days=45)
    
    new_appeal = Appeal(
        claim_id=appeal.claim_id,
        appeal_type=appeal.appeal_type,
        filed_date=filed_date,
        deadline=deadline,
        notes=appeal.notes
    )
    
    db.add(new_appeal)
    db.commit()
    db.refresh(new_appeal)
    
    return new_appeal

@app.get("/api/v1/reports/demand-letter/{claim_id}")
async def generate_demand_letter(
    claim_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate DFS demand letter for a specific claim"""
    
    claim = db.query(Claim).join(Provider).filter(
        Claim.id == claim_id,
        Provider.org_id == current_user.org_id
    ).first()
    
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    
    # In production, this would generate a PDF
    # For now, return structured data
    
    letter_content = {
        "date": datetime.utcnow().strftime("%B %d, %Y"),
        "payer": claim.payer,
        "claim_id": claim.claim_id,
        "provider": claim.provider.name,
        "violation_amount": float(abs(claim.delta)),
        "statutory_citations": [
            "NY Insurance Law §3221(l)(8)",
            "L.2024 c.57, Part AA",
            "MHPAEA (Federal)"
        ]
    }
    
    return letter_content

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)