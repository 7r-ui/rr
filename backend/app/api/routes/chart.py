from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.core.config import get_settings
from app.models.schemas import ChartAnalysisRequest, ChartAnalysisResponse, ChartReport
from app.vision.model_client import analyze_chart_with_vision_model, generate_full_report
from app.vision.parser import apply_price_mapping, decode_image, detect_horizontal_levels

router = APIRouter(prefix="/analyze-chart", tags=["vision"])

MAX_UPLOAD_BYTES = 8 * 1024 * 1024


@router.post("", response_model=ChartAnalysisResponse)
async def analyze_chart(
    image: UploadFile = File(...),
    symbol: str | None = Form(default=None),
    timeframe: str | None = Form(default=None),
    price_at_top: float | None = Form(default=None),
    price_at_bottom: float | None = Form(default=None),
) -> ChartAnalysisResponse:
    raw = await image.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Chart image exceeds 8MB upload limit.")

    try:
        cv_image = decode_image(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    price_axis_hint = None
    if price_at_top is not None and price_at_bottom is not None:
        price_axis_hint = (price_at_top, price_at_bottom)

    request = ChartAnalysisRequest(
        symbol=symbol, timeframe=timeframe, price_axis_hint=price_axis_hint
    )

    cv_levels = detect_horizontal_levels(cv_image)
    height, width = cv_image.shape[:2]
    model_levels = await analyze_chart_with_vision_model(
        raw, image_height=height, image_width=width
    )

    levels = apply_price_mapping(cv_levels + model_levels, cv_image, request)
    levels.sort(key=lambda lv: lv.confidence, reverse=True)

    notes = (
        f"{len(cv_levels)} level(s) from edge/Hough detection, "
        f"{len(model_levels)} from vision model. "
        + ("Price axis calibrated." if price_axis_hint else "No price axis hint provided — prices are unmapped.")
    )

    return ChartAnalysisResponse(symbol=symbol, levels=levels, notes=notes)


@router.post("/report", response_model=ChartReport)
async def analyze_chart_report(
    image: UploadFile = File(...),
    symbol: str | None = Form(default=None),
    account_balance: float | None = Form(default=None),
    risk_pct: float | None = Form(default=None),
) -> ChartReport:
    """The full SMC/Price-Action structured report (market structure, trade
    setup, risk management, conviction) from one chart screenshot, per the
    prompt in FULL_REPORT_PROMPT_TEMPLATE. Requires ANTHROPIC_API_KEY or
    OPENAI_API_KEY to be configured — returns 503 rather than a fabricated
    report when neither is set."""
    raw = await image.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Chart image exceeds 8MB upload limit.")

    try:
        decode_image(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    settings = get_settings()
    report = await generate_full_report(
        raw,
        symbol=symbol,
        account_balance=account_balance or settings.default_account_balance,
        risk_pct=risk_pct or settings.default_risk_pct,
    )
    if report is None:
        raise HTTPException(
            status_code=503,
            detail="No vision model configured (set ANTHROPIC_API_KEY or OPENAI_API_KEY), "
            "or the model's response didn't parse into a structured report.",
        )
    return report
