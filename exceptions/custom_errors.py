class QuantumFlowException(Exception):
    """Base class for all custom QuantumFlow errors."""

    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class ModelNotTrainedError(QuantumFlowException):
    def __init__(self, symbol: str):
        super().__init__(
            message=f"Machine learning models for {symbol.upper()} are not trained."
            " Please run the training pipeline first.",
            status_code=404,
        )


class RiskGateBlockedError(QuantumFlowException):
    def __init__(self, reason: str):
        super().__init__(
            message=f"Trade blocked by Risk Gate: {reason}", status_code=422
        )
