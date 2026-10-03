# P2-03 Research V2 Protocol Amendment 001

- **Amendment ID:** `P2_03_RESEARCH_V2_PROTOCOL_AMENDMENT_001`
- **Status:** `AWAITING_OWNER_APPROVAL`
- **Scope:** Initialization semantics only
- **Effective protocol:** Original frozen protocol plus this amendment, after Owner approval

## 1. Original protocol identity

- Original protocol: `docs/P2_03_RESEARCH_V2_PRE_REGISTRATION.md`
- Original protocol version: `P2-03-RESEARCH-V2-PRE-REGISTRATION-1.0`
- Original protocol SHA-256: `0ab04d326962a48439f0a762f5967d0268d8137fae6e26e07db5c7ca39c55290`
- Original frozen manifest: `.tmp/p203-v2-protocol/protocol_manifest.json`
- Original frozen manifest SHA-256: `9fbfd8cfe02bd47ace7893161bb6a5c1b6e9cba8639c6063c174cd91ef018ffb`
- Original manifest status: `FORMALLY_APPROVED_FROZEN_NOT_EXECUTED`

The original protocol and its manifest remain immutable historical records. This amendment does not replace either file or alter any recorded source-evidence hash.

## 2. Conflict and implementation evidence

Section 6 of the original protocol (`docs/P2_03_RESEARCH_V2_PRE_REGISTRATION.md:84`) says to keep the V1 algorithm and settings unchanged and includes the phrase “zero initialization.” Read literally as applying to every coefficient, that conflicts with the requirement to preserve the actual V1 initialization.

The actual V1 fit path is `scripts/p203_historical_research_replay.py:_fit` (`lines 143–178`). It counts positive and negative labels from the current training rows and initializes the coefficient vector at line 165 as:

```python
weights = [math.log((positives + 0.5) / (negatives + 0.5))] + [0.0] * feature_count
```

Thus the intercept starts at the smoothed training-label log-odds, while every feature coefficient starts at zero. The frozen wording is ambiguous if “zero initialization” is applied to the intercept as well.

## 3. Owner adjudication and corrected initialization contract

The Project Owner's supplied adjudication is that V2 preserves the actual V1 logistic initialization:

```text
P2_03_HISTORICAL_RESEARCH_LOGISTIC_V2 INITIALIZATION CONTRACT

Intercept:
Initialize from the same smoothed training-label log-odds rule as V1:
log((positive_count + 0.5) / (negative_count + 0.5))

Feature weights:
Initialize every feature coefficient to zero.

Interpretation:
The original generic phrase “zero initialization” applies to feature weights only;
it does not apply to the intercept.
```

The counts are calculated from the eligible, matured, prior training rows used for the individual forecast, under the original chronological expanding-training contract. No alternate initialization scheme is introduced.

## 4. Scope limitation

This erratum resolves the initialization wording conflict only. It does not change the feature set or formulas, target, direction, horizon, eligibility, training rules, normalization, model family, optimizer, iteration count, learning rate, regularization, update implementation, metrics, bootstrap, seed, evaluation windows, prospective sample requirements, or research gate.

The six frozen features remain exactly:

1. `momentum_strength_5`
2. `range_pct_1`
3. `trend_alignment_20`
4. `volume_confirmation_5`
5. `directional_price_location_20`
6. `range_pct_5`

The target remains `DIRECTIONAL_SUCCESS` at horizon `T+1 observed market session`. The logistic model remains deterministic and standard-library based. The statistical gate remains the 20-observation moving-block bootstrap with 10,000 iterations, seed `2030301`, 95% intervals, and the originally frozen Brier-difference / ROC-AUC criteria. The development window remains `2024-12-06` through `2026-10-01`; it is not a pristine final test. Independent final evaluation remains future prospective data only. The prospective seed and 272-pair final sample contract remain unchanged.

## 5. Effective interpretation and approval boundary

The effective protocol is the original owner-approved frozen protocol interpreted together with Amendment 001. The original document hash remains the identity of the original protocol; the amendment and effective-protocol identity have separate fingerprints.

Amendment 001 is `AWAITING_OWNER_APPROVAL`. This record does not approve itself. Until the Project Owner separately approves it, V2 historical development remains blocked pending amendment approval, V2 implementation and final evaluation remain `NOT STARTED`, and production P2-03 remains `BLOCKED` for insufficient prospective OOS calibration history. `probabilityLabelAllowed` remains `false`.

No V2 feature matrix, fit, forecast, replay, performance metric, bootstrap, or comparison of initialization schemes is authorized by this amendment record. Historical publication timing, historical vintages, and revision history remain `NOT PROVEN`.
