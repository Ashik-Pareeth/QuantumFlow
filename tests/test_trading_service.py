from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pandas as pd
import pytest

from db.models import Candle, Position, Trade, TradeSide, Wallet
from exceptions.custom_errors import InsufficientPositionError, RiskGateBlockedError
from services.trading_service import execute_trade_order


class QueryStub:
    def __init__(self, first_item=None, all_items=None):
        self.first_item = first_item
        self.all_items = all_items or []

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def distinct(self, *args, **kwargs):
        return self

    def with_for_update(self, *args, **kwargs):
        return self

    def first(self):
        return self.first_item

    def all(self):
        return self.all_items


class TradingDbStub:
    def __init__(self, latest_candle, wallet, position=None, positions=None):
        self.latest_candle = latest_candle
        self.wallet = wallet
        self.position = position
        self.positions = positions or ([] if position is None else [position])
        self.added = []
        self.deleted = []
        self.committed = False
        self.rolled_back = False

    def query(self, model):
        if model is Candle:
            return QueryStub(
                first_item=self.latest_candle,
                all_items=[self.latest_candle],
            )
        if model is Wallet:
            return QueryStub(first_item=self.wallet)
        if model is Position:
            return QueryStub(first_item=self.position, all_items=self.positions)
        raise AssertionError(f"Unexpected model query: {model}")

    def add(self, item):
        self.added.append(item)

    def delete(self, item):
        self.deleted.append(item)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def make_candle(symbol="AAPL", close="100.0000"):
    return SimpleNamespace(symbol=symbol, close=Decimal(close), time="latest")


def make_wallet(balance="10000.00"):
    return SimpleNamespace(user_id=uuid4(), cash_balance=Decimal(balance))


def make_position(user_id, symbol="AAPL", qty="5.0000", avg_price="80.0000"):
    return SimpleNamespace(
        user_id=user_id,
        symbol=symbol,
        qty=Decimal(qty),
        avg_price=Decimal(avg_price),
    )


@patch(
    "services.trading_service.detect_current_regime",
    return_value=(1, "Low Vol", False),
)
@patch(
    "services.trading_service.generate_features",
    return_value=pd.DataFrame({"close": [100.0], "atr": [2.0]}),
)
def test_buy_order_creates_position_and_trade(mock_generate, mock_regime):
    wallet = make_wallet("10000.00")
    db = TradingDbStub(latest_candle=make_candle(), wallet=wallet)

    result = execute_trade_order(
        user_id=wallet.user_id,
        symbol="AAPL",
        qty=Decimal("1.0000"),
        side=TradeSide.BUY,
        force_execution=False,
        db=db,
    )

    assert result["message"] == "BUY order executed successfully."
    assert wallet.cash_balance == Decimal("9900.00000000")
    assert any(isinstance(item, Position) for item in db.added)
    assert any(isinstance(item, Trade) for item in db.added)
    assert db.committed is True


@patch(
    "services.trading_service.detect_current_regime",
    return_value=(3, "Danger", True),
)
@patch(
    "services.trading_service.generate_features",
    return_value=pd.DataFrame({"close": [100.0], "atr": [2.0]}),
)
def test_buy_order_is_blocked_by_risk_gate(mock_generate, mock_regime):
    wallet = make_wallet("10000.00")
    db = TradingDbStub(latest_candle=make_candle(), wallet=wallet)

    with pytest.raises(RiskGateBlockedError):
        execute_trade_order(
            user_id=wallet.user_id,
            symbol="AAPL",
            qty=Decimal("1.0000"),
            side=TradeSide.BUY,
            force_execution=False,
            db=db,
        )


@patch("services.trading_service.detect_current_regime")
@patch("services.trading_service.generate_features")
def test_sell_order_executes_without_buy_risk_gate(mock_generate, mock_regime):
    wallet = make_wallet("100.00")
    position = make_position(wallet.user_id, qty="5.0000", avg_price="80.0000")
    db = TradingDbStub(
        latest_candle=make_candle(close="100.0000"),
        wallet=wallet,
        position=position,
    )

    result = execute_trade_order(
        user_id=wallet.user_id,
        symbol="AAPL",
        qty=Decimal("2.0000"),
        side=TradeSide.SELL,
        force_execution=False,
        db=db,
    )

    assert result["message"] == "SELL order executed successfully."
    assert result["realized_pnl"] == "40.00"
    assert wallet.cash_balance == Decimal("300.00000000")
    assert position.qty == Decimal("3.0000")
    mock_generate.assert_not_called()
    mock_regime.assert_not_called()
    assert db.committed is True


def test_sell_order_rejects_insufficient_position():
    wallet = make_wallet("100.00")
    position = make_position(wallet.user_id, qty="1.0000")
    db = TradingDbStub(latest_candle=make_candle(), wallet=wallet, position=position)

    with pytest.raises(InsufficientPositionError):
        execute_trade_order(
            user_id=wallet.user_id,
            symbol="AAPL",
            qty=Decimal("2.0000"),
            side=TradeSide.SELL,
            force_execution=False,
            db=db,
        )
