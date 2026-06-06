from pydantic import BaseModel, Field

class MarketPredictionResponse(BaseModel):
    symbol: str = Field(..., description="The stock symbol")
    regime: str = Field(..., description="The readable state from the HMM model")
    is_dangerous: bool = Field(..., description="Whether the current volatility is extremely high")
    signal: str = Field(..., description="'BUY', 'SELL', or 'NEUTRAL'")
    status: str = Field(..., description="Status of the analysis, e.g., 'ANALYSIS_COMPLETE' or 'INSUFFICIENT_DATA'")
