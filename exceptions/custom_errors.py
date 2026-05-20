from fastapi import status


class QuantumFlowException(Exception):
    """Base class for all custom QuantumFlow errors."""

    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


# ML & MARKET DATA EXCEPTIONS


class ModelNotTrainedError(QuantumFlowException):
    def __init__(self, symbol: str):
        super().__init__(
            message=f"Machine learning models for {symbol.upper()} are not trained."
            " Please run the training pipeline first.",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class RiskGateBlockedError(QuantumFlowException):
    def __init__(self, reason: str, status_code: int = status.HTTP_409_CONFLICT):
        # Defaulting to 409 Conflict for trading execution overrides
        super().__init__(
            message=f"Trade blocked by Risk Gate: {reason}", status_code=status_code
        )


class MarketDataNotFoundError(QuantumFlowException):
    def __init__(self, symbol: str):
        super().__init__(
            message=f"No pricing or market data available for {symbol.upper()}.",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class InsufficientDataError(QuantumFlowException):
    def __init__(self, process: str = "evaluate risk gate"):
        super().__init__(
            message=f"Insufficient historical data to {process}.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


# TRADING & ECONOMY EXCEPTIONS


class InsufficientFundsError(QuantumFlowException):
    def __init__(self, required: float):
        super().__init__(
            message="Insufficient funds to complete this trade."
            f" Required: ${required:.2f}.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class PositionLimitExceededError(QuantumFlowException):
    def __init__(self, limit_percentage: int = 20):
        super().__init__(
            message="Position limit exceeded."
            f" You cannot invest more than {limit_percentage}%"
            " of your portfolio in a single asset.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class InsufficientPositionError(QuantumFlowException):
    def __init__(self, symbol: str):
        super().__init__(
            message=f"You do not own enough shares of {symbol.upper()}"
            " to complete this sell order.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class WalletNotFoundError(QuantumFlowException):
    def __init__(self):
        super().__init__(
            message="User wallet not found.", status_code=status.HTTP_404_NOT_FOUND
        )


# AUTHENTICATION & SECURITY EXCEPTIONS (Phase 5)


class InvalidCredentialsError(QuantumFlowException):
    def __init__(self):
        super().__init__(
            message="Incorrect email or password.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class AuthenticationFailedError(QuantumFlowException):
    def __init__(self, detail: str = "Could not validate credentials"):
        super().__init__(message=detail, status_code=status.HTTP_401_UNAUTHORIZED)
