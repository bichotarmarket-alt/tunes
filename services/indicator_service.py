"""Service for loading indicators from database"""
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from models import Indicator
from loguru import logger


class IndicatorService:
    """Service for managing indicators from database"""

    @staticmethod
    def get_indicator_by_name(db: Session, name: str) -> Optional[Indicator]:
        """
        Get an indicator by name from database

        Args:
            db: Database session
            name: Indicator name

        Returns:
            Indicator object or None if not found
        """
        return db.query(Indicator).filter(
            Indicator.name == name,
            Indicator.is_active == True
        ).first()

    @staticmethod
    def get_indicator_by_id(db: Session, indicator_id: str) -> Optional[Indicator]:
        """
        Get an indicator by ID from database

        Args:
            db: Database session
            indicator_id: Indicator ID

        Returns:
            Indicator object or None if not found
        """
        return db.query(Indicator).filter(
            Indicator.id == indicator_id,
            Indicator.is_active == True
        ).first()

    @staticmethod
    def get_all_active_indicators(db: Session) -> List[Indicator]:
        """
        Get all active indicators from database

        Args:
            db: Database session

        Returns:
            List of active indicators
        """
        return db.query(Indicator).filter(
            Indicator.is_active == True
        ).order_by(Indicator.name).all()

    @staticmethod
    def get_default_indicators(db: Session) -> List[Indicator]:
        """
        Get all default system indicators

        Args:
            db: Database session

        Returns:
            List of default indicators
        """
        return db.query(Indicator).filter(
            Indicator.is_default == True,
            Indicator.is_active == True
        ).order_by(Indicator.name).all()

    @staticmethod
    def get_indicator_parameters(db: Session, name: str) -> Optional[Dict[str, Any]]:
        """
        Get parameters for a specific indicator

        Args:
            db: Database session
            name: Indicator name

        Returns:
            Dictionary with indicator parameters or None if not found
        """
        indicator = IndicatorService.get_indicator_by_name(db, name)
        if indicator:
            return indicator.parameters
        return None

    @staticmethod
    def load_indicator_config(db: Session, indicator_name: str, default_params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Load indicator configuration from database with fallback to defaults

        Args:
            db: Database session
            indicator_name: Name of the indicator
            default_params: Default parameters to use if not found in database

        Returns:
            Dictionary with indicator parameters
        """
        # Try to load from database
        db_params = IndicatorService.get_indicator_parameters(db, indicator_name)

        if db_params is not None:
            logger.debug(f"Loaded indicator '{indicator_name}' configuration from database")
            return db_params

        # Use default parameters if not found in database
        if default_params:
            logger.warning(
                f"Indicator '{indicator_name}' not found in database, using default parameters"
            )
            return default_params

        logger.error(f"Indicator '{indicator_name}' not found and no defaults provided")
        return {}

    @staticmethod
    def get_indicator_type(db: Session, name: str) -> Optional[str]:
        """
        Get the type of an indicator

        Args:
            db: Database session
            name: Indicator name

        Returns:
            Indicator type or None if not found
        """
        indicator = IndicatorService.get_indicator_by_name(db, name)
        if indicator:
            return indicator.type
        return None

    @staticmethod
    def validate_indicator_parameters(indicator_type: str, parameters: Dict[str, Any]) -> bool:
        """
        Validate indicator parameters based on type

        Args:
            indicator_type: Type of indicator
            parameters: Parameters to validate

        Returns:
            True if valid, False otherwise
        """
        # Define validation rules for each indicator type
        validation_rules = {
            "rsi": {
                "required": ["period"],
                "optional": ["overbought", "oversold"],
                "defaults": {"period": 14, "overbought": 70, "oversold": 30}
            },
            "macd": {
                "required": ["fast_period", "slow_period", "signal_period"],
                "optional": [],
                "defaults": {"fast_period": 12, "slow_period": 26, "signal_period": 9}
            },
            "bollinger_bands": {
                "required": ["period"],
                "optional": ["std_dev"],
                "defaults": {"period": 20, "std_dev": 2.0}
            },
            "sma": {
                "required": ["period"],
                "optional": [],
                "defaults": {"period": 20}
            },
            "ema": {
                "required": ["period"],
                "optional": [],
                "defaults": {"period": 20}
            },
            "stochastic": {
                "required": ["k_period", "d_period"],
                "optional": ["smooth"],
                "defaults": {"k_period": 14, "d_period": 3, "smooth": 3}
            },
            "atr": {
                "required": ["period"],
                "optional": [],
                "defaults": {"period": 14}
            },
            "cci": {
                "required": ["period"],
                "optional": [],
                "defaults": {"period": 20}
            },
            "williams_r": {
                "required": ["period"],
                "optional": [],
                "defaults": {"period": 14}
            },
            "zonas": {
                "required": [],
                "optional": ["swing_period", "zone_strength", "zone_tolerance"],
                "defaults": {"swing_period": 5, "zone_strength": 2, "zone_tolerance": 0.005}
            },
        }

        # Get validation rules for this indicator type
        rules = validation_rules.get(indicator_type)
        if not rules:
            logger.warning(f"No validation rules for indicator type: {indicator_type}")
            return True  # Allow unknown types

        # Check required parameters
        for param in rules["required"]:
            if param not in parameters:
                logger.error(f"Missing required parameter '{param}' for {indicator_type}")
                return False

        # Check parameter types
        if indicator_type in ["rsi", "macd", "bollinger_bands", "sma", "ema", "stochastic", "atr", "cci", "williams_r", "zonas"]:
            for param, value in parameters.items():
                if param in ["period", "fast_period", "slow_period", "signal_period", "k_period", "d_period", "smooth", "swing_period", "zone_strength"]:
                    if not isinstance(value, int) or value <= 0:
                        logger.error(f"Invalid value for parameter '{param}': must be positive integer")
                        return False
                elif param in ["std_dev", "zone_tolerance"]:
                    if not isinstance(value, (int, float)) or value <= 0:
                        logger.error(f"Invalid value for parameter '{param}': must be positive number")
                        return False
                # Removida validação restritiva de overbought/oversold para permitir valores negativos
                # (necessário para CCI, ROC, Williams R, etc.)

        return True

    @staticmethod
    def get_indicator_config_for_strategy(db: Session, strategy_id: str) -> List[Dict[str, Any]]:
        """
        Get all indicators configured for a specific strategy

        Args:
            db: Database session
            strategy_id: Strategy ID

        Returns:
            List of indicator configurations
        """
        from models import Strategy

        strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
        if not strategy:
            return []

        indicators = []
        for indicator in strategy.indicators or []:
            if indicator.is_active:
                indicators.append({
                    "id": indicator.id,
                    "name": indicator.name,
                    "type": indicator.type,
                    "parameters": indicator.parameters
                })

        return indicators


# Singleton instance for easy access
indicator_service = IndicatorService()
