# Team Presentation Guide – Problems 3 & 4
### TET4185 Power Markets, Resources and Environment — Spring 2026

---

## PART 0: FOUNDATION — What you need to know before any of this makes sense

Before jumping into Problem 3 and 4, everyone needs to be comfortable with five core ideas. These are the building blocks that every single task in Problems 3 and 4 sits on top of.

---

### 0.1 The Merit Order — Why generators are dispatched in a specific order

The most fundamental concept in power markets: generators are ranked by their marginal cost (the cost to produce one more MWh), cheapest first. The cheapest generator runs first and fills as much demand as it can. Then the next cheapest picks up what's left. And so on until all demand is met.

The **last generator to be turned on** — the most expensive one actually running — sets the price for the whole system. This is called the **marginal generator** or **price-setting unit**.

In our Nordic system:
- Norwegian hydro is cheapest (27–77 €/MWh depending on the zone)
- Swedish nuclear is in the middle (~55–70 €/MWh)
- Danish thermal is most expensive (~93 €/MWh)
- Finnish generation sits between Sweden and Denmark (~59 €/MWh)

So in a normal situation, Norway produces as much cheap hydro as it can, Sweden fills the gap with nuclear, and Denmark only runs its expensive thermal plants if there's still demand left over. The Danish plant then sets the price for the whole system or at least for the connected zones.

**Zero-cost wind** (Problem 4) shifts this whole picture: when wind is available, it jumps to the front of the queue and pushes expensive generators out. This is called the **merit-order effect** — wind lowers average prices because it displaces high-cost units.

---

### 0.2 Nodal Prices — Why different locations can have different prices

In a perfectly connected network with no transmission limits, every location in the system would have the same electricity price: the marginal cost of the cheapest available generator that's running system-wide.

But transmission lines have **capacity limits**. If a cheap generator is in one location and demand is in another, but the line connecting them is full, the cheap power physically cannot get there. The expensive local generator must run instead. This creates a **price difference between locations** — the node with the cheap generator will have a low price, and the node that can't receive the cheap power will have a high price.

These location-specific prices are called **nodal prices** (or **locational marginal prices**). They are the mathematical dual variables of the power-balance constraints in the optimisation — in plain language, the nodal price at a location tells you: "if demand here increased by 1 MW, how much more would the total system cost?"

**Key insight:** Congestion creates price differences. No congestion → uniform prices. Lots of congestion → large price spreads.

---

### 0.3 Congestion Rents — Who profits from price differences?

When two zones have different prices because a line between them is congested, the **congestion rent** is the profit earned by whoever controls the rights to use that line.

The formula is simple:
> **Congestion Rent = Flow on the line × (Price at receiving end − Price at sending end)**

For example: if Norway (cheap side) prices at 62 €/MWh, Denmark (expensive side) at 93 €/MWh, and the line carries 600 MW — the congestion rent is 600 × (93 − 62) = **18,600 €/hour**.

In real markets, this money goes to the Transmission System Operators (TSOs) and is supposed to be reinvested in the grid. In our model, we calculate it as an indicator of how valuable a particular transmission corridor is.

---

### 0.4 ATC vs FBMC — Two ways to model the transmission network

This is the central comparison of Problem 3. There are two fundamentally different ways to model how power flows across borders.

**ATC (Available Transfer Capacity) — the simple pipe model**

Imagine each transmission corridor as a simple pipe with a fixed capacity. You can push up to X MW from zone A to zone B, and the market optimises trade within that limit. The model does NOT care about what happens physically inside the network — it has no concept of how power actually distributes itself through parallel paths.

The problem: in reality, if you send power from Norway to Denmark, some of that power will physically flow through Sweden even if that wasn't intended. ATC ignores this. The result is that ATC can produce dispatch solutions that look fine on paper but would physically overload lines that weren't supposed to carry that power.

**FBMC (Flow-Based Market Coupling) — the physics-based model**

FBMC uses the actual physics of electricity to figure out how power flows. It uses a matrix called the **PTDF matrix** (Power Transfer Distribution Factors) to calculate how every MW of generation anywhere in the network affects every line in the network.

PTDF tells you: "if zone Norway injects 1 extra MW, what fraction of that ends up flowing on each line?" Because electricity follows Kirchhoff's laws and distributes across all parallel paths according to their impedance (resistance), a trade between Norway and Denmark simultaneously affects lines in Sweden, Finland, and everywhere else. FBMC captures this; ATC doesn't.

**Practical consequence:**
- FBMC is more realistic but more restrictive — it might block a trade that ATC would allow, because it knows that trade would overload a third line
- ATC is simpler and often produces cheaper dispatch results *in the model*, but that dispatch may be physically impossible
- In real markets across Europe, FBMC has largely replaced ATC because grid operators need the physics to be respected

---

### 0.5 The PTDF Matrix — How FBMC knows where the power flows

The PTDF (Power Transfer Distribution Factor) is a number between -1 and +1 that tells you: "if zone n injects 1 MW more (net), what fraction appears on transmission line l?"

It is computed from the network's electrical properties (the susceptance matrix). The key formula is:

> **PTDF = B_f × B_bus⁻¹**

Where B_f is the line susceptance matrix and B_bus is the node susceptance matrix. You don't need to calculate this by hand — the Python script does it. But the key idea is: once you have the PTDF matrix, the flow on any line is just a weighted sum of all the zonal net injections:

> **Flow on line l = Σ (PTDF_{l,n} × NetInjection_n)**

This is why FBMC couples every generator dispatch decision to every line flow. You can't change output in one zone without affecting flows on lines far away.

---

### 0.6 The Nordic 12-Node Model — What system are we actually modelling?

