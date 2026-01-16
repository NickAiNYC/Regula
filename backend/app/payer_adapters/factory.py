"""
Payer Adapter Factory

Registry and factory for creating payer adapter instances.
Enables dynamic adapter selection based on payer name/identifier.
"""

from typing import Dict, Optional, Type
import structlog

from .base import BasePayerAdapter, PayerAdapterError
from .cms_medicare import CMSMedicareAdapter
from .ny_medicaid import NYMedicaidAdapter
from .aetna_commercial import AetnaCommercialAdapter

logger = structlog.get_logger()


class PayerAdapterFactory:
    """
    Factory for creating payer adapter instances
    
    Maintains a registry of available adapters and provides
    lookup by payer name or identifier.
    """
    
    _registry: Dict[str, Type[BasePayerAdapter]] = {}
    _aliases: Dict[str, str] = {}
    
    @classmethod
    def register(
        cls,
        payer_key: str,
        adapter_class: Type[BasePayerAdapter],
        aliases: Optional[list[str]] = None
    ):
        """
        Register a payer adapter
        
        Args:
            payer_key: Primary identifier for the payer
            adapter_class: Adapter class to instantiate
            aliases: Alternative names/identifiers for the payer
        """
        cls._registry[payer_key.lower()] = adapter_class
        
        if aliases:
            for alias in aliases:
                cls._aliases[alias.lower()] = payer_key.lower()
        
        logger.info(
            "payer_adapter_registered",
            payer_key=payer_key,
            adapter=adapter_class.__name__,
            aliases=aliases or []
        )
    
    @classmethod
    def get_adapter(cls, payer_identifier: str) -> BasePayerAdapter:
        """
        Get payer adapter instance
        
        Args:
            payer_identifier: Payer name or identifier
            
        Returns:
            Adapter instance
            
        Raises:
            PayerAdapterError: If payer not found in registry
        """
        # Normalize identifier
        payer_key = payer_identifier.lower().strip()
        
        # Check aliases first
        if payer_key in cls._aliases:
            payer_key = cls._aliases[payer_key]
        
        # Get adapter class from registry
        adapter_class = cls._registry.get(payer_key)
        
        if not adapter_class:
            logger.warning("payer_adapter_not_found", payer=payer_identifier)
            raise PayerAdapterError(
                f"No adapter found for payer: {payer_identifier}. "
                f"Available payers: {', '.join(cls._registry.keys())}"
            )
        
        # Instantiate and return
        return adapter_class()
    
    @classmethod
    def list_supported_payers(cls) -> list[str]:
        """Get list of all supported payer identifiers"""
        return list(cls._registry.keys())
    
    @classmethod
    def is_supported(cls, payer_identifier: str) -> bool:
        """Check if payer is supported"""
        payer_key = payer_identifier.lower().strip()
        return payer_key in cls._registry or payer_key in cls._aliases


# Register built-in adapters
PayerAdapterFactory.register(
    "cms_medicare",
    CMSMedicareAdapter,
    aliases=["medicare", "cms", "medicare part b"]
)

PayerAdapterFactory.register(
    "ny_medicaid",
    NYMedicaidAdapter,
    aliases=["medicaid", "ny medicaid", "new york medicaid"]
)

PayerAdapterFactory.register(
    "aetna",
    AetnaCommercialAdapter,
    aliases=["aetna commercial", "aetna ppo", "aetna hmo"]
)


# Convenience function
def get_payer_adapter(payer_identifier: str) -> BasePayerAdapter:
    """
    Convenience function to get payer adapter
    
    Args:
        payer_identifier: Payer name or identifier
        
    Returns:
        Adapter instance
        
    Example:
        >>> adapter = get_payer_adapter("Aetna")
        >>> rate = await adapter.get_allowed_amount("90837", date(2025, 1, 15))
    """
    return PayerAdapterFactory.get_adapter(payer_identifier)
