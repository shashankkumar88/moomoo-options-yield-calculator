from datetime import datetime
import pandas as pd
import re
from moomoo import *

# =====================================================================
# 1. INITIALIZE CONNECTION & CONFIGURATION
# =====================================================================
MARKET = TrdMarket.US  # US Market Options
ENV = TrdEnv.REAL  # Real account trading. Change to TrdEnv.SIMULATE for paper trading.
PORT = 11113

print(f"[LOG 1/6] Initializing OpenSecTradeContext connection object on port {PORT}...")
trd_ctx = OpenSecTradeContext(filter_trdmarket=MARKET, host='127.0.0.1', port=PORT)


def calculate_portfolio_pnl():
    # Unlock trade account if accessing live production execution data
    # trd_ctx.unlock_trade(password="YOUR_6_DIGIT_PASS")

    # Set temporal constraints for YTD lookback (Jan 1st of Current Year to Now)
    current_time = datetime.now()
    end_date = current_time.strftime("%Y-%m-%d %H:%M:%S")
    start_date = f"{current_time.year}-01-01 00:00:00"

    # Exact total calendar days elapsed YTD for your portfolio
    ytd_start_dt = datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S")
    portfolio_days = max((current_time - ytd_start_dt).days, 1)

    print(f"[LOG 2/6] Querying moomoo OpenD for YTD history from {start_date} to {end_date}...")

    # 2. FETCH HISTORICAL EXECUTION DEALS
    ret, data = trd_ctx.history_deal_list_query(
        start=start_date,
        end=end_date,
        trd_env=ENV
    )

    print(f"[LOG 3/6] API Response received with status code: {ret}")

    if ret != RET_OK:
        print(f"[ERROR] API failed to retrieve data from OpenD. Details: {data}")
        trd_ctx.close()
        return

    print(f"[LOG 4/6] Raw trade records retrieved: {len(data)} total rows found.")

    if data.empty:
        print(f"[WARNING] Zero trade execution records found for YTD ({current_time.year}).")
        trd_ctx.close()
        return

    print("[LOG 5/6] Isolating options trades and sorting transactions chronologically...")

    # RESTORED FILTER: Look for both Calls (C) and Puts (P)
    options_df = data[
        (data['code'].str.contains(r'[C|P]\d+', regex=True)) &
        (data['qty'] > 0)
        ].copy()

    print(f"         Filtered down to {len(options_df)} individual option contract execution entries.")

    if options_df.empty:
        print("[WARNING] No underlying option contract fills found in your transaction logs.")
        trd_ctx.close()
        return

    # Sort chronologically by execution time
    options_df = options_df.sort_values(by='create_time')

    summary_data = {}
    ticker_summary = {}

    print("[LOG 6/6] Pipeline active: Running transaction grouping loop...")

    # =====================================================================
    # 3. LEDGER AGGREGATION PIPELINE
    # =====================================================================
    for index, row in options_df.iterrows():
        code = row['code']
        qty = float(row['qty'])
        price = float(row['price'])
        side_str = str(row['trd_side']).upper()
        trade_time = pd.to_datetime(row['create_time'])

        # Parse clean underlying ticker symbol
        ticker_match = re.match(r"(?:US\.)?([A-Z]+)\d+", code)
        ticker = ticker_match.group(1) if ticker_match else "UNKNOWN"

        # REGEX UPDATED: Dynamic capture for either C or P strike patterns
        strike_match = re.search(r'[C|P](\d+)', code)
        if strike_match:
            strike_price = float(strike_match.group(1)) / 1000.0
        else:
            strike_price = 0.0

        # COLLATERAL RULES:
        # Puts = 100% Cash-Secured Put value
        # Calls = Covered Call share value proxy based on strike price entry
        trade_collateral = strike_price * 100 * qty

        if code not in summary_data:
            summary_data[code] = {
                'total_sell_cash': 0.0,
                'total_buy_cash': 0.0,
                'total_qty_sold': 0.0,
                'total_qty_bought': 0.0,
                'ticker': ticker,
                'first_trade_time': trade_time,
                'last_trade_time': trade_time,
                'max_collateral': 0.0
            }

        if ticker not in ticker_summary:
            ticker_summary[ticker] = {
                'net_pnl': 0.0,
                'first_trade_time': trade_time,
                'last_trade_time': trade_time,
                'peak_collateral': 0.0
            }

        summary_data[code]['last_trade_time'] = trade_time
        summary_data[code]['max_collateral'] = max(summary_data[code]['max_collateral'], trade_collateral)

        ticker_summary[ticker]['last_trade_time'] = trade_time
        ticker_summary[ticker]['peak_collateral'] = max(ticker_summary[ticker]['peak_collateral'], trade_collateral)

        trade_cash = qty * price * 100

        if "SELL" in side_str:
            summary_data[code]['total_sell_cash'] += trade_cash
            summary_data[code]['total_qty_sold'] += (qty * 100)
            ticker_summary[ticker]['net_pnl'] += trade_cash
        elif "BUY" in side_str:
            summary_data[code]['total_buy_cash'] += trade_cash
            summary_data[code]['total_qty_bought'] += (qty * 100)
            ticker_summary[ticker]['net_pnl'] -= trade_cash

            # =====================================================================
    # 4. PRINT TABLE 1: DETAILED CONTRACT BREAKDOWN
    # =====================================================================
    print(f"\n{'=' * 35} CONTRACT BREAKDOWN {'=' * 35}\n")
    print(f"{'Option Symbol':<22} | {'Net P&L':<11} | {'Days':<5} | {'Collateral':<12} | {'Ann. Return':<12} | Status")
    print("-" * 92)

    grand_total_pnl = 0.0
    total_portfolio_collateral = 0.0

    for code, stats in summary_data.items():
        total_pnl = stats['total_sell_cash'] - stats['total_buy_cash']
        grand_total_pnl += total_pnl
        holding_days = max((stats['last_trade_time'] - stats['first_trade_time']).days, 1)
        collateral_used = stats['max_collateral']

        if collateral_used > 0:
            return_rate = total_pnl / collateral_used
            ann_return = ((1 + return_rate) ** (365.25 / holding_days)) - 1 if return_rate > -1 else -1.0
            ann_ret_str = f"{ann_return * 100:+,.1f}%"
        else:
            ann_ret_str = "0.0%"

        if stats['total_qty_sold'] == stats['total_qty_bought'] and stats['total_qty_sold'] > 0:
            status = "Fully Closed"
        elif stats['total_qty_sold'] > 0 and stats['total_qty_bought'] == 0:
            status = "Expired/Open Short"
        elif stats['total_qty_bought'] > 0 and stats['total_qty_sold'] == 0:
            status = "Open Long"
        else:
            status = "Partial/Adjusted"

        sign = "+" if total_pnl >= 0 else "-"
        pnl_str = f"{sign}${abs(total_pnl):,.2f}"
        collateral_str = f"${collateral_used:,.2f}"

        print(f"{code:<22} | {pnl_str:<11} | {holding_days:<5} | {collateral_str:<12} | {ann_ret_str:<12} | {status}")

    # =====================================================================
    # 5. PRINT TABLE 2: AGGREGATED TICKER NET PROFIT
    # =====================================================================
    print(f"\n{'=' * 22} TOTAL PROFIT & RETURN PER TICKER {'=' * 21}\n")
    print(f"{'Ticker Symbol':<15} | {'Net Profit/Loss':<17} | {'Peak Collateral':<20} | {'Ticker Ann. Return':<20}")
    print("-" * 80)


    for ticker, stats in sorted(ticker_summary.items(), key=lambda x: x[1]['net_pnl'], reverse=True):
        net_pnl = stats['net_pnl']
        ticker_days = max((stats['last_trade_time'] - stats['first_trade_time']).days, 1)
        peak_collateral = stats['peak_collateral']
        total_portfolio_collateral += peak_collateral

        if peak_collateral > 0:
            ticker_return_rate = net_pnl / peak_collateral
            ticker_ann_return = ((1 + ticker_return_rate) ** (
                        365.25 / ticker_days)) - 1 if ticker_return_rate > -1 else -1.0
            t_ann_str = f"{ticker_ann_return * 100:+,.1f}%"
        else:
            t_ann_str = "0.0%"

        pnl_str = f"{'+' if net_pnl >= 0 else '-'}${abs(net_pnl):,.2f}"
        collateral_str = f"${peak_collateral:,.2f}"

        print(f"{ticker:<15} | {pnl_str:<17} | {collateral_str:<20} | {t_ann_str:<20}")

    # =====================================================================
    # 6. PORTFOLIO WIDE ANNUALIZATION SUMMARY
    # =====================================================================
    if total_portfolio_collateral > 0:
        portfolio_return_rate = grand_total_pnl / total_portfolio_collateral
        portfolio_ann_return = ((1 + portfolio_return_rate) ** (365.25 / portfolio_days)) - 1
        portfolio_ann_str = f"{portfolio_ann_return * 100:,.2f}%"
    else:
        portfolio_ann_str = "0.00%"

    print("=" * 80)
    print(f"GRAND TOTAL PORTFOLIO P&L:  ${grand_total_pnl:,.2f}")
    print(f"PORTFOLIO YTD TIME ELAPSED: {portfolio_days} Days")
    print(
        f"PORTFOLIO ANNUALIZED RATE:  {portfolio_ann_str} (Based on ${total_portfolio_collateral:,.2f} Max Capital Allocated)")
    print("=" * 80)

    trd_ctx.close()
    print("\nConnection closed successfully.")


if __name__ == "__main__":
    calculate_portfolio_pnl()