The model represents the Nordic electricity system with 12 zones:
- **Norway**: NO1 (southeast), NO2 (southwest/central), NO3 (north-central), NO4 (far north), NO5 (west)
- **Sweden**: SE1 (north), SE2 (north-central), SE3 (south-central — this is where most Swedish nuclear sits), SE4 (south)
- **Denmark**: DK1 (Jutland/west), DK2 (islands/east)
- **Finland**: FI

SE1 (north Sweden) is the **reference node** — its phase angle is fixed at zero, which is required mathematically to make the PTDF calculation work. The choice of reference node doesn't affect prices or flows.

The system has both **AC transmission lines** (where flows follow physical laws and PTDF applies) and **HVDC links** (high-voltage direct current cables that are fully controllable — the operator decides exactly how much flows, regardless of physics).

The main HVDC links are:
- NO2→DK1 (connects southwest Norway to west Denmark)
- DK1↔DK2 (connects the two Danish zones)
- SE3→FI (connects Sweden to Finland)

The Python script (FBMC_pyomo.py) runs this entire model. Switch between FBMC and ATC by changing one parameter (DCFlow = 1 or 0). Switch between wet and dry year by changing the input Excel file.

---
---

## PROBLEM 3: Nordic System FBMC

**What this problem is about overall:** We take the 12-node Nordic model and run it under different scenarios to understand how the choice of market coupling method (FBMC vs ATC), seasonal conditions (wet vs dry hydro year), structural changes (nuclear phaseout), and policy instruments (carbon pricing) affect prices, dispatch, congestion, and system costs.

---

## Task 3-1: Getting Familiar With the Model

### What the task asks
Understand the Python model before running it. Specifically:
- (a) How does the model implement the two approximation methods? Where is the reference node set and why?
- (b) Write out the full mathematical formulation for both FBMC and ATC and explain the key difference

### The basic knowledge needed
You need to understand: what is an optimisation model (minimise cost subject to constraints), what are decision variables vs parameters, and the FBMC/ATC distinction from Section 0.4 above.

### Our solution and how we got there

**Part (a) — Reading the Python script**

The script uses a parameter called `DCFlow` (declared in the Excel Declarations sheet, read at line 63 of the script):
- `DCFlow = 1` → FBMC mode: uses PTDF sensitivities to compute AC flows
- `DCFlow = 0` → ATC mode: treats each AC flow as a free variable bounded only by bilateral capacity

The reference node is **SE1 (node 6)**. It is declared in the Declarations sheet and passed to the `Calculate_PTDF()` function at line 134. Inside that function, SE1's row and column are removed from the B matrix before inversion. This is mathematically necessary: the B matrix is singular (you can't invert it directly) because the absolute voltage angle doesn't matter — only differences between angles matter. By removing one node and fixing its angle to zero, you make the matrix invertible.

**Important:** the choice of reference node is completely arbitrary. Prices, flows, and dispatch are all identical regardless of which node you pick as the reference. SE1 was chosen by the script author, but it could have been any other node.

The objective function (shared by both methods) minimises total system cost:

> min Σ c_n · P_gen_n + c_shed · Σ P_shed_n

Where:
- c_n is the marginal generation cost at zone n (€/MWh)
- P_gen_n is the generation dispatch at zone n (MW)
- c_shed = 3200 €/MWh is the load-shedding penalty (the cost of not serving demand)
- P_shed_n is load shed at zone n

The 3200 €/MWh penalty is so high that the model will exhaust every available generator before allowing any load shedding. It represents the "value of lost load" — how much consumers are willing to pay to avoid a blackout.

**Part (b) — The mathematical formulations**

Both models share these constraints:

*Generator capacity bounds:*
> P_min_n ≤ P_gen_n ≤ P_max_n  for all zones n

*HVDC bounds:*
> −F_cap_h ≤ f_DC_h ≤ F_cap_h  for all HVDC links h

*Non-negativity of load shedding:*
> P_shed_n ≥ 0

**Where they differ — the AC transmission constraint:**

*FBMC:* Zonal net injection = generation − demand + shedding − HVDC exports. All net injections must sum to zero (global balance). AC flows are calculated via PTDF:
> f_AC_l = Σ PTDF_{l,n} × INJ_n  for all lines l
> −F_to_l ≤ f_AC_l ≤ F_from_l  (flow limits)

*ATC:* Each node has its own individual power balance:
> P_gen_n + P_shed_n = D_n + Σ X_{l,n} × f_AC_l + Σ ADC_{h,n} × f_DC_h

Where X_{l,n} is +1 or −1 depending on line orientation. Each AC flow is a free variable bounded only by thermal limits — there is no PTDF coupling. The model just checks that each individual corridor doesn't exceed its rated capacity.

**The bottom line of the difference:** In FBMC, sending 1 MW more through any line automatically changes flows on all other lines (captured by the PTDF). In ATC, each line is completely independent of every other line. This is why ATC can produce physically impossible dispatches in real meshed networks.

---

## Task 3-2: Analysing a Wet-Year Scenario

### What the task asks
Run the model with Norwegian/Swedish hydro at high capacity (wet year, Nordic_wet.xlsx). Compare FBMC and ATC results. Specifically:
- (a) Which method is more physically realistic and how does this affect the objective value?
- (b) Compare generation dispatch, nodal prices, transmission flows, and congestion rents between the two methods
- (c) Why does ATC produce a lower system cost despite being less accurate?

### The basic knowledge needed
The merit-order effect (0.1), nodal prices (0.2), congestion rents (0.3), FBMC vs ATC (0.4), and PTDF (0.5).

### Our solution and how we got there

**Part (a) — Which is more realistic?**

FBMC is more physically realistic because it uses PTDF sensitivities to distribute power across all parallel paths according to electrical impedance — exactly how real meshed AC grids behave. ATC treats each line as an independent bilateral pipe with no coupling between corridors.

