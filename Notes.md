This Notes are based on "The Price Impact of Order Book Events " Papers By  Cont et Kukanov et Stoikov 2014

Order book events: limit orders, market orders and cancellations

over a short time intervals, we found that price changes are mainly driven by the *order flow imbalance* (OFI), defined as the imbalance between supply and demand at the best bid and ask prices, the study below shows a linear relation between OFI and price changes, with a slope inversely proportional to market depth - market’s ability to sustain large order volumes without causing significant price fluctuations - and these results are robust to intraday seasonality effects and stable across other time scales and stocks

# Order Book Model: Formulas

## Price change (definition)

$\Delta P_k^{b,s} = P_k^{b,s} - P_{k-1}^{b,s}$, Where :

- $\Delta P_k^{b,s}$: change in the bid ($b$) or ask ($s$) price over the interval $[t_{k-1}, t_k]$
- $P_k^{b}$: bid price at time $t_k$
- $P_k^{s}$: ask price at time $t_k$
- $P_{k-1}^{b,s}$: bid or ask price at time $t_{k-1}$

## Equation (1): Bid price change

$\Delta P_k^b = \delta \left\lceil \dfrac{L_k^b - C_k^b - M_k^s}{D} \right\rceil$, Where :

- $\Delta P_k^b$: change in the bid price over $[t_{k-1}, t_k]$
- $\delta$: tick size
- $L_k^b$: total size of buy orders that arrived to the current best bid during $[t_{k-1}, t_k]$
- $C_k^b$: total size of buy orders canceled from the current best bid during $[t_{k-1}, t_k]$
- $M_k^s$: total size of marketable sell orders that arrived to the current best bid during $[t_{k-1}, t_k]$
- $D$: number of shares (depth) at each price level beyond the best bid and ask
- $\lceil \cdot \rceil$: ceiling function

## Equation (2): Ask price change

$\Delta P_k^s = -\delta \left\lceil \dfrac{L_k^s - C_k^s - M_k^b}{D} \right\rceil$, Where :

- $\Delta P_k^s$: change in the ask price over $[t_{k-1}, t_k]$
- $\delta$: tick size
- $L_k^s$: total size of sell orders that arrived to the current best ask during $[t_{k-1}, t_k]$
- $C_k^s$: total size of sell orders canceled from the current best ask during $[t_{k-1}, t_k]$
- $M_k^b$: total size of marketable buy orders that arrived to the current best ask during $[t_{k-1}, t_k]$
- $D$: number of shares (depth) at each price level beyond the best bid and ask
- $\lceil \cdot \rceil$: ceiling function

## Normalized mid-price

$P_k = \dfrac{P_k^b + P_k^s}{2\delta}$, Where :

- $P_k$: mid-price at time $t_k$, normalized by tick size
- $P_k^b$: bid price at time $t_k$
- $P_k^s$: ask price at time $t_k$
- $\delta$: tick size

## Equation (3): Mid-price change vs. order flow imbalance

$\Delta P_k = \dfrac{\mathrm{OFI}_k}{2D} + \epsilon_k$, Where :

- $\Delta P_k$: change in the normalized mid-price over $[t_{k-1}, t_k]$
- $\mathrm{OFI}_k$: order flow imbalance (net order flow) over $[t_{k-1}, t_k]$
- $D$: number of shares (depth) at each price level beyond the best bid and ask
- $\epsilon_k$: truncation error

## Equation (4): Order flow imbalance

$\mathrm{OFI}_k = L_k^b - C_k^b - M_k^s - L_k^s + C_k^s + M_k^b$, Where :

- $\mathrm{OFI}_k$: order flow imbalance (net order flow) over $[t_{k-1}, t_k]$
- $L_k^b$: total size of buy orders that arrived to the current best bid
- $C_k^b$: total size of buy orders canceled from the current best bid
- $M_k^s$: total size of marketable sell orders that arrived to the current best bid
- $L_k^s$: total size of sell orders that arrived to the current best ask
- $C_k^s$: total size of sell orders canceled from the current best ask
- $M_k^b$: total size of marketable buy orders that arrived to the current best ask

## Equation (5): Mid-price change vs. trade imbalance

$\Delta P_k = \dfrac{\mathrm{TI}_k}{2D} + \eta_k$, Where :

- $\Delta P_k$: change in the normalized mid-price over $[t_{k-1}, t_k]$
- $\mathrm{TI}_k$: trade imbalance over $[t_{k-1}, t_k]$
- $D$: number of shares (depth) at each price level beyond the best bid and ask
- $\eta_k$: noise term collecting limit order submissions, cancellations, and the truncation error

## Equation (6): Trade imbalance

$\mathrm{TI}_k = M_k^b - M_k^s$, Where :

- $\mathrm{TI}_k$: trade imbalance over $[t_{k-1}, t_k]$
- $M_k^b$: total size of marketable buy orders that arrived to the current best ask
- $M_k^s$: total size of marketable sell orders that arrived to the current best bid

## Noise term in equation (5)

