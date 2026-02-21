"""
Credit service - manages user credits and usage tracking.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func as sql_func
from typing import Optional, Tuple
from datetime import datetime, timezone
from decimal import Decimal
import logging

from .models import UserCredit, LLMPricing, UsageRecord, RequestType

logger = logging.getLogger(__name__)


class CreditService:
    """Service class for credit and usage operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def initialize_credits(self, user_id: str, amount_cents: int = 1000) -> UserCredit:
        """Initialize credit balance for a new user."""
        credit = UserCredit(
            user_id=user_id,
            balance_cents=amount_cents,
            total_deposited_cents=amount_cents,
        )
        self.db.add(credit)
        await self.db.flush()
        return credit

    async def get_balance(self, user_id: str) -> Optional[UserCredit]:
        """Get user's credit balance."""
        result = await self.db.execute(
            select(UserCredit).where(UserCredit.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def check_sufficient_credits(self, user_id: str, estimated_cost_cents: int) -> bool:
        """Check if user has enough credits for a request."""
        credit = await self.get_balance(user_id)
        if not credit:
            return False
        return credit.balance_cents >= estimated_cost_cents

    async def estimate_cost(self, provider: str, model: str, estimated_tokens: int) -> int:
        """Estimate cost in cents for a request."""
        pricing = await self._get_pricing(provider, model)
        if not pricing:
            return 0  # Unknown model, allow through

        # Rough estimate: assume 50/50 input/output split
        input_tokens = estimated_tokens // 2
        output_tokens = estimated_tokens // 2

        raw_cost = (
            (input_tokens / 1_000_000) * pricing.input_cost_per_1m_cents +
            (output_tokens / 1_000_000) * pricing.output_cost_per_1m_cents
        )

        return int(raw_cost * float(pricing.margin_multiplier)) + 1  # Round up

    async def calculate_cost(
        self, provider: str, model: str, input_tokens: int, output_tokens: int
    ) -> Tuple[int, int]:
        """
        Calculate actual cost.

        Returns:
            (cost_with_margin, raw_cost) in cents
        """
        pricing = await self._get_pricing(provider, model)
        if not pricing:
            return 0, 0

        raw_cost = (
            (input_tokens / 1_000_000) * pricing.input_cost_per_1m_cents +
            (output_tokens / 1_000_000) * pricing.output_cost_per_1m_cents
        )

        cost_with_margin = raw_cost * float(pricing.margin_multiplier)

        # Convert to integer cents (round up to avoid undercharging)
        raw_cost_cents = max(int(raw_cost) + (1 if raw_cost % 1 > 0 else 0), 0)
        cost_cents = max(int(cost_with_margin) + (1 if cost_with_margin % 1 > 0 else 0), 0)

        return cost_cents, raw_cost_cents

    async def record_usage_and_deduct(
        self,
        user_id: str,
        project_id: Optional[str],
        provider: str,
        model: str,
        request_type: str,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int = 0,
        is_own_key: bool = False,
    ) -> UsageRecord:
        """Record usage and deduct credits (if not own key)."""
        if is_own_key:
            cost_cents = 0
            raw_cost_cents = 0
        else:
            cost_cents, raw_cost_cents = await self.calculate_cost(
                provider, model, input_tokens, output_tokens
            )

        # Create usage record
        try:
            req_type = RequestType(request_type)
        except ValueError:
            req_type = RequestType.CHAT

        record = UsageRecord(
            user_id=user_id,
            project_id=project_id,
            provider=provider,
            model=model,
            request_type=req_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            cost_cents=cost_cents,
            raw_cost_cents=raw_cost_cents,
            is_own_key=is_own_key,
        )
        self.db.add(record)

        # Deduct from balance (only if not own key)
        if not is_own_key and cost_cents > 0:
            credit = await self.get_balance(user_id)
            if credit:
                credit.balance_cents = max(0, credit.balance_cents - cost_cents)
                credit.total_consumed_cents += cost_cents
                credit.last_charged_at = datetime.now(timezone.utc)

        await self.db.flush()
        return record

    async def admin_adjust_credits(
        self, user_id: str, amount_cents: int, reason: str
    ) -> Optional[UserCredit]:
        """Admin: adjust a user's credit balance."""
        credit = await self.get_balance(user_id)
        if not credit:
            # Create credit record if doesn't exist
            credit = await self.initialize_credits(user_id, amount_cents=max(0, amount_cents))
            return credit

        credit.balance_cents = max(0, credit.balance_cents + amount_cents)
        if amount_cents > 0:
            credit.total_deposited_cents += amount_cents

        logger.info(f"Admin credit adjustment: user={user_id} amount={amount_cents} reason={reason}")
        await self.db.flush()
        return credit

    async def get_usage_history(
        self, user_id: str, page: int = 1, page_size: int = 50
    ) -> Tuple[list, int]:
        """Get paginated usage history for a user."""
        # Count total
        count_result = await self.db.execute(
            select(sql_func.count()).select_from(UsageRecord).where(
                UsageRecord.user_id == user_id
            )
        )
        total = count_result.scalar()

        # Get page
        offset = (page - 1) * page_size
        result = await self.db.execute(
            select(UsageRecord)
            .where(UsageRecord.user_id == user_id)
            .order_by(UsageRecord.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        records = list(result.scalars().all())

        return records, total

    async def get_all_pricing(self) -> list:
        """Get all active pricing entries."""
        result = await self.db.execute(
            select(LLMPricing)
            .where(LLMPricing.is_active == True)
            .order_by(LLMPricing.provider, LLMPricing.model)
        )
        return list(result.scalars().all())

    async def update_pricing(
        self,
        provider: str,
        model: str,
        input_cost: Optional[int] = None,
        output_cost: Optional[int] = None,
        margin: Optional[float] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[LLMPricing]:
        """Update pricing for a provider/model."""
        pricing = await self._get_pricing(provider, model)
        if not pricing:
            return None

        if input_cost is not None:
            pricing.input_cost_per_1m_cents = input_cost
        if output_cost is not None:
            pricing.output_cost_per_1m_cents = output_cost
        if margin is not None:
            pricing.margin_multiplier = Decimal(str(margin))
        if is_active is not None:
            pricing.is_active = is_active

        await self.db.flush()
        return pricing

    async def _get_pricing(self, provider: str, model: str) -> Optional[LLMPricing]:
        """Get pricing for a specific provider/model."""
        result = await self.db.execute(
            select(LLMPricing).where(
                LLMPricing.provider == provider,
                LLMPricing.model == model,
                LLMPricing.is_active == True,
            )
        )
        return result.scalar_one_or_none()
