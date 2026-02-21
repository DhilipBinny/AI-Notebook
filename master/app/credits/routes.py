"""
Credit and usage tracking API routes.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.auth.dependencies import get_current_active_user, get_current_admin_user
from app.users.models import User
from .service import CreditService
from .schemas import (
    CreditBalanceResponse,
    UsageHistoryResponse,
    UsageRecordResponse,
    LLMPricingResponse,
    AdminCreditAdjust,
    AdminPricingUpdate,
    UsageReport,
)

router = APIRouter(tags=["Credits"])


# =============================================================================
# User routes
# =============================================================================

@router.get("/credits/balance", response_model=CreditBalanceResponse)
async def get_balance(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user's credit balance."""
    service = CreditService(db)
    credit = await service.get_balance(current_user.id)

    if not credit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credit record not found",
        )

    return CreditBalanceResponse(
        user_id=credit.user_id,
        balance_cents=credit.balance_cents,
        balance_dollars=credit.balance_cents / 100,
        total_deposited_cents=credit.total_deposited_cents,
        total_consumed_cents=credit.total_consumed_cents,
        last_charged_at=credit.last_charged_at,
    )


@router.get("/credits/usage", response_model=UsageHistoryResponse)
async def get_usage_history(
    page: int = 1,
    page_size: int = 50,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get paginated usage history for the current user."""
    service = CreditService(db)
    records, total = await service.get_usage_history(
        current_user.id, page=page, page_size=page_size
    )

    return UsageHistoryResponse(
        records=[
            UsageRecordResponse(
                id=r.id,
                provider=r.provider,
                model=r.model,
                request_type=r.request_type.value if hasattr(r.request_type, 'value') else r.request_type,
                input_tokens=r.input_tokens,
                output_tokens=r.output_tokens,
                cost_cents=r.cost_cents,
                is_own_key=r.is_own_key,
                created_at=r.created_at,
            )
            for r in records
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/credits/pricing", response_model=list[LLMPricingResponse])
async def get_pricing(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all active LLM pricing."""
    service = CreditService(db)
    pricing_list = await service.get_all_pricing()

    return [
        LLMPricingResponse(
            id=p.id,
            provider=p.provider,
            model=p.model,
            input_cost_per_1m_cents=p.input_cost_per_1m_cents,
            output_cost_per_1m_cents=p.output_cost_per_1m_cents,
            margin_multiplier=float(p.margin_multiplier),
            is_active=p.is_active,
        )
        for p in pricing_list
    ]


# =============================================================================
# Admin routes
# =============================================================================

@router.post("/admin/credits/adjust", response_model=CreditBalanceResponse)
async def admin_adjust_credits(
    request: AdminCreditAdjust,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Admin: adjust a user's credit balance."""
    service = CreditService(db)
    credit = await service.admin_adjust_credits(
        request.user_id, request.amount_cents, request.reason
    )

    if not credit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    await db.commit()

    return CreditBalanceResponse(
        user_id=credit.user_id,
        balance_cents=credit.balance_cents,
        balance_dollars=credit.balance_cents / 100,
        total_deposited_cents=credit.total_deposited_cents,
        total_consumed_cents=credit.total_consumed_cents,
        last_charged_at=credit.last_charged_at,
    )


@router.post("/admin/credits/pricing", response_model=LLMPricingResponse)
async def admin_update_pricing(
    request: AdminPricingUpdate,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Admin: update LLM pricing."""
    service = CreditService(db)
    pricing = await service.update_pricing(
        provider=request.provider,
        model=request.model,
        input_cost=request.input_cost_per_1m_cents,
        output_cost=request.output_cost_per_1m_cents,
        margin=request.margin_multiplier,
        is_active=request.is_active,
    )

    if not pricing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pricing entry not found",
        )

    await db.commit()

    return LLMPricingResponse(
        id=pricing.id,
        provider=pricing.provider,
        model=pricing.model,
        input_cost_per_1m_cents=pricing.input_cost_per_1m_cents,
        output_cost_per_1m_cents=pricing.output_cost_per_1m_cents,
        margin_multiplier=float(pricing.margin_multiplier),
        is_active=pricing.is_active,
    )


# =============================================================================
# Internal route (called by playground via master proxy)
# =============================================================================

@router.post("/internal/usage/report")
async def report_usage(
    report: UsageReport,
    db: AsyncSession = Depends(get_db),
):
    """
    Internal endpoint for recording usage after LLM calls.
    Called by the master SSE proxy after receiving a done event from playground.
    """
    service = CreditService(db)
    record = await service.record_usage_and_deduct(
        user_id=report.user_id,
        project_id=report.project_id,
        provider=report.provider,
        model=report.model,
        request_type=report.request_type,
        input_tokens=report.input_tokens,
        output_tokens=report.output_tokens,
        cached_tokens=report.cached_tokens,
        is_own_key=report.is_own_key,
    )

    await db.commit()

    # Get updated balance
    credit = await service.get_balance(report.user_id)
    balance_cents = credit.balance_cents if credit else 0

    return {
        "success": True,
        "cost_cents": record.cost_cents,
        "balance_cents": balance_cents,
    }