The objective values: **FBMC costs 3,292,168 €; ATC costs 3,265,108 €** — a gap of 27,060 € (0.8%). ATC is cheaper, and the reason is important: ATC is *less constrained*. It doesn't enforce PTDF coupling, so its feasible region is larger. The optimiser can dispatch cheaper generators more freely. But that solution might physically overload lines the model didn't track. The FBMC premium of 27,060 € represents the **true cost of respecting network physics**.

**Part (b) — Generation, prices, flows, congestion rents**

*Generation differences:*

The biggest difference is at NO5 and NO2. Under ATC, the model dispatches NO5 (one of the cheapest zones at 63 €/MWh) at its full 6,500 MW capacity. Under FBMC, NO5 is limited to 4,949 MW because the NO5→NO2 corridor (600 MW limit) binds under PTDF physics. The model knows that pushing more power through NO5 would overload that corridor. The 1,551 MW shortfall shifts to NO2 (77 €/MWh), which rises from 5,912 to 8,227 MW. This is why FBMC costs more — it's forced to use a more expensive generator because the physics of the network limits how much cheap NO5 power can actually reach the deficit zones.

SE4 output also drops under FBMC (from 1,600 MW to 836 MW) because cheaper imports via SE3→SE4 can serve SE4 demand more efficiently once loop flows are captured.

*Nodal prices:*

Under ATC: near-uniform 77 €/MWh across almost all Scandinavian and Finnish zones (NO2 sets the price everywhere because it can dispatch freely without PTDF restrictions). DK1/DK2 separate at 93 €/MWh.

Under FBMC: internal congestion prevents full price equalisation. Norwegian zones range from 62.49 to 77.00 €/MWh, Swedish/Finnish zones cluster around 69–70 €/MWh, Denmark stays at 93 €/MWh. The fact that FBMC produces more differentiated prices is actually more realistic — it means the model is correctly identifying which zones are "trapped" behind congested corridors.

*Transmission flows and binding constraints:*

Under FBMC, five AC lines bind: NO4→SE1 (700 MW), NO3→NO1 (500 MW), NO5→NO2 (600 MW), SE4→DK2 (1,300 MW), and SE3→DK1 (680 MW). Plus two HVDC links: NO2→DK1 (1,632 MW) and DK1→DK2 (600 MW).

Under ATC, seven AC lines bind, most notably NO5→NO1 at 3,900 MW — a flow that FBMC would prohibit because it would simultaneously overload the parallel NO5→NO2 corridor. ATC routes 3,900 MW on NO5→NO1 while NO2→NO1 flows in reverse at −1,320 MW. FBMC identifies this as a NO5→NO2 violation and forces 2,315 MW to shift from cheap NO5 to expensive NO2 — this single decision directly explains the 27,060 € cost gap.

*Congestion rents:*