$\eta_k = \dfrac{L_k^b - C_k^b - L_k^s + C_k^s}{2D} + \epsilon_k$, Where :

- $\eta_k$: noise term in equation (5)
- $L_k^b$: total size of buy orders that arrived to the current best bid
- $C_k^b$: total size of buy orders canceled from the current best bid
- $L_k^s$: total size of sell orders that arrived to the current best ask
- $C_k^s$: total size of sell orders canceled from the current best ask
- $D$: number of shares (depth) at each price level beyond the best bid and ask
- $\epsilon_k$: truncation error

## Condition: limit order activity dominates

$|L_k^{b,s}|,\ |C_k^{b,s}| \gg |M_k^{b,s}|$, Where :

- $|L_k^{b,s}|$: absolute size of limit order arrivals at the best bid or ask
- $|C_k^{b,s}|$: absolute size of cancellations at the best bid or ask
- $|M_k^{b,s}|$: absolute size of marketable buy or sell orders 



Real order books are more complex than the stylized model, so the authors assume a noisy linear relation between price changes and order flow imbalance that holds locally over short intervals. The price impact coefficient $\beta_i$ varies across longer intervals and is modeled as inversely related to market depth, with **$\frac{1}{2\beta_i}$** read as an **implied depth**. A parallel relation using trade imbalance is also considered, but it is expected to be much noisier.
## Time interval nesting

$[t_{k-1,i},\ t_{k,i}] \subset [T_{i-1},\ T_i]$, Where :

- $[t_{k-1,i},\ t_{k,i}]$: $k$-th short time interval, on which the price–OFI relation holds locally
- $[T_{i-1},\ T_i]$: $i$-th longer time interval containing the short intervals
- $k$: index of the short interval
- $i$: index of the longer interval

## Equation (7): Price change vs. order flow imbalance

$\Delta P_{k,i} = \beta_i\, \mathrm{OFI}_{k,i} + \epsilon_{k,i}$, Where :

- $\Delta P_{k,i}$: price change over the $k$-th short interval within the $i$-th longer interval
- $\beta_i$: price impact coefficient for the $i$-th time interval
- $\mathrm{OFI}_{k,i}$: order flow imbalance over the $k$-th short interval within the $i$-th longer interval
- $\epsilon_{k,i}$: noise term summarizing influences of other factors (e.g., deeper levels of the order book)

## Implied order book depth

$\dfrac{1}{2\beta_i}$, Where :

- $\dfrac{1}{2\beta_i}$: implied order book depth for the $i$-th time interval
- $\beta_i$: price impact coefficient for the $i$-th time interval

## Equation (8): Price impact coefficient vs. market depth

$\beta_i = \dfrac{c}{D_i^{\lambda}} + \nu_i$, Where :

- $\beta_i$: price impact coefficient for the $i$-th time interval
- $c$: constant
- $\lambda$: constant (exponent on depth)
- $D_i$: market depth during the $i$-th time interval
- $\nu_i$: noise term

## Stylized order book model (special case of equation (8))

$c = \dfrac{1}{2},\ \lambda = 1$, Where :

- $c$: constant in equation (8)
- $\lambda$: exponent on depth in equation (8)

## Equation (9): Price change vs. trade imbalance

$\Delta P_{k,i} = \beta_i^{T}\, \mathrm{TI}_{k,i} + \eta_{k,i}$, Where :

- $\Delta P_{k,i}$: price change over the $k$-th short interval within the $i$-th longer interval
- $\beta_i^{T}$: price impact coefficient of trades for the $i$-th time interval ($T$ is a label for "trade", not a transpose)
- $\mathrm{TI}_{k,i}$: trade imbalance over the $k$-th short interval within the $i$-th longer interval
- $\eta_{k,i}$: noise term, expected to be much larger than in equation (7)

## Timing of an individual order

$\tau \in [t_{k-1},\ t_k]$, Where :

- $\tau$: time at which an order is submitted or canceled
- $[t_{k-1},\ t_k]$: time interval in which the order book events arrive
- $e_\tau$: signed quantity that the order at time $\tau$ contributes to supply/demand

## Order in the same direction as the concurrent OFI

$\operatorname{sgn}(e_\tau) = \operatorname{sgn}(\mathrm{OFI}_k)$, Where :

- $\operatorname{sgn}(\cdot)$: sign function
- $e_\tau$: signed contribution of the order at time $\tau$ to supply/demand
- $\mathrm{OFI}_k$: order flow imbalance over $[t_{k-1}, t_k]$
- Meaning: the order reinforces the concurrent OFI and can affect the price

## Order against the concurrent OFI

$\operatorname{sgn}(e_\tau) = -\operatorname{sgn}(\mathrm{OFI}_k)$, Where :

- $\operatorname{sgn}(\cdot)$: sign function
- $e_\tau$: signed contribution of the order at time $\tau$ to supply/demand
- $\mathrm{OFI}_k$: order flow imbalance over $[t_{k-1}, t_k]$
- Meaning: the order is compensated by other orders and has an instantaneous impact of zero
