"""
Regula Health - Document Generator
PDF generation for demand letters, appeals, and reports
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional
from pathlib import Path
import structlog
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
import tempfile

from app.models import Claim, Organization, Provider

logger = structlog.get_logger()


class DocumentGenerator:
    """
    Generate PDF documents for compliance and appeals
    
    Features:
    - DFS-compliant demand letters
    - Appeal documentation
    - Executive summary reports
    - Batch generation (100+ PDFs in <30 seconds)
    """
    
    def __init__(self, template_dir: str = "templates"):
        """
        Initialize document generator with Jinja2 templates
        
        Args:
            template_dir: Directory containing HTML templates
        """
        self.template_dir = Path(template_dir)
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=True
        )
        
        # Register custom filters
        self.jinja_env.filters['currency'] = self._format_currency
        self.jinja_env.filters['date'] = self._format_date
    
    @staticmethod
    def _format_currency(value: Decimal) -> str:
        """Format decimal as currency"""
        return f"${value:,.2f}"
    
    @staticmethod
    def _format_date(value: date) -> str:
        """Format date as MM/DD/YYYY"""
        return value.strftime("%m/%d/%Y")
    
    async def generate_demand_letter(
        self,
        violations: List[Claim],
        provider: Provider,
        organization: Organization,
        payer_name: str,
        payer_address: Optional[dict] = None
    ) -> bytes:
        """
        Generate DFS-compliant demand letter for underpayment violations
        
        Template includes:
        - Provider letterhead
        - Payer address
        - Table of violations (claim ID, DOS, CPT, paid, mandate, delta)
        - Legal citations (NY Insurance Law § 3221(l)(8), Part AA Ch.57 Laws 2024)
        - Deadline for payment (30 days)
        - Signature block
        
        Args:
            violations: List of underpaid claims
            provider: Provider information
            organization: Organization details
            payer_name: Insurance payer name
            payer_address: Optional payer mailing address
            
        Returns:
            PDF file as bytes
        """
        if not violations:
            raise ValueError("No violations provided for demand letter")
        
        # Calculate totals
        total_owed = sum(claim.delta for claim in violations)
        total_claims = len(violations)
        
        # Payment deadline (30 days from today)
        deadline = date.today() + timedelta(days=30)
        
        # Prepare violation data for template
        violation_data = [
            {
                'claim_id': claim.claim_id,
                'dos': claim.dos,
                'cpt_code': claim.cpt_code,
                'billed': claim.billed_amount or claim.mandate_rate,
                'paid': claim.paid_amount,
                'mandate': claim.mandate_rate,
                'delta': claim.delta,
            }
            for claim in violations
        ]
        
        # Default payer address if not provided
        if not payer_address:
            payer_address = {
                'name': payer_name,
                'street': 'Claims Department',
                'city': 'New York',
                'state': 'NY',
                'zip': '10001'
            }
        
        # Render HTML from template
        template = self.jinja_env.get_template('demand_letter/demand_letter.html')
        html_content = template.render(
            organization=organization,
            provider=provider,
            payer_name=payer_name,
            payer_address=payer_address,
            violations=violation_data,
            total_claims=total_claims,
            total_owed=total_owed,
            deadline=deadline,
            generation_date=date.today(),
            # Legal citations
            citation_insurance_law="NY Insurance Law § 3221(l)(8)",
            citation_parity_mandate="L.2024 c.57, Part AA",
            citation_mhpaea="Mental Health Parity and Addiction Equity Act (MHPAEA)"
        )
        
        # Convert HTML to PDF
        logger.info(
            "generating_demand_letter",
            provider_id=str(provider.id),
            payer=payer_name,
            violations_count=total_claims,
            total_owed=float(total_owed)
        )
        
        pdf_bytes = HTML(string=html_content).write_pdf()
        
        return pdf_bytes
    
    async def generate_appeal_package(
        self,
        claim: Claim,
        provider: Provider,
        organization: Organization
    ) -> bytes:
        """
        Generate appeal documentation package
        
        Includes:
        - Cover letter
        - Claim details
        - Rate calculation breakdown
        - Supporting documentation
        
        Args:
            claim: Claim to appeal
            provider: Provider information
            organization: Organization details
            
        Returns:
            PDF file as bytes
        """
        template = self.jinja_env.get_template('appeal/appeal_package.html')
        html_content = template.render(
            claim=claim,
            provider=provider,
            organization=organization,
            generation_date=date.today()
        )
        
        logger.info(
            "generating_appeal_package",
            claim_id=claim.claim_id,
            provider_id=str(provider.id)
        )
        
        return HTML(string=html_content).write_pdf()
    
    async def generate_executive_summary(
        self,
        claims: List[Claim],
        organization: Organization,
        start_date: date,
        end_date: date
    ) -> bytes:
        """
        Generate executive summary report
        
        Includes:
        - Total violations and recoverable amount
        - Top violating payers
        - Trend analysis
        - Service category breakdown
        
        Args:
            claims: List of claims to analyze
            organization: Organization details
            start_date: Report period start
            end_date: Report period end
            
        Returns:
            PDF file as bytes
        """
        # Calculate metrics
        violations = [c for c in claims if c.is_violation]
        total_recoverable = sum(c.delta for c in violations)
        violation_rate = (len(violations) / len(claims) * 100) if claims else 0
        
        # Group by payer
        payer_stats = {}
        for claim in violations:
            if claim.payer not in payer_stats:
                payer_stats[claim.payer] = {
                    'count': 0,
                    'total': Decimal('0.00')
                }
            payer_stats[claim.payer]['count'] += 1
            payer_stats[claim.payer]['total'] += claim.delta
        
        # Sort by total owed
        top_violators = sorted(
            payer_stats.items(),
            key=lambda x: x[1]['total'],
            reverse=True
        )[:10]
        
        template = self.jinja_env.get_template('reports/executive_summary.html')
        html_content = template.render(
            organization=organization,
            start_date=start_date,
            end_date=end_date,
            total_claims=len(claims),
            total_violations=len(violations),
            violation_rate=violation_rate,
            total_recoverable=total_recoverable,
            top_violators=top_violators,
            generation_date=date.today()
        )
        
        logger.info(
            "generating_executive_summary",
            organization_id=str(organization.id),
            claims_count=len(claims),
            violations_count=len(violations)
        )
        
        return HTML(string=html_content).write_pdf()
    
    async def batch_generate_demand_letters(
        self,
        violations_by_payer: dict,
        provider: Provider,
        organization: Organization
    ) -> dict:
        """
        Batch generate demand letters for multiple payers
        
        Target: 100+ PDFs in <30 seconds
        
        Args:
            violations_by_payer: Dict of {payer_name: [claims]}
            provider: Provider information
            organization: Organization details
            
        Returns:
            Dict of {payer_name: pdf_bytes}
        """
        results = {}
        
        for payer_name, violations in violations_by_payer.items():
            try:
                pdf_bytes = await self.generate_demand_letter(
                    violations=violations,
                    provider=provider,
                    organization=organization,
                    payer_name=payer_name
                )
                results[payer_name] = pdf_bytes
                
            except Exception as e:
                logger.error(
                    "batch_generation_error",
                    payer=payer_name,
                    error=str(e)
                )
                results[payer_name] = None
        
        logger.info(
            "batch_generation_complete",
            total_payers=len(violations_by_payer),
            successful=len([r for r in results.values() if r is not None])
        )
        
        return results
