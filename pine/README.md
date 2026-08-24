# NexusTrade AI - Pine Script webhook feed

`nexustrade-webhook-alerts.pine` is a companion indicator that lets any
symbol/timeframe available on TradingView feed live OHLCV bars into
NexusTrade AI's `POST /webhook/tradingview` endpoint — the same candle
store / Redis pub-sub pipeline, and therefore the same SMC + Elliott
confluence signal engine, that the Binance, Bybit, OANDA and Polygon
ingestion feeds already use. Use it for any symbol that doesn't have a
dedicated exchange WS integration in `backend/app/ingestion/` (e.g. an
index, a stock, or an FX/crypto pair those feeds don't cover).

## 1. Add the indicator to a chart

1. Open the symbol/timeframe you want to feed into NexusTrade AI.
2. Pine Editor -> paste `nexustrade-webhook-alerts.pine` -> **Add to chart**
   (or publish it privately and add it from your Indicators list).
3. Settings you'll typically touch:
   - **Swing Lookback** — purely cosmetic/structural (the plotted
     triangles); it does not affect the webhook payload.
   - **Fire webhook alert() on confirmed bar close** — leave on; this is
     what actually drives the webhook.
   - **Symbol override** — leave blank unless the backend needs a symbol
     string that differs from TradingView's own ticker for this instrument.

## 2. Create the TradingView Alert

The indicator only *calls* `alert()`; TradingView won't send anything
anywhere until you create an **Alert** on top of it:

1. Right-click the chart -> **Add alert** (or the clock icon in the
   right-hand toolbar).
2. **Condition**: pick this indicator, then choose **"Any alert() function
   call"** — not one of the two swing-high/swing-low `alertcondition`
   entries, those are just chart-side convenience alerts.
3. **Trigger**: **"Once Per Bar Close"**. This must match the script's own
   `barstate.isconfirmed` gate — the platform's own README documents this
   repo's "no repainting the trailing edge" convention, and firing on an
   unconfirmed bar would violate it by sending a bar that can still change.
4. **Notifications** -> enable **Webhook URL** and set it to:

   ```
   https://<your-backend-host>/webhook/tradingview?secret=<TRADINGVIEW_WEBHOOK_SECRET>
   ```

   Use the `?secret=` query-param form, not a header. TradingView's alert
   dialog has no field for custom HTTP headers, so `X-Webhook-Secret`
   (the other option the backend accepts, per
   `backend/app/api/routes/webhook.py`) is not reachable from here — only
   the query-param path is. If the backend operator left
   `TRADINGVIEW_WEBHOOK_SECRET` unset, the `?secret=` param can be omitted,
   but that's local-dev-only: an unauthenticated webhook accepts data from
   anyone who finds the URL.
5. Message field: leave it on the default `{{strategy.order.alert_message}}`
   placeholder (or simply the default text) — for "Any alert() function
   call" conditions, TradingView sends the exact string built by the
   script's `alert()` call, ignoring the message box, so no further setup
   is needed there.
6. Save. Every confirmed bar close now POSTs a body like:

   ```json
   {"symbol":"BTCUSDT","timeframe":"1h","open":43250.50,"high":43310.00,"low":43180.25,"close":43267.75,"volume":128.4321}
   ```

   which matches `TradingViewAlertPayload` in
   `backend/app/models/schemas.py` field-for-field (`time` is omitted; the
   backend defaults it to receipt time, per the schema).

## Notes

- One alert = one symbol/timeframe. Add the indicator + a separate alert
  per chart you want streamed in.
- `timeframe` is derived from the chart's resolution and mapped to the
  same `"1m"/"5m"/"15m"/"1h"/"4h"/"1d"`-style strings
  `backend/app/ingestion/binance_ws.py`'s `BINANCE_INTERVALS` uses, so a
  TradingView bar lands in the same store bucket a Binance kline of the
  same interval would.
- This script is intentionally a lightweight companion, not a
  reimplementation of `backend/app/analysis/smc.py` — it only plots
  confirmed swing highs/lows for its own on-chart usefulness. All BOS/CHoCH,
  order block, FVG, liquidity, and Elliott Wave analysis happens
  server-side once the candles land in the store.
- TradingView alerts run on TradingView's own infrastructure and don't
  require the chart tab to stay open, but they do require an active
  TradingView plan tier that supports webhook notifications.
