# Moomoo Options Yield Calculator: YTD Total Premiums & Annualized Returns

A Python script for the **Moomoo OpenD API** designed to calculate aggregate Year-to-Date (YTD) premium metrics and annualized rates of return for options strategies—metrics that are not natively displayed in the standard user interface.

This script interfaces directly with your live transaction history via the local OpenD gateway to automate the calculation of options portfolio returns and capital efficiency.

---

## 🛑 Limitations of the Standard UI
The standard platform interface lacks aggregate analytics tailored specifically for short options strategies:
* **No Aggregate Premium Tracking:** Rolling historical net gains and losses are not totaled over a YTD period, requiring manual data tracking or spreadsheet exports.
* **No Time-Weighted Velocity Metrics:** The platform does not account for trade duration. A premium collected over 7 days has a different velocity than the same premium collected over 60 days, but the UI treats them identically.
* **Missing Return on Capital (ROC):** Standard interfaces calculate option return percentages based on premium values rather than the actual cash collateral required to back the trade.

---

## ✨ System Functions
This script addresses these limitations by processing transaction logs through a direct calculation pipeline:

1. **Transaction Aggregation:** Pulls historical option execution logs from January 1st of the current year to the present time.
2. **Strike Price Parsing:** Uses regular expressions to extract option strike prices directly from standard ticker codes (e.g., extracting strike `$150.00` from `US.AAPL260618C150000`).
3. **Collateral Cost Basis Mapping:** 
   * **Cash-Secured Puts (CSP):** Sets the cost basis to 100% of the assignment cash requirement (`Strike * 100 * Quantity`).
   * **Covered Calls (CC):** Uses the strike price as a proxy for the underlying stock equity footprint.
4. **Annualized Yield Calculations:** Calculates exact calendar holding times between opening and closing trades to determine annualized performance per contract and across the portfolio.

---

## 📊 Analytics Dashboard Visual Output Example

When executed, the script processes your live portfolio data and prints two distinct reporting layers:

```text
=================================== CONTRACT BREAKDOWN ===================================

Option Symbol          | Net P&L     | Days  | Collateral   | Ann. Return | Status
--------------------------------------------------------------------------------------------
US.NVDA260320P125000   | +\$4,500.00  | 14    | \$12,500.00   | +146.2%     | Fully Closed
US.TSLA260417P180000   | +\$8,200.00  | 28    | \$18,000.00   | +78.4%      | Fully Closed
US.AAPL260515P175000   | +\$3,100.00  | 35    | \$17,500.00   | +19.7%      | Expired/Open Short
US.AMD260605P150000    | -\$1,500.00  | 7     | \$15,000.00   | -41.3%      | Fully Closed

====================== TOTAL PROFIT & RETURN PER TICKER ======================

Ticker Symbol   | Net Profit/Loss   | Peak Collateral      | Ticker Ann. Return
--------------------------------------------------------------------------------
TSLA            | +\$8,200.00        | \$18,000.00           | +78.4%            
NVDA            | +\$4,500.00        | \$12,500.00           | +146.2%           
AAPL            | +\$3,100.00        | \$17,500.00           | +19.7%            
AMD             | -\$1,500.00        | \$15,000.00           | -41.3%            
================================================================================
GRAND TOTAL PORTFOLIO P&L:  \$14,300.00
PORTFOLIO YTD TIME ELAPSED: 155 Days
PORTFOLIO ANNUALIZED RATE:  22.70% (Based on \$63,000.00 Max Capital Allocated)
================================================================================
```

---

## 🧮 Mathematical Logic Foundations

### Per-Ticker Annualized Return
To calculate return percentages based on actual trade duration, the script applies a standard Compounded Annual Growth Rate (CAGR) formula:

$$\text{Annualized Return} = \left(1 + \frac{\text{Net Realised P\&L}}{\text{Max Collateral Blocked}}\right)^{\frac{365.25}{\text{Holding Days}}} - 1$$

### Portfolio-Wide Annualized Rate
The script avoids averaging individual ticker percentages. Instead, it aggregates concurrent peak locked collateral relative to total YTD time elapsed:

$$\text{Portfolio Rate} = \left(1 + \frac{\text{Grand Total Realised P\&L}}{\text{Cumulative Peak Portfolio Collateral}}\right)^{\frac{365.25}{\text{YTD Days Elapsed}}} - 1$$

---

## ⚡ Quick Start & Deployment Requirements

### 1. Prerequisites
* **Moomoo OpenD Client:** The native Moomoo desktop application with the OpenD API gateway toggled active.
* **Python Runtime Environment:** Python 3.8 to 3.11 recommended.

### 2. Installation
Install the necessary system dependencies via standard package managers:
```bash
pip install pandas moomoo-api
```

### 3. Execution
Ensure your Moomoo desktop app is open and running on local port `11113`, then launch the script:
```bash
python totalpremiumv2.py
```

---

## 🔒 Production Security and Safety Protocols
* **Read-Only Data Access:** This script runs strictly read-only execution logic using `history_deal_list_query()`. It lacks routing functions, preventing unintended order placement.
* **Local Loopback Network Integrity:** API execution stays inside a localized loopback address (`127.0.0.1`). Your trade details are never broadcasted to external cloud networks.
