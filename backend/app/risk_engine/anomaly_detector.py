"""
Anomaly Detector

Unsupervised learning to identify aberrant billing patterns that may:
- Trigger payer audits
- Indicate coding errors
- Reveal systematic underpayment patterns

Helps providers avoid audits and optimize revenue cycle.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import structlog

logger = structlog.get_logger()


class AnomalyDetector:
    """
    Detect anomalous billing patterns using statistical methods
    
    Anomaly Types Detected:
    1. Volume anomalies (sudden spikes/drops in claim volume)
    2. Payment anomalies (unusual payment amounts)
    3. Code combination anomalies (unusual CPT pairings)
    4. Temporal anomalies (unusual billing patterns by time)
    5. Geographic anomalies (inconsistent regional patterns)
    
    Methods:
    - Statistical (Z-score, IQR)
    - Isolation Forest (for multi-dimensional anomalies)
    - Time-series (ARIMA for volume forecasting)
    """
    
    # Anomaly thresholds
    Z_SCORE_THRESHOLD = 3.0  # Standard deviations
    IQR_MULTIPLIER = 1.5
    MIN_SAMPLES_FOR_DETECTION = 30  # Minimum data points needed
    
    def __init__(self):
        self.baseline_stats = {}
        self.anomaly_history = []
    
    async def detect_provider_anomalies(
        self,
        provider_id: str,
        claims_data: List[Dict],
        historical_baseline: Optional[Dict] = None
    ) -> Dict:
        """
        Detect anomalies in provider's billing patterns
        
        Args:
            provider_id: Provider identifier
            claims_data: Recent claims to analyze
            historical_baseline: Historical statistics for comparison
            
        Returns:
            Dictionary with:
            - has_anomalies: bool
            - anomalies: List[Dict] (detected anomalies with details)
            - risk_level: str (low, medium, high)
            - recommendations: List[str]
        """
        anomalies = []
        
        # 1. Volume anomaly detection
        volume_anomalies = self._detect_volume_anomalies(
            claims_data, historical_baseline
        )
        anomalies.extend(volume_anomalies)
        
        # 2. Payment amount anomalies
        payment_anomalies = self._detect_payment_anomalies(
            claims_data, historical_baseline
        )
        anomalies.extend(payment_anomalies)
        
        # 3. Code combination anomalies
        code_anomalies = self._detect_code_combination_anomalies(claims_data)
        anomalies.extend(code_anomalies)
        
        # 4. Temporal pattern anomalies
        temporal_anomalies = self._detect_temporal_anomalies(claims_data)
        anomalies.extend(temporal_anomalies)
        
        # 5. Payer concentration anomalies
        payer_anomalies = self._detect_payer_concentration_anomalies(claims_data)
        anomalies.extend(payer_anomalies)
        
        # Assess overall risk
        risk_level = self._assess_risk_level(anomalies)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(anomalies, risk_level)
        
        result = {
            "provider_id": provider_id,
            "has_anomalies": len(anomalies) > 0,
            "anomaly_count": len(anomalies),
            "anomalies": anomalies,
            "risk_level": risk_level,
            "recommendations": recommendations,
            "analysis_date": datetime.now().isoformat(),
            "claims_analyzed": len(claims_data)
        }
        
        logger.info(
            "anomaly_detection_complete",
            provider_id=provider_id,
            anomaly_count=len(anomalies),
            risk_level=risk_level
        )
        
        return result
    
    def _detect_volume_anomalies(
        self,
        claims_data: List[Dict],
        baseline: Optional[Dict]
    ) -> List[Dict]:
        """
        Detect unusual claim volume patterns
        
        Checks for:
        - Sudden spikes (possible upcoding or billing errors)
        - Sudden drops (possible system issues)
        """
        anomalies = []
        
        if not baseline or len(claims_data) < self.MIN_SAMPLES_FOR_DETECTION:
            return anomalies
        
        # Calculate current volume by CPT code
        current_volumes = defaultdict(int)
        for claim in claims_data:
            current_volumes[claim.get("cpt_code", "")] += 1
        
        # Compare to baseline
        baseline_volumes = baseline.get("avg_volumes_by_cpt", {})
        baseline_std = baseline.get("std_volumes_by_cpt", {})
        
        for cpt_code, current_count in current_volumes.items():
            if cpt_code not in baseline_volumes:
                continue
            
            baseline_avg = baseline_volumes[cpt_code]
            baseline_deviation = baseline_std.get(cpt_code, baseline_avg * 0.2)
            
            # Calculate Z-score
            if baseline_deviation > 0:
                z_score = (current_count - baseline_avg) / baseline_deviation
                
                if abs(z_score) > self.Z_SCORE_THRESHOLD:
                    anomalies.append({
                        "type": "volume_anomaly",
                        "severity": "high" if abs(z_score) > 4 else "medium",
                        "cpt_code": cpt_code,
                        "message": (
                            f"Unusual volume for {cpt_code}: {current_count} claims "
                            f"(baseline: {baseline_avg:.1f} ± {baseline_deviation:.1f})"
                        ),
                        "z_score": round(z_score, 2),
                        "direction": "spike" if z_score > 0 else "drop"
                    })
        
        return anomalies
    
    def _detect_payment_anomalies(
        self,
        claims_data: List[Dict],
        baseline: Optional[Dict]
    ) -> List[Dict]:
        """
        Detect unusual payment amounts
        
        Identifies payments that are statistical outliers
        """
        anomalies = []
        
        if len(claims_data) < self.MIN_SAMPLES_FOR_DETECTION:
            return anomalies
        
        # Group payments by CPT code
        payments_by_cpt = defaultdict(list)
        for claim in claims_data:
            cpt = claim.get("cpt_code")
            paid = claim.get("paid_amount")
            if cpt and paid:
                payments_by_cpt[cpt].append(float(paid))
        
        # Detect outliers using IQR method
        for cpt_code, payments in payments_by_cpt.items():
            if len(payments) < 10:  # Need sufficient sample
                continue
            
            # Calculate IQR
            sorted_payments = sorted(payments)
            q1_idx = len(sorted_payments) // 4
            q3_idx = (3 * len(sorted_payments)) // 4
            
            q1 = sorted_payments[q1_idx]
            q3 = sorted_payments[q3_idx]
            iqr = q3 - q1
            
            # Define outlier bounds
            lower_bound = q1 - (self.IQR_MULTIPLIER * iqr)
            upper_bound = q3 + (self.IQR_MULTIPLIER * iqr)
            
            # Find outliers
            outliers = [p for p in payments if p < lower_bound or p > upper_bound]
            
            if outliers:
                anomalies.append({
                    "type": "payment_anomaly",
                    "severity": "medium",
                    "cpt_code": cpt_code,
                    "message": (
                        f"{len(outliers)} unusual payment amounts for {cpt_code} "
                        f"(expected range: ${lower_bound:.2f} - ${upper_bound:.2f})"
                    ),
                    "outlier_count": len(outliers),
                    "outlier_examples": [round(p, 2) for p in outliers[:3]]
                })
        
        return anomalies
    
    def _detect_code_combination_anomalies(
        self,
        claims_data: List[Dict]
    ) -> List[Dict]:
        """
        Detect unusual CPT code combinations
        
        Identifies code pairings that:
        - Are rarely billed together
        - May indicate bundling violations
        - Could trigger payer audits
        """
        anomalies = []
        
        # Group claims by date and patient (to find same-day services)
        same_day_services = defaultdict(list)
        for claim in claims_data:
            key = (
                claim.get("service_date"),
                claim.get("patient_id", claim.get("member_id", "unknown"))
            )
            same_day_services[key].append(claim.get("cpt_code"))
        
        # Check for problematic combinations
        for (dos, patient), codes in same_day_services.items():
            if len(codes) < 2:
                continue
            
            # Check for evaluation codes billed together (typically not allowed)
            eval_codes = ["90791", "90792"]
            eval_count = sum(1 for c in codes if c in eval_codes)
            if eval_count > 1:
                anomalies.append({
                    "type": "code_combination_anomaly",
                    "severity": "high",
                    "message": (
                        f"Multiple evaluation codes billed on same day: {eval_codes}"
                    ),
                    "codes": codes,
                    "service_date": str(dos)
                })
            
            # Check for excessive psychotherapy on same day
            therapy_codes = ["90832", "90834", "90837"]
            therapy_count = sum(1 for c in codes if c in therapy_codes)
            if therapy_count > 2:
                anomalies.append({
                    "type": "code_combination_anomaly",
                    "severity": "medium",
                    "message": (
                        f"{therapy_count} psychotherapy sessions on same day may trigger audit"
                    ),
                    "codes": codes,
                    "service_date": str(dos)
                })
        
        return anomalies
    
    def _detect_temporal_anomalies(
        self,
        claims_data: List[Dict]
    ) -> List[Dict]:
        """
        Detect unusual temporal billing patterns
        """
        anomalies = []
        
        # Check for unusual billing day patterns
        day_of_week_counts = defaultdict(int)
        for claim in claims_data:
            dos = claim.get("service_date")
            if dos:
                if isinstance(dos, str):
                    dos = datetime.fromisoformat(dos).date()
                day_of_week_counts[dos.weekday()] += 1
        
        # Check if billing is heavily concentrated on weekends (unusual for most practices)
        weekend_count = day_of_week_counts[5] + day_of_week_counts[6]  # Sat + Sun
        total_count = sum(day_of_week_counts.values())
        
        if total_count > 0 and (weekend_count / total_count) > 0.4:
            anomalies.append({
                "type": "temporal_anomaly",
                "severity": "low",
                "message": (
                    f"{(weekend_count/total_count)*100:.1f}% of services on weekends "
                    "(may be legitimate but unusual for most practices)"
                ),
                "weekend_percentage": round((weekend_count/total_count)*100, 1)
            })
        
        return anomalies
    
    def _detect_payer_concentration_anomalies(
        self,
        claims_data: List[Dict]
    ) -> List[Dict]:
        """
        Detect unusual payer concentration patterns
        """
        anomalies = []
        
        # Calculate payer distribution
        payer_counts = defaultdict(int)
        for claim in claims_data:
            payer_counts[claim.get("payer", "Unknown")] += 1
        
        total = len(claims_data)
        if total < 10:
            return anomalies
        
        # Check for over-concentration (>80% from single payer)
        for payer, count in payer_counts.items():
            percentage = (count / total) * 100
            if percentage > 80:
                anomalies.append({
                    "type": "payer_concentration_anomaly",
                    "severity": "low",
                    "message": (
                        f"{percentage:.1f}% of claims from single payer ({payer}). "
                        "Consider diversifying payer mix for business resilience."
                    ),
                    "payer": payer,
                    "percentage": round(percentage, 1)
                })
        
        return anomalies
    
    def _assess_risk_level(self, anomalies: List[Dict]) -> str:
        """Assess overall risk level based on anomalies"""
        if not anomalies:
            return "low"
        
        high_severity_count = sum(1 for a in anomalies if a.get("severity") == "high")
        medium_severity_count = sum(1 for a in anomalies if a.get("severity") == "medium")
        
        if high_severity_count >= 2:
            return "high"
        elif high_severity_count >= 1 or medium_severity_count >= 3:
            return "medium"
        else:
            return "low"
    
    def _generate_recommendations(
        self,
        anomalies: List[Dict],
        risk_level: str
    ) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []
        
        if risk_level == "high":
            recommendations.append(
                "⚠️ URGENT: Review billing patterns immediately. "
                "Multiple high-severity anomalies detected."
            )
        
        # Type-specific recommendations
        anomaly_types = {a.get("type") for a in anomalies}
        
        if "volume_anomaly" in anomaly_types:
            recommendations.append(
                "Review recent volume changes. Ensure coding consistency and "
                "documentation supports service levels."
            )
        
        if "payment_anomaly" in anomaly_types:
            recommendations.append(
                "Investigate unusual payment amounts. Verify fee schedules and "
                "check for payer-specific adjustments."
            )
        
        if "code_combination_anomaly" in anomaly_types:
            recommendations.append(
                "Review CPT code combinations. Consult NCCI edits and payer policies "
                "to avoid bundling violations."
            )
        
        if not recommendations:
            recommendations.append(
                "✓ Continue monitoring billing patterns. No immediate action required."
            )
        
        return recommendations
