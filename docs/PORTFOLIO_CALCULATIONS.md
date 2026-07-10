# Portfolio Calculations Overview

This document provides a detailed mathematical and functional overview of the financial and statistical calculations utilized in [ticker_period_ranks_data.py](file:///Users/philipmassey/projects/market_data/portfolio/ticker_period_ranks_data.py) to rank ticker performance across multiple historical periods.

---

## 1. Core Performance Metrics

The metrics in this section are calculated over a sequence of $N$ business days for a list of target tickers.

### A. Overall Percentage Change (`over_pc`)
Measures the overall return from the oldest available closing price to the newest closing price in the period.
$$\text{over\_pc} = \left( \frac{\text{Price}_{\text{newest}} - \text{Price}_{\text{oldest}}}{\text{Price}_{\text{oldest}}} \right) \times 100$$

### B. Period Return Mean (`pc_mean`)
The average of consecutive period-to-period returns. For a sequence of prices $P_1, P_2, \dots, P_T$, the period return $r_t$ at step $t$ is:
$$r_t = \left( \frac{P_t - P_{t-1}}{P_{t-1}} \right) \times 100$$
$$\text{pc\_mean} = \frac{1}{T-1} \sum_{t=2}^{T} r_t$$

### C. Period Return Volatility (`pc_std`)
The standard deviation of period-to-period returns, representing the asset's historical volatility during the period:
$$\text{pc\_std} = \sqrt{\frac{1}{T-2} \sum_{t=2}^{T} (r_t - \text{pc\_mean})^2}$$

### D. Risk-Reward Ratio (`risk_reward`)
A simplified proxy for the Sharpe Ratio. It measures the excess return per unit of volatility:
$$\text{risk\_reward} = \begin{cases} 
\frac{\text{pc\_mean}}{\text{pc\_std}} & \text{if } \text{pc\_std} > 0 \\
0 & \text{otherwise}
\end{cases}$$

---

## 2. Advanced Ranking Metrics

### A. Relative Strength vs. Industry (`rel_strength_ind`)
Measures the difference between a ticker's overall percentage change and the average overall percentage change of all tickers in the same sector and industry:
$$\text{rel\_strength\_ind} = \text{over\_pc} - \mu_{\text{industry}}(\text{over\_pc})$$

### B. Probability of a Green Period (`prob_green_day_%`)
Calculates the statistical probability that a single period return is positive ($r_t > 0$), assuming the returns are normally distributed with mean $\mu = \text{pc\_mean}$ and standard deviation $\sigma = \text{pc\_std}$.

Using the standard normal cumulative distribution function (CDF) $\Phi(x)$:
$$P(r_t > 0) = 1 - \Phi\left(\frac{0 - \mu}{\sigma}\right) = \Phi\left(\frac{\mu}{\sigma}\right)$$

In terms of the error function $\text{erf}(x)$, this is evaluated as:
$$\text{prob\_green\_day\_}\% = 50.0 \times \left[ 1.0 + \text{erf}\left( \frac{\text{pc\_mean}}{\text{pc\_std} \sqrt{2}} \right) \right]$$

### C. Stretch Score (`stretch_score`)
Measures how many standard deviations the overall return (`over_pc`) is away from zero. It serves as a normalization of total return relative to the volatility of the asset:
$$\text{stretch\_score} = \begin{cases} 
\frac{\text{over\_pc}}{\text{pc\_std}} & \text{if } \text{pc\_std} > 0 \\
0 & \text{otherwise}
\end{cases}$$

### D. Kelly Fraction (`kelly_fraction`)
An approximation of the optimal bet sizing fraction using the Kelly Criterion for continuous outcomes. It dictates what fraction of capital to allocate to maximize the exponential growth rate of the portfolio:
$$\text{kelly\_fraction} = \begin{cases} 
\frac{\text{pc\_mean}}{\text{pc\_std}^2} & \text{if } \text{pc\_std} > 0 \\
0 & \text{otherwise}
\end{cases}$$

---

## 3. Period Definitions

The ranking process combines performance across 5 specific historical window periods:

| Period Key | Parameter | Description |
| :--- | :--- | :--- |
| **Daily** | `calc_percent_daily` | Past 10 consecutive business days |
| **1 Week** | `calc_percent_weekly` | Past 6 consecutive business weeks |
| **2 Weeks** | `calc_percent_2weekly` | Past 12 consecutive business weeks (bi-weekly steps) |
| **1 Month** | `calc_percent_monthly` | Past 6 consecutive business months |
| **2 Months** | `calc_percent_2monthly` | Past 12 consecutive business months (bi-monthly steps) |

---

## 4. Ranking and Formatting

All calculated metrics are ranked globally across all tickers within each period:
* **Ranking Method**: Descending order, using the `'min'` method (ties receive the lowest numerical rank, e.g., if two tickers share rank 1, both get rank 1, and the next receives rank 3).
* **Ranks Generated**:
  * `risk_reward_rank`
  * `rel_strength_ind_rank`
  * `prob_green_day_rank`
  * `stretch_score_rank`
  * `kelly_fraction_rank`
