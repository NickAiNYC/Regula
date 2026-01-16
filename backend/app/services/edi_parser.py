"""
Regula Health - EDI 835 Parser Service
High-performance parsing of Electronic Remittance Advice files
Target: 10,000+ claims/second
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Optional
import structlog

logger = structlog.get_logger()


class EDI835Parser:
    """
    Parse EDI 835 Electronic Remittance Advice

    Extracts claim payment information and service line details
    for compliance checking against NY Medicaid rates.

    Performance target: <1ms per claim
    """

    def __init__(self):
        self.segment_separator = "~"
        self.element_separator = "*"

    async def parse_file(self, file_content: str) -> List[Dict]:
        """
        Parse complete EDI 835 file

        Args:
            file_content: Raw EDI 835 file content

        Returns:
            List of parsed claim dictionaries
        """
        start_time = datetime.now()

        # Split into segments
        segments = self._split_segments(file_content)

        # Parse claims from segments
        claims = self._extract_claims(segments)

        processing_time = (datetime.now() - start_time).total_seconds()
        logger.info(
            "edi_835_parsed",
            claims_count=len(claims),
            processing_time_seconds=processing_time,
        )

        return claims

    def _split_segments(self, content: str) -> List[str]:
        """Split EDI content into segments"""
        # Handle both ~ and newline as separators
        content = content.replace("\n", "~")
        segments = [s.strip() for s in content.split("~") if s.strip()]
        return segments

    def _extract_claims(self, segments: List[str]) -> List[Dict]:
        """
        Extract claims from EDI segments

        EDI 835 Structure:
        - N1: Payer identification
        - CLP: Claim payment information (one per claim)
        - SVC: Service line details (one or more per claim)
        """
        claims = []
        current_payer = None
        current_claim = None

        for segment in segments:
            elements = segment.split(self.element_separator)
            segment_id = elements[0] if elements else ""

            if segment_id == "N1":
                # Payer identification
                current_payer = self._parse_n1_segment(elements)

            elif segment_id == "CLP":
                # New claim - save previous if exists
                if current_claim and current_claim.get("service_lines"):
                    # Flatten service lines into individual claims
                    for svc in current_claim["service_lines"]:
                        claims.append(
                            {
                                "claim_id": current_claim["claim_id"],
                                "payer": current_payer or "Unknown",
                                "payer_id": current_claim.get("payer_claim_id"),
                                "patient_status": current_claim.get("patient_status"),
                                **svc,
                            }
                        )

                # Parse new claim header
                current_claim = self._parse_clp_segment(elements)

            elif segment_id == "SVC" and current_claim:
                # Service line details
                svc = self._parse_svc_segment(elements)
                if svc:
                    if "service_lines" not in current_claim:
                        current_claim["service_lines"] = []
                    current_claim["service_lines"].append(svc)

            elif segment_id == "DTM" and current_claim:
                # Date/time reference (service date)
                date_info = self._parse_dtm_segment(elements)
                if date_info and "service_lines" in current_claim:
                    # Apply to last service line
                    if current_claim["service_lines"]:
                        current_claim["service_lines"][-1]["dos"] = date_info["date"]

        # Don't forget the last claim
        if current_claim and current_claim.get("service_lines"):
            for svc in current_claim["service_lines"]:
                claims.append(
                    {
                        "claim_id": current_claim["claim_id"],
                        "payer": current_payer or "Unknown",
                        "payer_id": current_claim.get("payer_claim_id"),
                        "patient_status": current_claim.get("patient_status"),
                        **svc,
                    }
                )

        return claims

    def _parse_n1_segment(self, elements: List[str]) -> Optional[str]:
        """
        Parse N1 (Payer Identification) segment

        Format: N1*PR*PAYER_NAME*
        """
        try:
            if len(elements) >= 3:
                return elements[2]  # Payer name
        except Exception as e:
            logger.warning("failed_to_parse_n1_segment", error=str(e))
        return None

    def _parse_clp_segment(self, elements: List[str]) -> Dict:
        """
        Parse CLP (Claim Payment Information) segment

        Format: CLP*CLAIM_ID*STATUS*BILLED*PAID*PATIENT_RESP*CLAIM_TYPE*PAYER_CLAIM_ID*

        Example: CLP*123456*1*500.00*450.00*0.00*MC*789*
        """
        try:
            return {
                "claim_id": elements[1] if len(elements) > 1 else None,
                "patient_status": elements[2] if len(elements) > 2 else None,
                "billed_amount": (
                    self._parse_decimal(elements[3]) if len(elements) > 3 else None
                ),
                "claim_paid_amount": (
                    self._parse_decimal(elements[4]) if len(elements) > 4 else None
                ),
                "payer_claim_id": elements[7] if len(elements) > 7 else None,
                "service_lines": [],
            }
        except Exception as e:
            logger.error("failed_to_parse_clp_segment", error=str(e), elements=elements)
            return {"service_lines": []}

    def _parse_svc_segment(self, elements: List[str]) -> Optional[Dict]:
        """
        Parse SVC (Service Line) segment

        Format: SVC*HC:CPT_CODE*BILLED*PAID*UNITS*

        Example: SVC*HC:90837*500.00*450.00*1*
        """
        try:
            # Extract CPT code from composite (HC:90837 or just 90837)
            cpt_raw = elements[1] if len(elements) > 1 else ""
            cpt_code = self._extract_cpt_code(cpt_raw)

            if not cpt_code:
                return None

            return {
                "cpt_code": cpt_code,
                "billed_amount": (
                    self._parse_decimal(elements[2]) if len(elements) > 2 else None
                ),
                "paid_amount": (
                    self._parse_decimal(elements[3])
                    if len(elements) > 3
                    else Decimal("0.00")
                ),
                "units": int(elements[4]) if len(elements) > 4 and elements[4] else 1,
                "dos": None,  # Will be filled by DTM segment
            }
        except Exception as e:
            logger.warning(
                "failed_to_parse_svc_segment", error=str(e), elements=elements
            )
            return None

    def _parse_dtm_segment(self, elements: List[str]) -> Optional[Dict]:
        """
        Parse DTM (Date/Time Reference) segment

        Format: DTM*472*YYYYMMDD*

        Example: DTM*472*20250115*
        """
        try:
            if len(elements) >= 3:
                date_str = elements[2]
                # Parse YYYYMMDD format
                dos = datetime.strptime(date_str, "%Y%m%d").date()
                return {"date": dos}
        except Exception as e:
            logger.warning(
                "failed_to_parse_dtm_segment", error=str(e), elements=elements
            )
        return None

    @staticmethod
    def _extract_cpt_code(cpt_raw: str) -> Optional[str]:
        """
        Extract CPT code from composite identifier

        Examples:
        - "HC:90837" -> "90837"
        - "90837" -> "90837"
        """
        if ":" in cpt_raw:
            parts = cpt_raw.split(":")
            return parts[1] if len(parts) > 1 else None
        return cpt_raw if cpt_raw else None

    @staticmethod
    def _parse_decimal(value: str) -> Optional[Decimal]:
        """Safely parse decimal value"""
        try:
            if value:
                return Decimal(value)
        except Exception:
            pass
        return None


# Singleton instance
edi_parser = EDI835Parser()
