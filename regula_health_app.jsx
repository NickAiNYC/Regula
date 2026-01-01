import React, { useState, useEffect } from 'react';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell, Area, AreaChart } from 'recharts';
import { AlertCircle, CheckCircle, TrendingUp, DollarSign, FileText, Download, Upload, Shield, AlertTriangle, Search, Filter, Users, Calendar, Building, Settings, ChevronRight, Eye, Mail, Clock, Target, Scale, BookOpen } from 'lucide-react';

const RegulaHealthApp = () => {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [uploadedFile, setUploadedFile] = useState(null);
  const [analysisData, setAnalysisData] = useState(null);
  const [selectedPayer, setSelectedPayer] = useState('all');
  const [dateRange, setDateRange] = useState('30');
  const [loading, setLoading] = useState(false);

  // NY Medicaid Rate Database (2025 with 2.84% COLA)
  const RATE_DATABASE = {
    "90837": { base: 158.00, cola2025: 162.49, description: "Psychotherapy 60 min", category: "Therapy" },
    "90834": { base: 110.00, cola2025: 113.12, description: "Psychotherapy 45 min", category: "Therapy" },
    "90791": { base: 175.00, cola2025: 179.97, description: "Psychiatric Diagnostic Eval", category: "Assessment" },
    "90832": { base: 85.00, cola2025: 87.41, description: "Psychotherapy 30 min", category: "Therapy" },
    "90846": { base: 125.00, cola2025: 128.55, description: "Family Therapy w/o patient", category: "Family" },
    "90847": { base: 135.00, cola2025: 138.83, description: "Family Therapy w/ patient", category: "Family" },
    "90853": { base: 95.00, cola2025: 97.70, description: "Group Psychotherapy", category: "Group" },
    "H0032": { base: 68.00, cola2025: 69.93, description: "Mental Health Service", category: "Community" },
    "96127": { base: 45.00, cola2025: 46.28, description: "Brief Emotional/Behavioral Assessment", category: "Assessment" }
  };

  // Geographic adjustment factors
  const GEO_ADJUSTMENTS = {
    "nyc": { factor: 1.065, label: "New York City Metro" },
    "longisland": { factor: 1.025, label: "Long Island" },
    "upstate": { factor: 1.000, label: "Upstate NY" }
  };

  // Sample parsed data simulation
  const generateSampleAnalysis = () => {
    setLoading(true);
    
    setTimeout(() => {
      const claims = [];
      const payers = ['Aetna', 'United Healthcare', 'Cigna', 'Blue Cross Blue Shield', 'Oscar Health'];
      const providers = ['Dr. Sarah Johnson', 'Dr. Michael Chen', 'Dr. Emily Rodriguez', 'Dr. James Williams', 'Dr. Lisa Anderson'];
      const geoRegions = Object.keys(GEO_ADJUSTMENTS);
      
      for (let i = 0; i < 147; i++) {
        const cptCode = Object.keys(RATE_DATABASE)[Math.floor(Math.random() * Object.keys(RATE_DATABASE).length)];
        const rateInfo = RATE_DATABASE[cptCode];
        const geoRegion = geoRegions[Math.floor(Math.random() * geoRegions.length)];
        const geoFactor = GEO_ADJUSTMENTS[geoRegion].factor;
        const mandateRate = rateInfo.cola2025 * geoFactor;
        
        // Simulate some underpayments
        const isUnderpaid = Math.random() > 0.35;
        const paidAmount = isUnderpaid 
          ? mandateRate * (0.65 + Math.random() * 0.25) 
          : mandateRate * (1.0 + Math.random() * 0.15);
        
        const claim = {
          claimId: `CLM-2025-${1000 + i}`,
          payer: payers[Math.floor(Math.random() * payers.length)],
          provider: providers[Math.floor(Math.random() * providers.length)],
          dos: new Date(2025, Math.floor(Math.random() * 12), Math.floor(Math.random() * 28) + 1).toISOString().split('T')[0],
          cptCode: cptCode,
          description: rateInfo.description,
          category: rateInfo.category,
          geoRegion: geoRegion,
          geoLabel: GEO_ADJUSTMENTS[geoRegion].label,
          mandateRate: mandateRate,
          paidAmount: parseFloat(paidAmount.toFixed(2)),
          delta: parseFloat((paidAmount - mandateRate).toFixed(2)),
          isViolation: paidAmount < mandateRate - 0.01,
          violationPercent: paidAmount < mandateRate ? ((mandateRate - paidAmount) / mandateRate * 100).toFixed(1) : 0,
          processingDate: new Date(2025, Math.floor(Math.random() * 12), Math.floor(Math.random() * 28) + 1).toISOString().split('T')[0]
        };
        
        claims.push(claim);
      }
      
      setAnalysisData(claims);
      setLoading(false);
    }, 1500);
  };

  useEffect(() => {
    generateSampleAnalysis();
  }, []);

  // Calculate metrics
  const calculateMetrics = () => {
    if (!analysisData) return null;
    
    const filteredData = selectedPayer === 'all' 
      ? analysisData 
      : analysisData.filter(c => c.payer === selectedPayer);
    
    const violations = filteredData.filter(c => c.isViolation);
    const totalRecoverable = violations.reduce((sum, c) => sum + Math.abs(c.delta), 0);
    const avgUnderpayment = violations.length > 0 ? totalRecoverable / violations.length : 0;
    const violationRate = (violations.length / filteredData.length * 100).toFixed(1);
    
    // Payer breakdown
    const payerStats = {};
    filteredData.forEach(claim => {
      if (!payerStats[claim.payer]) {
        payerStats[claim.payer] = { total: 0, violations: 0, recoverable: 0 };
      }
      payerStats[claim.payer].total++;
      if (claim.isViolation) {
        payerStats[claim.payer].violations++;
        payerStats[claim.payer].recoverable += Math.abs(claim.delta);
      }
    });
    
    // Category breakdown
    const categoryStats = {};
    filteredData.forEach(claim => {
      if (!categoryStats[claim.category]) {
        categoryStats[claim.category] = { total: 0, violations: 0, recoverable: 0 };
      }
      categoryStats[claim.category].total++;
      if (claim.isViolation) {
        categoryStats[claim.category].violations++;
        categoryStats[claim.category].recoverable += Math.abs(claim.delta);
      }
    });
    
    // Trend data (monthly)
    const monthlyTrends = {};
    filteredData.forEach(claim => {
      const month = claim.dos.substring(0, 7);
      if (!monthlyTrends[month]) {
        monthlyTrends[month] = { violations: 0, recoverable: 0 };
      }
      if (claim.isViolation) {
        monthlyTrends[month].violations++;
        monthlyTrends[month].recoverable += Math.abs(claim.delta);
      }
    });
    
    const trendData = Object.keys(monthlyTrends).sort().map(month => ({
      month: month,
      violations: monthlyTrends[month].violations,
      recoverable: monthlyTrends[month].recoverable
    }));
    
    return {
      totalClaims: filteredData.length,
      violations: violations.length,
      violationRate,
      totalRecoverable,
      avgUnderpayment,
      payerStats,
      categoryStats,
      trendData,
      topViolations: violations.sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta)).slice(0, 10)
    };
  };

  const metrics = calculateMetrics();

  // Dashboard Component
  const DashboardView = () => {
    if (!metrics) return <div className="loading-state">Analyzing compliance data...</div>;
    
    const payerChartData = Object.keys(metrics.payerStats).map(payer => ({
      name: payer,
      violations: metrics.payerStats[payer].violations,
      recoverable: metrics.payerStats[payer].recoverable
    }));
    
    const categoryChartData = Object.keys(metrics.categoryStats).map(cat => ({
      name: cat,
      violations: metrics.categoryStats[cat].violations,
      recoverable: metrics.categoryStats[cat].recoverable
    }));
    
    const COLORS = ['#ef4444', '#f97316', '#f59e0b', '#eab308', '#84cc16'];
    
    return (
      <div className="dashboard-grid">
        {/* Key Metrics */}
        <div className="metrics-row">
          <div className="metric-card primary">
            <div className="metric-icon">
              <Shield size={28} />
            </div>
            <div className="metric-content">
              <div className="metric-label">Total Claims Analyzed</div>
              <div className="metric-value">{metrics.totalClaims.toLocaleString()}</div>
              <div className="metric-subtitle">Across all payers</div>
            </div>
          </div>
          
          <div className="metric-card danger">
            <div className="metric-icon">
              <AlertTriangle size={28} />
            </div>
            <div className="metric-content">
              <div className="metric-label">Compliance Violations</div>
              <div className="metric-value">{metrics.violations}</div>
              <div className="metric-subtitle">{metrics.violationRate}% violation rate</div>
            </div>
          </div>
          
          <div className="metric-card success">
            <div className="metric-icon">
              <DollarSign size={28} />
            </div>
            <div className="metric-content">
              <div className="metric-label">Total Recoverable</div>
              <div className="metric-value">${metrics.totalRecoverable.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>
              <div className="metric-subtitle">Available for appeal</div>
            </div>
          </div>
          
          <div className="metric-card info">
            <div className="metric-icon">
              <TrendingUp size={28} />
            </div>
            <div className="metric-content">
              <div className="metric-label">Avg Underpayment</div>
              <div className="metric-value">${metrics.avgUnderpayment.toFixed(2)}</div>
              <div className="metric-subtitle">Per violation</div>
            </div>
          </div>
        </div>
        
        {/* Charts Section */}
        <div className="charts-row">
          <div className="chart-card wide">
            <div className="chart-header">
              <h3>Monthly Violation Trends</h3>
              <div className="chart-legend">
                <span className="legend-item"><div className="legend-dot red"></div>Violations</span>
                <span className="legend-item"><div className="legend-dot blue"></div>Recoverable Amount</span>
              </div>
            </div>
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={metrics.trendData}>
                <defs>
                  <linearGradient id="colorViolations" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#ef4444" stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="colorRecoverable" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" />
                <XAxis dataKey="month" stroke="#666" />
                <YAxis stroke="#666" />
                <Tooltip contentStyle={{backgroundColor: '#1a1a1a', border: '1px solid #333'}} />
                <Area type="monotone" dataKey="violations" stroke="#ef4444" fillOpacity={1} fill="url(#colorViolations)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          
          <div className="chart-card">
            <div className="chart-header">
              <h3>Violations by Service Category</h3>
            </div>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={categoryChartData}
                  dataKey="violations"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={100}
                  label={(entry) => `${entry.name}: ${entry.violations}`}
                >
                  {categoryChartData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{backgroundColor: '#1a1a1a', border: '1px solid #333'}} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
        
        <div className="charts-row">
          <div className="chart-card wide">
            <div className="chart-header">
              <h3>Payer Compliance Performance</h3>
              <div className="chart-subtitle">Recoverable amount by insurance carrier</div>
            </div>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={payerChartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" />
                <XAxis dataKey="name" stroke="#666" angle={-15} textAnchor="end" height={80} />
                <YAxis stroke="#666" />
                <Tooltip contentStyle={{backgroundColor: '#1a1a1a', border: '1px solid #333'}} />
                <Bar dataKey="recoverable" fill="#ef4444" radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    );
  };

  // Claims List View
  const ClaimsView = () => {
    if (!analysisData) return null;
    
    const filteredClaims = selectedPayer === 'all' 
      ? analysisData 
      : analysisData.filter(c => c.payer === selectedPayer);
    
    const violations = filteredClaims.filter(c => c.isViolation);
    
    return (
      <div className="claims-container">
        <div className="claims-header">
          <div className="claims-header-left">
            <h2>Claims Analysis</h2>
            <div className="claims-stats">
              <span className="stat-badge danger">{violations.length} Violations</span>
              <span className="stat-badge success">{filteredClaims.length - violations.length} Compliant</span>
            </div>
          </div>
          <div className="claims-filters">
            <select value={selectedPayer} onChange={(e) => setSelectedPayer(e.target.value)} className="filter-select">
              <option value="all">All Payers</option>
              {[...new Set(analysisData.map(c => c.payer))].map(payer => (
                <option key={payer} value={payer}>{payer}</option>
              ))}
            </select>
          </div>
        </div>
        
        <div className="claims-table-container">
          <table className="claims-table">
            <thead>
              <tr>
                <th>Claim ID</th>
                <th>DOS</th>
                <th>Payer</th>
                <th>Provider</th>
                <th>CPT</th>
                <th>Service</th>
                <th>Region</th>
                <th>Mandate Rate</th>
                <th>Paid Amount</th>
                <th>Delta</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {violations.slice(0, 50).map((claim, idx) => (
                <tr key={idx} className={claim.isViolation ? 'violation-row' : ''}>
                  <td className="claim-id">{claim.claimId}</td>
                  <td>{claim.dos}</td>
                  <td>{claim.payer}</td>
                  <td className="provider-name">{claim.provider}</td>
                  <td className="cpt-code">{claim.cptCode}</td>
                  <td className="service-desc">{claim.description}</td>
                  <td>{claim.geoLabel}</td>
                  <td className="amount">${claim.mandateRate.toFixed(2)}</td>
                  <td className="amount">${claim.paidAmount.toFixed(2)}</td>
                  <td className={claim.delta < 0 ? 'amount negative' : 'amount positive'}>
                    ${Math.abs(claim.delta).toFixed(2)}
                  </td>
                  <td>
                    {claim.isViolation ? (
                      <span className="status-badge violation">
                        <AlertCircle size={14} /> Violation
                      </span>
                    ) : (
                      <span className="status-badge compliant">
                        <CheckCircle size={14} /> Compliant
                      </span>
                    )}
                  </td>
                  <td>
                    <button className="action-btn">
                      <Eye size={16} /> Review
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  // Regulatory Framework View
  const RegulatoryView = () => {
    return (
      <div className="regulatory-container">
        <div className="regulatory-header">
          <Scale size={32} />
          <h2>Regulatory Compliance Framework</h2>
          <p>NY Behavioral Health Parity Mandate (L.2024 c.57, Part AA)</p>
        </div>
        
        <div className="regulatory-cards">
          <div className="reg-card">
            <div className="reg-card-header">
              <BookOpen size={24} />
              <h3>NY Insurance Law §3221(l)(8)</h3>
            </div>
            <div className="reg-card-content">
              <p className="reg-citation">
                <strong>Effective:</strong> January 1, 2025
              </p>
              <p>
                Commercial health insurers operating in New York State must reimburse 
                behavioral health services at rates no less than the applicable Medicaid 
                fee-for-service rates, adjusted for geographic region and annual COLA increases.
              </p>
              <div className="reg-requirements">
                <h4>Key Requirements:</h4>
                <ul>
                  <li>Minimum reimbursement floor tied to NY Medicaid rates</li>
                  <li>Geographic adjustment factors (NYC: 1.065, LI: 1.025, Upstate: 1.000)</li>
                  <li>Annual COLA adjustments (2025: 2.84% increase)</li>
                  <li>Applies to all CPT codes for outpatient behavioral health services</li>
                </ul>
              </div>
            </div>
          </div>
          
          <div className="reg-card">
            <div className="reg-card-header">
              <Shield size={24} />
              <h3>Federal MHPAEA Compliance</h3>
            </div>
            <div className="reg-card-content">
              <p className="reg-citation">
                <strong>Mental Health Parity and Addiction Equity Act</strong>
              </p>
              <p>
                Federal regulations prohibit discriminatory non-quantitative treatment 
                limitations (NQTLs) in behavioral health coverage, including reimbursement 
                rate disparities that create access barriers.
              </p>
              <div className="reg-requirements">
                <h4>Enforcement Actions:</h4>
                <ul>
                  <li>DOL strengthened enforcement rules (effective 2024)</li>
                  <li>Comparative analysis requirements for NQTLs</li>
                  <li>Penalties for systematic underpayment patterns</li>
                  <li>State coordination with federal regulators</li>
                </ul>
              </div>
            </div>
          </div>
          
          <div className="reg-card">
            <div className="reg-card-header">
              <AlertTriangle size={24} />
              <h3>DFS Enforcement & Appeals</h3>
            </div>
            <div className="reg-card-content">
              <p className="reg-citation">
                <strong>NY Department of Financial Services</strong>
              </p>
              <p>
                Providers have the right to appeal underpayments and file complaints with 
                DFS for systematic violations. DFS has authority to levy fines and require 
                retroactive payment adjustments.
              </p>
              <div className="reg-requirements">
                <h4>Provider Rights:</h4>
                <ul>
                  <li>45-day appeal window from EOB receipt</li>
                  <li>Right to external review for denied appeals</li>
                  <li>DFS complaint filing for systematic violations</li>
                  <li>Retroactive payment adjustment for proven violations</li>
                </ul>
              </div>
            </div>
          </div>
          
          <div className="reg-card full-width">
            <div className="reg-card-header">
              <FileText size={24} />
              <h3>2025 Rate Schedule (with 2.84% COLA)</h3>
            </div>
            <div className="reg-card-content">
              <div className="rate-table">
                <table>
                  <thead>
                    <tr>
                      <th>CPT Code</th>
                      <th>Service Description</th>
                      <th>Category</th>
                      <th>Base Rate (2024)</th>
                      <th>2025 Rate (w/ COLA)</th>
                      <th>NYC Rate</th>
                      <th>LI Rate</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.keys(RATE_DATABASE).map(code => {
                      const rate = RATE_DATABASE[code];
                      return (
                        <tr key={code}>
                          <td className="code-cell">{code}</td>
                          <td>{rate.description}</td>
                          <td><span className="category-badge">{rate.category}</span></td>
                          <td className="rate-cell">${rate.base.toFixed(2)}</td>
                          <td className="rate-cell highlight">${rate.cola2025.toFixed(2)}</td>
                          <td className="rate-cell">${(rate.cola2025 * 1.065).toFixed(2)}</td>
                          <td className="rate-cell">${(rate.cola2025 * 1.025).toFixed(2)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  // Reports View
  const ReportsView = () => {
    if (!metrics) return null;
    
    return (
      <div className="reports-container">
        <div className="reports-header">
          <h2>Compliance Reports & Documentation</h2>
          <p>Generate statutory demand letters and audit documentation</p>
        </div>
        
        <div className="report-cards">
          <div className="report-card">
            <div className="report-icon">
              <FileText size={40} />
            </div>
            <h3>DFS Demand Letter</h3>
            <p>Auto-generated statutory demand letter with violation details and regulatory citations</p>
            <div className="report-stats">
              <span>{metrics.violations} violations documented</span>
              <span>${metrics.totalRecoverable.toFixed(2)} total demand</span>
            </div>
            <button className="report-btn primary">
              <Download size={18} />
              Generate Letter
            </button>
          </div>
          
          <div className="report-card">
            <div className="report-icon">
              <Scale size={40} />
            </div>
            <h3>Appeal Documentation Package</h3>
            <p>Complete appeal documentation with claim-level analysis and supporting evidence</p>
            <div className="report-stats">
              <span>Ready for submission</span>
              <span>45-day deadline tracking</span>
            </div>
            <button className="report-btn primary">
              <Download size={18} />
              Generate Package
            </button>
          </div>
          
          <div className="report-card">
            <div className="report-icon">
              <TrendingUp size={40} />
            </div>
            <h3>Executive Summary Report</h3>
            <p>High-level compliance metrics and trend analysis for leadership review</p>
            <div className="report-stats">
              <span>Board-ready format</span>
              <span>Quarterly trends included</span>
            </div>
            <button className="report-btn primary">
              <Download size={18} />
              Generate Report
            </button>
          </div>
          
          <div className="report-card">
            <div className="report-icon">
              <Building size={40} />
            </div>
            <h3>Payer-Specific Analysis</h3>
            <p>Detailed breakdown of violations by insurance carrier with historical patterns</p>
            <div className="report-stats">
              <span>{Object.keys(metrics.payerStats).length} payers analyzed</span>
              <span>Pattern recognition enabled</span>
            </div>
            <button className="report-btn primary">
              <Download size={18} />
              Generate Analysis
            </button>
          </div>
        </div>
        
        <div className="audit-trail">
          <h3>Recent Activity & Audit Trail</h3>
          <div className="audit-log">
            <div className="audit-item">
              <Clock size={18} />
              <div className="audit-content">
                <div className="audit-title">Batch Analysis Completed</div>
                <div className="audit-meta">147 claims processed • 2 minutes ago</div>
              </div>
            </div>
            <div className="audit-item">
              <FileText size={18} />
              <div className="audit-content">
                <div className="audit-title">DFS Demand Letter Generated</div>
                <div className="audit-meta">United Healthcare • 15 minutes ago</div>
              </div>
            </div>
            <div className="audit-item">
              <Mail size={18} />
              <div className="audit-content">
                <div className="audit-title">Appeal Package Submitted</div>
                <div className="audit-meta">Aetna - 23 violations • 1 hour ago</div>
              </div>
            </div>
            <div className="audit-item">
              <Target size={18} />
              <div className="audit-content">
                <div className="audit-title">Compliance Threshold Alert</div>
                <div className="audit-meta">Cigna violation rate exceeded 40% • 3 hours ago</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="regula-app">
      {/* Header */}
      <header className="app-header">
        <div className="header-left">
          <div className="logo">
            <Scale size={32} />
            <div className="logo-text">
              <h1>Regula Health</h1>
              <span className="tagline">NY Medicaid Rate Compliance Engine</span>
            </div>
          </div>
        </div>
        <div className="header-right">
          <button className="header-btn">
            <Upload size={18} />
            Import 835 ERA
          </button>
          <button className="header-btn">
            <Users size={18} />
          </button>
          <button className="header-btn">
            <Settings size={18} />
          </button>
        </div>
      </header>
      
      {/* Navigation */}
      <nav className="app-nav">
        <button 
          className={`nav-item ${activeTab === 'dashboard' ? 'active' : ''}`}
          onClick={() => setActiveTab('dashboard')}
        >
          <TrendingUp size={20} />
          Dashboard
        </button>
        <button 
          className={`nav-item ${activeTab === 'claims' ? 'active' : ''}`}
          onClick={() => setActiveTab('claims')}
        >
          <FileText size={20} />
          Claims Analysis
        </button>
        <button 
          className={`nav-item ${activeTab === 'regulatory' ? 'active' : ''}`}
          onClick={() => setActiveTab('regulatory')}
        >
          <BookOpen size={20} />
          Regulatory Framework
        </button>
        <button 
          className={`nav-item ${activeTab === 'reports' ? 'active' : ''}`}
          onClick={() => setActiveTab('reports')}
        >
          <Download size={20} />
          Reports & Appeals
        </button>
      </nav>
      
      {/* Main Content */}
      <main className="app-content">
        {loading ? (
          <div className="loading-container">
            <div className="loading-spinner"></div>
            <p>Analyzing compliance data...</p>
          </div>
        ) : (
          <>
            {activeTab === 'dashboard' && <DashboardView />}
            {activeTab === 'claims' && <ClaimsView />}
            {activeTab === 'regulatory' && <RegulatoryView />}
            {activeTab === 'reports' && <ReportsView />}
          </>
        )}
      </main>
      
      {/* Footer */}
      <footer className="app-footer">
        <div className="footer-content">
          <div className="footer-left">
            <span>© 2025 Regula Health</span>
            <span className="separator">•</span>
            <span>HIPAA Compliant</span>
            <span className="separator">•</span>
            <span>Data Encrypted</span>
          </div>
          <div className="footer-right">
            <span className="status-indicator">
              <div className="status-dot"></div>
              System Operational
            </span>
          </div>
        </div>
      </footer>
      
      <style jsx>{`
        * {
          margin: 0;
          padding: 0;
          box-sizing: border-box;
        }
        
        .regula-app {
          font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
          background: linear-gradient(135deg, #0a0a0a 0%, #1a1a1a 100%);
          min-height: 100vh;
          color: #e5e5e5;
          display: flex;
          flex-direction: column;
        }
        
        /* Header */
        .app-header {
          background: rgba(20, 20, 20, 0.95);
          backdrop-filter: blur(20px);
          border-bottom: 1px solid rgba(255, 255, 255, 0.08);
          padding: 1rem 2rem;
          display: flex;
          justify-content: space-between;
          align-items: center;
          position: sticky;
          top: 0;
          z-index: 100;
        }
        
        .header-left {
          display: flex;
          align-items: center;
          gap: 2rem;
        }
        
        .logo {
          display: flex;
          align-items: center;
          gap: 0.75rem;
        }
        
        .logo svg {
          color: #ef4444;
        }
        
        .logo-text h1 {
          font-size: 1.5rem;
          font-weight: 700;
          color: #ffffff;
          line-height: 1;
          margin-bottom: 0.25rem;
        }
        
        .tagline {
          font-size: 0.75rem;
          color: #888;
          letter-spacing: 0.5px;
          text-transform: uppercase;
        }
        
        .header-right {
          display: flex;
          gap: 1rem;
        }
        
        .header-btn {
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid rgba(255, 255, 255, 0.1);
          color: #e5e5e5;
          padding: 0.625rem 1.25rem;
          border-radius: 8px;
          cursor: pointer;
          display: flex;
          align-items: center;
          gap: 0.5rem;
          font-size: 0.875rem;
          font-weight: 500;
          transition: all 0.2s;
        }
        
        .header-btn:hover {
          background: rgba(239, 68, 68, 0.1);
          border-color: #ef4444;
          transform: translateY(-1px);
        }
        
        /* Navigation */
        .app-nav {
          background: rgba(25, 25, 25, 0.8);
          backdrop-filter: blur(10px);
          border-bottom: 1px solid rgba(255, 255, 255, 0.08);
          padding: 0 2rem;
          display: flex;
          gap: 0.5rem;
          position: sticky;
          top: 73px;
          z-index: 90;
        }
        
        .nav-item {
          background: transparent;
          border: none;
          color: #999;
          padding: 1rem 1.5rem;
          cursor: pointer;
          display: flex;
          align-items: center;
          gap: 0.5rem;
          font-size: 0.9rem;
          font-weight: 500;
          border-bottom: 2px solid transparent;
          transition: all 0.2s;
        }
        
        .nav-item:hover {
          color: #e5e5e5;
          background: rgba(255, 255, 255, 0.03);
        }
        
        .nav-item.active {
          color: #ef4444;
          border-bottom-color: #ef4444;
        }
        
        /* Main Content */
        .app-content {
          flex: 1;
          padding: 2rem;
          max-width: 1600px;
          width: 100%;
          margin: 0 auto;
        }
        
        /* Dashboard Grid */
        .dashboard-grid {
          display: flex;
          flex-direction: column;
          gap: 2rem;
        }
        
        .metrics-row {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 1.5rem;
        }
        
        .metric-card {
          background: linear-gradient(135deg, rgba(30, 30, 30, 0.9) 0%, rgba(20, 20, 20, 0.9) 100%);
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 16px;
          padding: 1.5rem;
          display: flex;
          gap: 1rem;
          position: relative;
          overflow: hidden;
          transition: all 0.3s;
        }
        
        .metric-card::before {
          content: '';
          position: absolute;
          top: 0;
          left: 0;
          right: 0;
          height: 3px;
          background: linear-gradient(90deg, transparent, rgba(239, 68, 68, 0.5), transparent);
        }
        
        .metric-card.primary::before { background: linear-gradient(90deg, transparent, rgba(59, 130, 246, 0.5), transparent); }
        .metric-card.danger::before { background: linear-gradient(90deg, transparent, rgba(239, 68, 68, 0.5), transparent); }
        .metric-card.success::before { background: linear-gradient(90deg, transparent, rgba(34, 197, 94, 0.5), transparent); }
        .metric-card.info::before { background: linear-gradient(90deg, transparent, rgba(168, 85, 247, 0.5), transparent); }
        
        .metric-card:hover {
          transform: translateY(-4px);
          border-color: rgba(239, 68, 68, 0.3);
          box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
        }
        
        .metric-icon {
          width: 48px;
          height: 48px;
          border-radius: 12px;
          display: flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
        }
        
        .metric-card.primary .metric-icon {
          background: linear-gradient(135deg, rgba(59, 130, 246, 0.2), rgba(37, 99, 235, 0.1));
          color: #3b82f6;
        }
        
        .metric-card.danger .metric-icon {
          background: linear-gradient(135deg, rgba(239, 68, 68, 0.2), rgba(220, 38, 38, 0.1));
          color: #ef4444;
        }
        
        .metric-card.success .metric-icon {
          background: linear-gradient(135deg, rgba(34, 197, 94, 0.2), rgba(22, 163, 74, 0.1));
          color: #22c55e;
        }
        
        .metric-card.info .metric-icon {
          background: linear-gradient(135deg, rgba(168, 85, 247, 0.2), rgba(147, 51, 234, 0.1));
          color: #a855f7;
        }
        
        .metric-content {
          flex: 1;
        }
        
        .metric-label {
          font-size: 0.8rem;
          color: #888;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          margin-bottom: 0.5rem;
        }
        
        .metric-value {
          font-size: 2rem;
          font-weight: 700;
          color: #ffffff;
          line-height: 1;
          margin-bottom: 0.5rem;
        }
        
        .metric-subtitle {
          font-size: 0.85rem;
          color: #666;
        }
        
        /* Charts */
        .charts-row {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 1.5rem;
        }
        
        .chart-card {
          background: linear-gradient(135deg, rgba(30, 30, 30, 0.9) 0%, rgba(20, 20, 20, 0.9) 100%);
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 16px;
          padding: 1.5rem;
        }
        
        .chart-card.wide {
          grid-column: span 2;
        }
        
        .chart-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 1.5rem;
        }
        
        .chart-header h3 {
          font-size: 1.1rem;
          color: #ffffff;
          font-weight: 600;
        }
        
        .chart-subtitle {
          font-size: 0.85rem;
          color: #666;
          margin-top: 0.25rem;
        }
        
        .chart-legend {
          display: flex;
          gap: 1.5rem;
        }
        
        .legend-item {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          font-size: 0.85rem;
          color: #999;
        }
        
        .legend-dot {
          width: 10px;
          height: 10px;
          border-radius: 50%;
        }
        
        .legend-dot.red { background: #ef4444; }
        .legend-dot.blue { background: #3b82f6; }
        
        /* Claims View */
        .claims-container {
          display: flex;
          flex-direction: column;
          gap: 1.5rem;
        }
        
        .claims-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding-bottom: 1rem;
          border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        }
        
        .claims-header-left h2 {
          font-size: 1.8rem;
          color: #ffffff;
          margin-bottom: 0.5rem;
        }
        
        .claims-stats {
          display: flex;
          gap: 0.75rem;
        }
        
        .stat-badge {
          padding: 0.375rem 0.875rem;
          border-radius: 20px;
          font-size: 0.8rem;
          font-weight: 600;
        }
        
        .stat-badge.danger {
          background: rgba(239, 68, 68, 0.15);
          color: #ef4444;
          border: 1px solid rgba(239, 68, 68, 0.3);
        }
        
        .stat-badge.success {
          background: rgba(34, 197, 94, 0.15);
          color: #22c55e;
          border: 1px solid rgba(34, 197, 94, 0.3);
        }
        
        .claims-filters {
          display: flex;
          gap: 1rem;
        }
        
        .filter-select {
          background: rgba(30, 30, 30, 0.9);
          border: 1px solid rgba(255, 255, 255, 0.1);
          color: #e5e5e5;
          padding: 0.625rem 1rem;
          border-radius: 8px;
          font-size: 0.9rem;
          cursor: pointer;
        }
        
        .claims-table-container {
          background: linear-gradient(135deg, rgba(30, 30, 30, 0.9) 0%, rgba(20, 20, 20, 0.9) 100%);
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 16px;
          overflow: hidden;
        }
        
        .claims-table {
          width: 100%;
          border-collapse: collapse;
        }
        
        .claims-table thead {
          background: rgba(20, 20, 20, 0.8);
          border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .claims-table th {
          padding: 1rem;
          text-align: left;
          font-size: 0.8rem;
          font-weight: 600;
          color: #888;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }
        
        .claims-table td {
          padding: 1rem;
          border-bottom: 1px solid rgba(255, 255, 255, 0.05);
          font-size: 0.9rem;
        }
        
        .claims-table tbody tr {
          transition: background 0.2s;
        }
        
        .claims-table tbody tr:hover {
          background: rgba(255, 255, 255, 0.03);
        }
        
        .claims-table tbody tr.violation-row {
          background: rgba(239, 68, 68, 0.03);
        }
        
        .claim-id {
          font-family: 'Courier New', monospace;
          color: #3b82f6;
          font-size: 0.85rem;
        }
        
        .provider-name {
          font-weight: 500;
          color: #e5e5e5;
        }
        
        .cpt-code {
          font-family: 'Courier New', monospace;
          font-weight: 600;
          color: #a855f7;
        }
        
        .service-desc {
          color: #999;
          font-size: 0.85rem;
        }
        
        .amount {
          font-family: 'Courier New', monospace;
          font-weight: 600;
        }
        
        .amount.negative {
          color: #ef4444;
        }
        
        .amount.positive {
          color: #22c55e;
        }
        
        .status-badge {
          display: inline-flex;
          align-items: center;
          gap: 0.375rem;
          padding: 0.375rem 0.75rem;
          border-radius: 20px;
          font-size: 0.75rem;
          font-weight: 600;
        }
        
        .status-badge.violation {
          background: rgba(239, 68, 68, 0.15);
          color: #ef4444;
          border: 1px solid rgba(239, 68, 68, 0.3);
        }
        
        .status-badge.compliant {
          background: rgba(34, 197, 94, 0.15);
          color: #22c55e;
          border: 1px solid rgba(34, 197, 94, 0.3);
        }
        
        .action-btn {
          background: rgba(59, 130, 246, 0.1);
          border: 1px solid rgba(59, 130, 246, 0.3);
          color: #3b82f6;
          padding: 0.5rem 0.875rem;
          border-radius: 6px;
          cursor: pointer;
          display: inline-flex;
          align-items: center;
          gap: 0.375rem;
          font-size: 0.8rem;
          font-weight: 500;
          transition: all 0.2s;
        }
        
        .action-btn:hover {
          background: rgba(59, 130, 246, 0.2);
          transform: translateY(-1px);
        }
        
        /* Regulatory View */
        .regulatory-container {
          display: flex;
          flex-direction: column;
          gap: 2rem;
        }
        
        .regulatory-header {
          text-align: center;
          padding: 2rem 0;
          border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        }
        
        .regulatory-header svg {
          color: #ef4444;
          margin-bottom: 1rem;
        }
        
        .regulatory-header h2 {
          font-size: 2rem;
          color: #ffffff;
          margin-bottom: 0.5rem;
        }
        
        .regulatory-header p {
          color: #888;
          font-size: 1rem;
        }
        
        .regulatory-cards {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 1.5rem;
        }
        
        .reg-card {
          background: linear-gradient(135deg, rgba(30, 30, 30, 0.9) 0%, rgba(20, 20, 20, 0.9) 100%);
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 16px;
          overflow: hidden;
        }
        
        .reg-card.full-width {
          grid-column: span 2;
        }
        
        .reg-card-header {
          background: rgba(20, 20, 20, 0.8);
          padding: 1.5rem;
          border-bottom: 1px solid rgba(255, 255, 255, 0.08);
          display: flex;
          align-items: center;
          gap: 1rem;
        }
        
        .reg-card-header svg {
          color: #ef4444;
        }
        
        .reg-card-header h3 {
          font-size: 1.2rem;
          color: #ffffff;
        }
        
        .reg-card-content {
          padding: 1.5rem;
        }
        
        .reg-citation {
          background: rgba(239, 68, 68, 0.1);
          border-left: 3px solid #ef4444;
          padding: 0.75rem 1rem;
          margin-bottom: 1rem;
          font-size: 0.9rem;
          color: #e5e5e5;
        }
        
        .reg-card-content p {
          color: #999;
          line-height: 1.7;
          margin-bottom: 1.5rem;
        }
        
        .reg-requirements h4 {
          color: #ffffff;
          font-size: 1rem;
          margin-bottom: 0.75rem;
        }
        
        .reg-requirements ul {
          list-style: none;
          padding: 0;
        }
        
        .reg-requirements li {
          color: #999;
          padding: 0.5rem 0;
          padding-left: 1.5rem;
          position: relative;
          line-height: 1.6;
        }
        
        .reg-requirements li::before {
          content: '▸';
          position: absolute;
          left: 0;
          color: #ef4444;
        }
        
        .rate-table {
          overflow-x: auto;
        }
        
        .rate-table table {
          width: 100%;
          border-collapse: collapse;
        }
        
        .rate-table thead {
          background: rgba(20, 20, 20, 0.8);
        }
        
        .rate-table th {
          padding: 1rem;
          text-align: left;
          font-size: 0.8rem;
          font-weight: 600;
          color: #888;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .rate-table td {
          padding: 1rem;
          border-bottom: 1px solid rgba(255, 255, 255, 0.05);
          font-size: 0.9rem;
        }
        
        .code-cell {
          font-family: 'Courier New', monospace;
          font-weight: 600;
          color: #a855f7;
        }
        
        .category-badge {
          background: rgba(59, 130, 246, 0.15);
          color: #3b82f6;
          padding: 0.25rem 0.625rem;
          border-radius: 12px;
          font-size: 0.75rem;
          font-weight: 600;
        }
        
        .rate-cell {
          font-family: 'Courier New', monospace;
          font-weight: 600;
        }
        
        .rate-cell.highlight {
          color: #22c55e;
        }
        
        /* Reports View */
        .reports-container {
          display: flex;
          flex-direction: column;
          gap: 2rem;
        }
        
        .reports-header {
          text-align: center;
          padding: 1rem 0;
          border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        }
        
        .reports-header h2 {
          font-size: 1.8rem;
          color: #ffffff;
          margin-bottom: 0.5rem;
        }
        
        .reports-header p {
          color: #888;
        }
        
        .report-cards {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 1.5rem;
        }
        
        .report-card {
          background: linear-gradient(135deg, rgba(30, 30, 30, 0.9) 0%, rgba(20, 20, 20, 0.9) 100%);
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 16px;
          padding: 2rem;
          text-align: center;
          transition: all 0.3s;
        }
        
        .report-card:hover {
          transform: translateY(-4px);
          border-color: rgba(239, 68, 68, 0.3);
          box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
        }
        
        .report-icon {
          width: 80px;
          height: 80px;
          margin: 0 auto 1.5rem;
          border-radius: 16px;
          background: linear-gradient(135deg, rgba(239, 68, 68, 0.2), rgba(220, 38, 38, 0.1));
          display: flex;
          align-items: center;
          justify-content: center;
          color: #ef4444;
        }
        
        .report-card h3 {
          font-size: 1.2rem;
          color: #ffffff;
          margin-bottom: 0.75rem;
        }
        
        .report-card p {
          color: #999;
          font-size: 0.9rem;
          line-height: 1.6;
          margin-bottom: 1.5rem;
        }
        
        .report-stats {
          display: flex;
          justify-content: center;
          gap: 1.5rem;
          margin-bottom: 1.5rem;
          padding: 1rem;
          background: rgba(0, 0, 0, 0.3);
          border-radius: 8px;
        }
        
        .report-stats span {
          font-size: 0.8rem;
          color: #888;
        }
        
        .report-btn {
          width: 100%;
          padding: 0.875rem 1.5rem;
          border-radius: 8px;
          border: none;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 0.5rem;
          font-size: 0.95rem;
          font-weight: 600;
          transition: all 0.2s;
        }
        
        .report-btn.primary {
          background: linear-gradient(135deg, #ef4444, #dc2626);
          color: #ffffff;
        }
        
        .report-btn.primary:hover {
          background: linear-gradient(135deg, #dc2626, #b91c1c);
          transform: translateY(-2px);
          box-shadow: 0 10px 20px rgba(239, 68, 68, 0.3);
        }
        
        .audit-trail {
          background: linear-gradient(135deg, rgba(30, 30, 30, 0.9) 0%, rgba(20, 20, 20, 0.9) 100%);
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 16px;
          padding: 2rem;
        }
        
        .audit-trail h3 {
          font-size: 1.2rem;
          color: #ffffff;
          margin-bottom: 1.5rem;
        }
        
        .audit-log {
          display: flex;
          flex-direction: column;
          gap: 1rem;
        }
        
        .audit-item {
          display: flex;
          gap: 1rem;
          padding: 1rem;
          background: rgba(0, 0, 0, 0.3);
          border-radius: 8px;
          border-left: 3px solid #3b82f6;
        }
        
        .audit-item svg {
          color: #3b82f6;
          flex-shrink: 0;
        }
        
        .audit-content {
          flex: 1;
        }
        
        .audit-title {
          font-weight: 600;
          color: #e5e5e5;
          margin-bottom: 0.25rem;
        }
        
        .audit-meta {
          font-size: 0.85rem;
          color: #666;
        }
        
        /* Footer */
        .app-footer {
          background: rgba(20, 20, 20, 0.95);
          border-top: 1px solid rgba(255, 255, 255, 0.08);
          padding: 1rem 2rem;
          margin-top: auto;
        }
        
        .footer-content {
          display: flex;
          justify-content: space-between;
          align-items: center;
          max-width: 1600px;
          margin: 0 auto;
        }
        
        .footer-left, .footer-right {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          font-size: 0.85rem;
          color: #666;
        }
        
        .separator {
          color: #333;
        }
        
        .status-indicator {
          display: flex;
          align-items: center;
          gap: 0.5rem;
        }
        
        .status-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: #22c55e;
          animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
        
        .loading-container {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          min-height: 400px;
          gap: 1rem;
        }
        
        .loading-spinner {
          width: 50px;
          height: 50px;
          border: 4px solid rgba(239, 68, 68, 0.1);
          border-top-color: #ef4444;
          border-radius: 50%;
          animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        
        .loading-container p {
          color: #888;
          font-size: 0.95rem;
        }
        
        @media (max-width: 1400px) {
          .metrics-row {
            grid-template-columns: repeat(2, 1fr);
          }
        }
        
        @media (max-width: 768px) {
          .metrics-row {
            grid-template-columns: 1fr;
          }
          
          .charts-row {
            grid-template-columns: 1fr;
          }
          
          .report-cards {
            grid-template-columns: 1fr;
          }
          
          .regulatory-cards {
            grid-template-columns: 1fr;
          }
        }
      `}</style>
    </div>
  );
};

export default RegulaHealthApp;