# Decision methodology

Every output of SIGNALFORGE is labelled as exactly one of the following.

| Type | Question answered | Evidence needed | Wording |
|---|---|---|---|
| **Descriptive** | What happened? | Validated data and a documented metric | "Late deliveries were X% in period Y" |
| **Predictive** | What is likely to happen? | Model with a baseline, time-aware validation, uncertainty | "The model estimates..., error is..." |
| **Prescriptive** | What should we do? | Descriptive and predictive inputs plus stated assumptions and trade-offs | "We recommend... because... assuming..." |
| **Causal** | What would change if we intervene? | Experiment or a defensible causal design | Never inferred from correlation alone |

## Rules

1. **Correlation is not causation.** Observational findings are described as associations. A claim like "faster delivery raises reviews" needs a causal design, or is phrased as an association.
2. **Forecasts carry uncertainty and a baseline.** A model is reported against a simple baseline (for example last period or the mean), on a held-out later time window, never on training data.
3. **Prevent leakage.** Features may only use information available at prediction time.
4. **Assumptions are first-class.** Each recommendation lists its assumptions, the data it relies on, and what would invalidate it.
5. **Scenarios are not forecasts.** "If X changes by 10%" is a what-if under stated assumptions, not a prediction.
6. **Say what is unknown.** Missing cost or revenue data is stated, not approximated silently.

## Recommendation record (planned format)

```text
decision:      <what to do>
evidence:      <metrics and models, with versions>
type:          descriptive | predictive | prescriptive | causal
assumptions:   <list>
risks:         <list>
invalidated_if:<conditions>
```