FBMC total congestion rent: 107,258 € — nearly double the ATC figure of 57,792 €. Under ATC, rents only appear on Danish interconnectors (since all other zones price at 77 €/MWh, there's zero price differential between Norwegian and Swedish zones to generate rent). FBMC generates additional rents on internal Norwegian lines due to price differentiation. The highest shadow price is on NO5→NO2 at 30.96 €/MW, with SE4→DK2 and SE3→DK1 each at 23.00 €/MW.

**Part (c) — Why does ATC produce a lower cost despite being less realistic?**

Three reasons, and this is an important conceptual point:

1. *Modelling assumptions:* In real life, FBMC's advantage over ATC comes from TSOs setting ATC limits conservatively to guard against loop flows. When FBMC is then applied, it reveals additional capacity that was being left unused under conservative ATC limits. In our model, both methods use identical line ratings. ATC is never penalised by conservative margins, so that advantage for FBMC never materialises.

2. *Network representation:* With single-node zones, PTDF values are exact. The 12-node topology also lacks the dense parallel-path structure of real-world meshed networks where loop-flow effects — and thus FBMC's advantage — are most pronounced.

3. *Constraint structure:* PTDF coupling restricts dispatch combinations that would overload parallel paths. ATC's independent line flows face no such coupling, so its feasible region is strictly larger. A larger feasible region always means a lower or equal optimum cost.

**Conclusion:** The results don't contradict theory. Identical capacity limits, single-node zones, and absent NTC conservatism collectively remove the conditions under which FBMC's advantages normally materialise over ATC.

---

## Task 3-3: Dry-Year Scenario Comparison

### What the task asks
Switch to the dry-year input file (Nordic_dry.xlsx). Norwegian hydro inflow is much lower, meaning hydro capacity is sharply reduced. Compare results against the wet year under both FBMC and ATC:
- (a) How do generation and prices change?
- (b) How do AC line flows and congestion patterns change?
- (c) Compare the two years directly — what does this tell us about interconnection?

### The basic knowledge needed
Same as Task 3-2, plus an understanding of why hydro scarcity translates into higher prices (the merit order shifts when cheap capacity disappears).

### Our solution and how we got there

**Part (a) — Generation and prices in the dry year**

Total system cost rises dramatically: **5,062,341 € under FBMC and 5,056,200 € under ATC** — roughly 54% above the wet-year FBMC figure. The reason is straightforward: cheap Norwegian hydro is no longer available in the same quantities, so the system must run more expensive generators.

Nine of twelve zones produce at full capacity under FBMC: NO4, NO5, NO2, NO1, SE1, SE2, SE3, SE4, and FI. The cheap wet-year surplus has largely vanished — NO5's capacity falls from 6,500 to 3,400 MW against unchanged 2,600 MW demand. Only NO3 retains marginal spare capacity (3,229 of 3,300 MW), constrained by the binding NO3→NO1 line (500 MW). DK1 and DK2 have headroom as power now flows *into* Denmark via the reversed NO2→DK1 HVDC link (in the wet year, Norway was exporting to Denmark; now Denmark exports back to Norway).

*Nodal prices under FBMC:* Several distinct price clusters emerge:
- **NO3 at 78 €/MWh** — the only zone below full capacity, so its own marginal cost sets the local price
- **NO4 at 85.27 €/MWh** — at full capacity, congested export lines price it above its own 52 €/MWh marginal cost
- **SE1 (92.44), SE2 (94.35), SE3/SE4/FI (97.83 €/MWh)** — all at full capacity, priced by the cost of importing the marginal MW through the congested AC network
- **NO5, NO2, NO1, DK1 at 114 €/MWh** — expensive Danish thermal generation sets the marginal price for this connected cluster
- **DK2 at 108 €/MWh** — isolated from the 114 €/MWh cluster by the binding SE4→DK2 line

*Under ATC:* A single uniform price of 114 €/MWh across all twelve zones. No binding constraint separates any zone from any other.

Prices are substantially higher than the wet year (FBMC: 62–93 €/MWh in wet, 78–114 €/MWh in dry).

**Part (b) — Flow pattern changes in the dry year**

Under FBMC, four AC lines bind: NO3→NO1 (500 MW), SE1→FI (1,500 MW), SE4→DK2 (1,300 MW), and SE3→DK1 (680 MW) — fewer than the wet year's five, because reduced Norwegian surplus releases the NO4→SE1 and NO5→NO2 corridors (which were congested in the wet year because Norway was pushing surplus power southward).

The most notable flow reversals in the dry year:
- **NO2→DK1 HVDC reverses:** wet-year export of 1,632 MW flips to −651 MW (Denmark now exports to Norway)
- **NO1→SE3 reverses:** a modest 144 MW wet-year flow becomes −1,149 MW (SE3 now exports heavily toward NO1 to compensate for reduced Norwegian hydro)
- **NO5→NO2 reverses:** wet-year +600 MW surplus flow becomes −101 MW (NO5 has lost its excess capacity)
- **SE2→SE3 remains dominant:** flow eases from 7,285 to 6,629 MW but stays the largest single flow in the system

Congestion rents: ATC generates zero congestion rent in the dry year because all zones price uniformly at 114 €/MWh — no price differential means no rent. Under FBMC, total rent is 87,972 €, below the wet-year 107,258 € despite higher absolute prices. The reason: the wet year's large spread between cheap Norwegian zones (62–63 €/MWh) and Denmark (93 €/MWh) has compressed in the dry year (Norwegian zones now at 78–114 €/MWh), and fewer AC lines are saturated. SE2→SE3 and NO1→SE3 now dominate the rent distribution.

**Part (c) — Wet vs dry comparison and the role of interconnection**

Norway completely reverses its position in the system. In the wet year, Norwegian generation is 24,676 MW against 21,600 MW demand (+3,076 MW net export position). In the dry year, generation falls to 19,729 MW against unchanged 21,600 MW demand (−1,871 MW, a net import position). This swing of nearly 5,000 MW is absorbed by increased Swedish exports (+2,664 MW) and reduced Danish import needs (as the HVDC reverses).

**Interconnection matters enormously but in opposite directions in each year:**

*Wet year:* Norway has 3,076 MW of surplus it physically cannot absorb domestically. Without interconnectors, cheap hydro would be curtailed (wasted) while neighbouring countries continue burning expensive thermal generation. Cross-border capacity converts this surplus into exports, earns congestion rent revenue, and lowers prices across Scandinavia.

*Dry year:* Norway's 1,871 MW deficit requires imports for supply security. Without interconnectors, load shedding at 3,200 €/MWh would be unavoidable. The reversed NO2→DK1 flow (−651 MW) and the SE3→NO1 import (−1,149 MW) demonstrate interconnectors functioning as a security-of-supply lifeline.

Norway's 49% average price increase (from 63 to 94 €/MWh), far exceeding any other country, underscores this asymmetry: a hydro-dominated system is uniquely exposed to precipitation variation, and without strong interconnection the seasonal price volatility would be even more extreme.

---

## Task 3-4: Phasing Out Baseload Production

### What the task asks
Remove Sweden's nuclear capacity from the model (SE3 loses 8,400 MW of nuclear). This simulates a political decision to phase out nuclear power, similar to what Germany did in 2023. Analyse:
- (a) How does total system cost change and why?
- (b) Which generators compensate for the lost nuclear?
- (c) How do zonal prices change — who suffers most?
- (d) What policies would need to precede such a phaseout to avoid these outcomes?

### The basic knowledge needed
Load shedding / value of lost load (why 3,200 €/MWh appears as a price), transmission bottlenecks preventing power from reaching deficit zones even when surplus exists elsewhere, and how nodal prices spike when the marginal resource becomes load shedding.

### Our solution and how we got there

**Part (a) — Cost impact**

Total system cost rises from 3.29 to **12.45 million €, an increase of 9.16 million € (+278%).** The increase is almost entirely driven by load shedding — not from the electricity generation cost itself changing, but from demand that physically cannot be served.

Here's why this happens: the base case (wet year FBMC) has **zero reserve margin** — total available capacity (60,600 MW) exactly equals total demand (60,600 MW). Removing 8,400 MW of nuclear from SE3 leaves 52,200 MW of capacity against 60,600 MW of demand. Even with every remaining generator running at full output, there is a system-wide shortfall of 8,400 MW. Some zones physically cannot receive power because of transmission bottlenecks (explained below), so the actual load shedding is 2,862 MW — smaller than 8,400 MW because some zones that were previously running below their limits pick up more output. But 2,862 MW × 3,200 €/MWh ≈ 9.16 million €, which is virtually the entire cost increase.

**Part (b) — How does the system try to compensate?**

The system responds by ramping up every other available generator:
- **NO2 provides the largest increase** (+1,678 MW, to 9,905 MW — near its 10,000 MW cap). NO2 has the most spare capacity and pushes power via NO2→NO1→SE3. The NO1→SE3 flow rises from 144 to 2,145 MW, hitting its limit.
- **Denmark (DK1, DK2)** increases by +1,420 and +1,200 MW. Previously a net importer, Denmark now ramps expensive thermal generation (93 €/MWh) to export toward Sweden. The SE3→DK1 line reverses from +680 to −740 MW (now flowing from Denmark toward Sweden).
- **Western Norway (NO5)** increases by +739 MW. NO5→NO1 rises from 1,749 to 2,488 MW.
- **SE4 reaches full capacity** (+764 MW, to 1,600 MW), but this is still far below SE4's own 4,000 MW demand.

Counterintuitively, NO4 and NO3 decrease slightly (−231 and −33 MW): the PTDF constraints mean increasing output there would overload parallel paths, so the optimiser shifts generation to zones with better electrical connectivity to the SE3 deficit.

Despite this system-wide response, **2,862 MW goes unserved** at SE4 (2,400 MW), FI (362 MW), and DK2 (100 MW). All three are electrically downstream of the SE3 bottleneck — once SE3 stops exporting, these zones cannot receive enough imports through the congested network.

**Part (c) — Price impacts**

The phaseout **splits the system into two sharply separated price zones:**

*Shedding-price zones (3,200 €/MWh):* SE3, SE4, FI, DK2, and SE1 rise to the load-shedding penalty. SE2 reaches 3,104 €/MWh (slightly below due to PTDF coupling with Norwegian zones). Even SE1 and SE2, which don't shed any load themselves, price near 3,200 €/MWh because an additional MW of demand there would increase flows toward SE4 or FI, triggering more shedding at the penalty price.

*Norwegian and DK1 zones (27–93 €/MWh):* Norwegian prices stay low or even fall. NO4 drops from 62.49 to 27 €/MWh, NO3 from 63.74 to 38 €/MWh, NO5/NO2/NO1 are unchanged. DK1 stays at 93 €/MWh. These zones are separated from the shedding cluster by saturated constraints (NO1→SE3 and NO4→SE1 both bind), so marginal Norwegian demand is served by cheap local generation rather than triggering further Swedish shedding.

*Who is hit hardest:* SE4 consumers face 3,200 €/MWh, a 45-fold increase from the base 70 €/MWh. 60% of SE4's demand (2,400 of 4,000 MW) goes unserved entirely. Finnish consumers also face 362 MW unserved at the shedding price. Norwegian consumers are shielded almost entirely.

**Part (d) — What policies would need to precede a phaseout?**

Three preconditions matter most:

New capacity must be located near the deficit zone, not just added to the system generally. Total system capacity falls below demand after the phaseout, making shedding inevitable regardless of network configuration. Norwegian and Danish surplus cannot substitute because the NO1→SE3 and SE3→SE4 corridors saturate before enough power reaches SE4 and Finland. New capacity (wind, solar, or gas) therefore needs to be built in or near SE3 specifically.

Transmission reinforcement and a gradual phaseout schedule are equally important. Expanding NO1→SE3, SE3→SE4, and the SE3→FI HVDC would allow existing surplus to reach the deficit zones — the base-case shadow prices already flag these corridors as the highest-value bottlenecks. Spreading retirements over several years generates incremental price signals that pull forward replacement investment before each step.

Finally, demand-side flexibility and Nordic TSO coordination are needed to manage residual risk. All demand in the model is inelastic, so shortfalls translate directly into involuntary shedding at 3,200 €/MWh. Interruptible contracts in SE4 and Finland would achieve voluntary reductions at far lower cost. And because Finnish consumers face shedding solely through import dependence on SE3, agreed reserve-sharing between Nordic TSOs is essential.

---

## Task 3-5: Environmental Constraint

### What the task asks
Apply a carbon price to the Nordic model using real EU ETS emission intensities. Specifically:
- (a) Look up real emission intensities for each zone and calculate which zones emit the most
- (b) Explain the history of EU ETS prices and forecast where they're heading
- (c) Predict qualitatively what a 65 €/tCO₂ carbon price would do to the merit order and dispatch
- (d) Discuss long-term trends for the Nordic system as carbon prices rise toward 2050
- (e) Actually run the model with the carbon price and check whether the results match the predictions

### The basic knowledge needed
How carbon pricing works (adding emission cost to marginal cost), the EU ETS structure (cap-and-trade), and how carbon prices change the merit order.

### Our solution and how we got there

**Part (a) — Emission intensities**

Emission intensity values were taken from Electricity Maps at 12:00 CET on 27 March 2026 (gCO₂/kWh):
- Norwegian zones: ~9.7 gCO₂/kWh (almost entirely lifecycle emissions from hydro infrastructure)
- Swedish zones: ~15 gCO₂/kWh (nuclear and hydro mix — lowest intensity in the system)
- Finnish zones: ~95 gCO₂/kWh (gas, peat, and biomass CHP — highest intensity)
- DK1: ~155 gCO₂/kWh (highest intensity — coal and gas thermal)
- DK2: ~120 gCO₂/kWh

**Key insight about absolute emissions vs intensity:** Finland emits 931 tCO₂/h (44% of the system total) despite producing only 16% of generation — because its intensity is high AND it produces a lot. SE3 has the lowest intensity (15 gCO₂/kWh) but still ranks third in absolute emissions (186 tCO₂/h) purely because it is the largest generating zone in the system (12,400 MW). The ranking of emitters is about both intensity and volume.

**Part (b) — EU ETS history**

The EU ETS (Emissions Trading System) is a cap-and-trade mechanism — the regulator sets a total cap on emissions, issues allowances equal to the cap, and lets the market trade them. The price of an allowance is determined by supply and demand. It has gone through four phases:

- **Phase 1 (2005–2007):** Over-allocated — prices briefly hit ~30 €, then collapsed near zero when the surplus was discovered and banking was prohibited
- **Phase 2 (2008–2012):** Financial crisis suppressed industrial output and emissions. Prices averaged ~15 €/tCO₂, large surplus accumulated
- **Phase 3 (2013–2020):** Prices depressed at 5–8 €/tCO₂ until the Market Stability Reserve (MSR — a mechanism to automatically absorb surplus allowances) began working in 2019, driving prices from ~8 € to ~35 €/tCO₂ by end-2020
- **Phase 4 (2021–present):** Prices surged above 95 €/tCO₂ in early 2023 (driven by tightened cap, continued MSR absorption, and the energy crisis after Russia's invasion of Ukraine). Prices have since moderated to 65–75 €/tCO₂

**Forecast to 2050:** The trajectory points to sustained increase: 65–85 €/tCO₂ in 2026–2027, 100–150 € by 2030, 150–300 € by 2040–2050. The drivers are: a linear reduction factor rising to 4.3% per year after 2024, phase-out of free allowances by 2034, and the Carbon Border Adjustment Mechanism (CBAM) which extends carbon costs to imports.

**Part (c) — Predicted effects of 65 €/tCO₂ carbon price**

Adding a carbon cost to each zone's marginal cost:

> c_new_n = c_n + emission_intensity_n × carbon_price

The cost adders are highly asymmetric:
- Norwegian and Swedish zones: +0.97 to +1.69 €/MWh (barely affected)
- Finland: +6.18 €/MWh (overtakes NO5 at 64.24 €/MWh with its new 65.18 €/MWh)
- DK2: +7.80 €/MWh (rises to 100.80 €/MWh)
- DK1: +10.08 €/MWh (rises to 103.08 €/MWh — most expensive in the system)

Predicted effects: DK1 and DK2 become even less competitive, likely reducing local output. Finland becomes slightly less competitive relative to Norwegian hydro. Danish generation, already the most expensive, becomes even more so, increasing import incentives.

**Part (e) — Actual results (running the model)**

The result was partly surprising:

1. **The Danish swap:** All ten Scandinavian and Finnish zones dispatch identically to the base case. Only Denmark changes: DK1 falls from 1,488 to 288 MW while DK2 rises from 300 to 1,500 MW. Why? In the base case, DK1 and DK2 both cost 93 €/MWh and were interchangeable. After the carbon adder, DK1 (155 gCO₂/kWh) reaches 103.08 €/MWh while DK2 (120 gCO₂/kWh) only reaches 100.80 €/MWh. The optimiser substitutes DK1 with DK2. The DK1↔DK2 HVDC reverses from +600 to −600 MW.

2. **AC flows unchanged:** All fifteen AC flows are identical to the base case. Since the AC network reaches Denmark only through SE4→DK2 and SE3→DK1, and the total Danish net position seen by the AC network is unchanged, the five binding constraints from Task 3-2 remain the same.

3. **Zonal prices:** Each zone's price increases by approximately its local carbon adder. Norwegian zones +0.07–1.43 €/MWh; Swedish and Finnish ~+1 €/MWh; Denmark +7.80–10.08 €/MWh.

4. **System cost and emissions:** Total cost rises by 134,037 € (+4.1%). Emissions fall by only 42 tCO₂/h (−2.0%). The 65 €/tCO₂ price is insufficient to displace Finnish or other thermal generation — the merit-order change is confined to the intra-Danish swap.

5. **The surprise:** The DK1↔DK2 swap was not predicted in part (c). Both Danish zones were interchangeable at 93 €/MWh before the carbon price. The carbon price breaks this symmetry by penalising DK1 more heavily, creating an intra-country differential that didn't exist before. This demonstrates that carbon pricing can split zones that were previously identical, and that HVDC links are essential for enabling the resulting re-optimisation.

---
---

## PROBLEM 4: Wind Integration and Price Spikes

**What this problem is about overall:** We add large-scale wind power to the Nordic wet-year model and study two consequences: (1) how wind changes prices, dispatch, flows, and congestion when it's available; and (2) what happens to prices when demand spikes or wind disappears — why electricity prices can jump from 55 €/MWh to 3,200 €/MWh in a matter of hours.

---

## Task 4-1: Wind Integration in the Base (Wet-Year) Case

### What the task asks
Add 19,100 MW of wind capacity distributed across the 12 zones. Run the model and analyse how wind changes dispatch, prices, flows, and congestion rents compared to the base case (Task 3-2 FBMC).

### The basic knowledge needed
The merit-order effect from Section 0.1, plus the concept that wind has zero marginal cost (fuel is free) so it always runs first and pushes expensive generators out of the merit order.

### Modelling approach

Wind is modelled as a reduction in net demand rather than an extra generator:

> D_net_n = D_n − W_n

Where W_n is installed wind capacity at zone n. At zero marginal cost, wind is always dispatched first regardless of how you model it — treating it as negative demand vs. a zero-cost generator gives identical results. Using demand reduction is simpler and avoids adding new decision variables.

Total wind capacity is 19,100 MW. DK1 and DK2 wind exactly matches their total demand, leaving zero net demand in both Danish zones.

### Our solution and how we got there

**Generation and the merit-order effect:**

Wind displaces 19,100 MW of conventional generation. Total conventional output falls from 60,600 to 41,500 MW. The largest reductions are at the most expensive units: SE3 (−5,394 MW), NO2 (−5,310 MW), and FI (−3,300 MW). Danish conventional generation is eliminated entirely — wind covers all Danish demand.

This is the merit-order effect in action: zero-cost wind shifts the supply curve rightward, so the same demand level is now met by cheaper units. In the base case, SE4 (70 €/MWh) was marginal in the Nordic/Swedish cluster. With wind, SE3 (55 €/MWh) becomes marginal in several zones, and NO4/NO3 fall to their own marginal costs (27 and 38 €/MWh) because reduced net demand removes the need for congestion-elevated export pricing.

**Price effects:**

Demand-weighted average price drops from 71.92 to 58.24 €/MWh (−19%). The largest decreases:
- DK2: −38 €/MWh (Danish thermal was the price-setter; wind eliminates the need for it)
- NO4: −35.49 €/MWh (falls to its own 27 €/MWh marginal cost)
- SE1: −27.45 €/MWh

Total system cost falls by **1,223,498 € (−37.2%)**, from 3.29 to 2.07 million €.

**Flow changes:**

The key changes reflect the reversal of Denmark from net importer to net exporter:
- NO2→DK1 HVDC **reverses** from +1,632 to −1,280 MW. With Danish demand fully covered by wind, the link now exports Danish surplus back toward Norway.
- NO1→SE3 **reverses** from +144 to −426 MW. Reduced Swedish net demand eliminates the need for Norwegian imports.
- SE3→SE4 **halves** from 4,464 to 2,100 MW — SE4's own 2,000 MW wind covers half its demand locally.
- SE3→FI HVDC **increases** from 585 to 1,200 MW (binding) — cheap Swedish power pushes toward Finland.

**Congestion:**

Three new binding constraints appear: NO4→NO3 (1,200 MW), SE1→FI (1,500 MW), and SE2→SE3 (7,300 MW). Wind relieves north-to-south export corridors (NO4→SE1 goes from binding at 700 MW to 500 MW, non-binding) but creates new bottlenecks on Finnish feed lines and internal Swedish lines.

Total congestion rent **rises from 107,258 to 195,798 € (+83%)** despite lower average prices. Wind widens zonal price differentials — prices now range from 27 to 77 €/MWh versus the tighter 69–77 €/MWh base-case cluster. SE2→SE3 alone generates 60,590 €, driven by an 8.3 €/MWh spread across 7,300 MW.

**The key insight — lower average prices but higher volatility:**

Wind reduces average prices when it's blowing. But it also creates more spatial variation in prices (more congestion, more price differentials between zones). During low-wind periods, the system reverts to conventional dispatch at higher prices. This combination — lower mean, higher variance — is a well-documented consequence of large-scale wind integration. It is exactly why batteries, interconnection, and demand flexibility become more important as wind penetration grows.

---

## Task 4-2: Price Spikes from Peak Demand

### What the task asks
Take the wind base case from Task 4-1 and increase demand. Start with +10% and +20% demand increases at DK2 and SE4 (the zones most exposed to supply constraints). Then run a +30% system-wide stress test. Why do small demand increases sometimes cause enormous price spikes while other times prices don't move at all?

### The basic knowledge needed
The concept of the residual supply curve — the supply curve seen by the market after wind has already been dispatched. The key insight is that this curve is not smooth: it has a flat section (lots of spare cheap capacity), then a steep section (only expensive capacity left), then a vertical section (all capacity exhausted, load shedding begins). Small demand increases in the flat section have no price effect. The same demand increase at the boundary between flat and steep can cause huge price jumps.

### Our solution and how we got there

**Scenarios A (+10% DK2 and SE4) and B (+20% DK2 and SE4):**

Surprisingly, **neither scenario produces any price change whatsoever.** Prices remain at the wind-base-case level of 55 €/MWh across the Swedish/Finnish/DK2 cluster. Why?

In the wind base case, SE3 dispatches only 7,006 MW of its 12,400 MW capacity — it has approximately **5,400 MW of spare capacity.** SE3 is the marginal generator (price-setter), and the corridors from SE3 to SE4 and DK2 are uncongested. The additional demand in Scenarios A and B (+620 MW and +1,240 MW respectively) is absorbed entirely by SE3 at its existing 55 €/MWh marginal cost. No generator reaches its limit, no transmission line saturates, and the marginal resource does not change. Total cost rises linearly (55 × ΔD €/MW) with no price spike. This is the **flat region of the residual supply curve.**

**When do prices actually start to move?**

The model was tested to identify the threshold. At approximately +80% demand at DK2 and SE4: SE3 output approaches 10,106 MW and SE3→SE4 approaches capacity. SE4 rises from 55 to 70 €/MWh and DK2 to 77 €/MWh — the first price movements, marking the transition to the steep portion of the supply curve.

**The +30% system-wide stress test:**

At +30% system-wide demand, SE3 hits its 12,400 MW cap. SE1→FI saturates, forcing **150 MW of Finnish shedding at 3,200 €/MWh.** Finland spikes to 3,200 €/MWh. Most other zones rise to ~73 €/MWh.

**The three regimes of the residual supply curve:**

This is the central conceptual lesson of the task:

1. **Flat region:** SE3 has ~5,400 MW of spare capacity. Adding demand in this region has zero price effect — cost rises linearly at 55 €/MWh. Scenarios A and B stay here.

2. **Steep region:** SE3 is exhausted. The marginal unit jumps to SE4 (70 €/MWh) or NO1 (67 €/MWh) — a 12–17 €/MWh jump triggered by a single marginal MW.

3. **Vertical (scarcity) region:** Total capacity exhausted. Price rises discontinuously to the Value of Lost Load (3,200 €/MWh). The +30% scenario hits this region for Finland due to the saturated SE1→FI interconnector.

**Why transmission constraints amplify this nonlinearity:**

Finland reaches shedding prices in the +30% scenario not because of a system-wide capacity shortage, but because SE1→FI (1,500 MW) and SE3→FI HVDC (1,200 MW) are both simultaneously saturated. Finland is physically cut off from additional imports even though there is still spare capacity elsewhere in the system. The combination of a steep residual supply curve and congested interconnectors produces the extreme price spikes characteristic of scarcity pricing.

---

## Task 4-3: Price Spikes from Supply Scarcity

### What the task asks
Explore price spikes from the supply side rather than the demand side. Progressively reduce wind from full capacity to 25% to zero. Then add a compound scarcity: zero wind + 30% reduction in Norwegian hydro. This simulates a "dark, still winter" — the worst-case scenario for a renewable-heavy Nordic system.

### The basic knowledge needed
How the merit-order effect works in reverse: removing zero-cost wind means the system must re-dispatch to more expensive conventional generators, raising prices. And how compound scarcity (both wind and hydro low simultaneously) can drive prices to the shedding level even without a demand spike.

### Our solution and how we got there

**Progressive wind reduction — prices:**

- **Full wind → 25% wind:** Demand-weighted average rises from 58.24 to 63.78 €/MWh (+9.5%). FI (59 €/MWh) becomes marginal in the eastern cluster; DK1/DK2 jump to 93 €/MWh as Danish thermal must ramp up to fill the gap; NO4 rises from 27 to 41 €/MWh as demand for Norwegian hydro increases.

- **25% wind → no wind:** Average rises to 71.92 €/MWh (+23.5% vs. full wind). This is identical to the Task 3-2 base case — removing all wind returns the system exactly to its pre-wind dispatch, as expected.

- **Compound scarcity (no wind + hydro −30%):** All twelve zones spike to **3,200 €/MWh**. Total conventional capacity (59,700 MW after hydro reduction) falls below total demand (60,600 MW), forcing 900 MW of shedding at SE4. The shedding price propagates to every zone because no transmission constraint creates any price separation — when every zone is priced at the shedding level, there is no price differential across any line.

**Congestion pattern shifts:**

As wind decreases, congestion reverts toward the base-case structure: NO4→SE1 returns to binding (700 MW); SE3→FI HVDC falls from 1,200 MW (binding at full wind) to 585 MW (non-binding); NO2→DK1 HVDC reverses from −1,280 back to +1,632 MW, restoring normal Norway-to-Denmark export flow.

**Congestion rents and the paradox:**

In the compound scarcity scenario, all zones share 3,200 €/MWh, so every price differential is zero and total congestion rent is approximately zero — the exact opposite of the full-wind case (195,798 €). The most extreme scarcity paradoxically produces zero rent. This makes sense: rent is earned from price differences between zones. When everyone prices at 3,200 €/MWh, there are no differences to earn from.

**Where prices spike the most:**

In the wind-reduction scenarios, Denmark sees the largest swings: DK1/DK2 rise from 55–77 €/MWh (full wind) to 93 €/MWh (no wind), a swing of 16–38 €/MWh. Danish thermal had been priced out of the market entirely by zero-cost wind; when wind disappears, it rushes back in at its full 93 €/MWh cost. In the compound scenario, SE4 bears the physical impact (900 MW unserved), but the shedding price propagates through the PTDF-coupled network to all twelve zones.

**Do interconnectors mitigate or amplify scarcity?**

Both, and this tension is fundamental to the energy transition:

*Mitigating physical scarcity:* SE3→SE4 delivers 4,300 MW of imports, reducing SE4's potential 2,400 MW shortfall to 900 MW. Finland avoids shedding entirely through SE1→FI and SE3→FI imports. Interconnectors reduce total shedding volume.

*Amplifying price exposure:* Interconnectors simultaneously spread the 3,200 €/MWh scarcity price to all twelve zones. Without interconnection, only SE4 would face shedding prices — the other eleven zones would continue pricing normally. With interconnection, the entire system prices at 3,200 €/MWh. Interconnectors mitigate physical scarcity while amplifying price exposure.

**The big-picture lesson:**

The spread between full-wind conditions (NO4 at 27 €/MWh) and compound scarcity (3,200 €/MWh system-wide) — a factor of 118x — defines the price volatility introduced by variable renewable integration. Each MW of wind lost is replaced by the next unit in the merit order: at 25% wind, the marginal generator shifts from SE3 (55 €/MWh) to FI (59 €/MWh). At zero wind, SE4 (70 €/MWh) returns as marginal. This progression is smooth — but compound scarcity creates a discontinuity where the system falls off the supply curve entirely.

Managing this volatility — through storage (batteries, pumped hydro), demand response (interruptible loads, smart pricing), and interconnection — is one of the central challenges of the energy transition. The Nordic system, with its unique combination of abundant hydro flexibility and growing wind capacity, is simultaneously one of the most resilient and most exposed systems in Europe. The hydro acts as a giant battery that smooths variability; but in dry years with low wind, that battery can run empty very quickly.

---

## Quick-Reference Summary Table

| Task | Core question | Key result |
|------|--------------|------------|
| 3-1 | What is FBMC vs ATC mathematically? | FBMC uses PTDF physics; ATC treats lines as independent pipes |
| 3-2 | Wet year: how do the two methods compare? | FBMC costs 0.8% more but is physically realistic; ATC is cheaper because less constrained |
| 3-3 | Dry year: what changes when hydro is scarce? | Norway flips from net exporter to importer; prices rise 49%; interconnectors become a lifeline |
| 3-4 | What happens if Sweden phases out nuclear? | +278% cost increase; 2,862 MW of load shedding; SE4/FI face 3,200 €/MWh; Norway unaffected |
| 3-5 | What does a carbon price do to the Nordic system? | At 65 €/tCO₂: only the Danish intra-zone swap changes; emissions fall just 2% |
| 4-1 | What does large-scale wind do to the market? | −37% cost, −19% average price, +83% congestion rents; lower mean, higher spatial variance |
| 4-2 | Why do small demand increases cause huge price spikes? | Residual supply curve has three regimes: flat → steep → vertical; scarcity is nonlinear |
| 4-3 | What happens when both wind and hydro are low? | Compound scarcity → 3,200 €/MWh system-wide; interconnectors reduce physical shedding but spread the price spike everywhere |
