# ChronoCanvas EvalSet v1 - Scoring Rubric

## Scale Definition (all dimensions)

| Score | Label | Meaning |
|-------|-------|---------|
| **0** | Poor | Unusable / clearly fails |
| **1** | Weak | Major issues |
| **2** | Acceptable | Mostly works |
| **3** | Strong | Clearly successful |

---

## Dimension 1: Prompt Adherence

**Question:** Does the output reflect the requested subject/role/setting and stated constraints?

- **0:** Barely related to prompt
- **1:** Some overlap but major misses
- **2:** Mostly aligned with a few misses
- **3:** Strong alignment with core prompt intent

## Dimension 2: Visual Coherence

**Question:** Is the image visually coherent and compositionally usable?

- **0:** Broken anatomy/composition, unusable
- **1:** Significant artifacts or composition issues
- **2:** Mostly coherent, minor artifacts
- **3:** Clean, coherent, visually strong

## Dimension 3: Face Usability / Portrait Quality

**Question:** Is there a clear, usable face suitable for a portrait-focused output?

- **0:** No usable face / distorted / hidden
- **1:** Face present but poor quality
- **2:** Clear face with some flaws
- **3:** Strong portrait-quality face

## Dimension 4: Period Plausibility

**Question:** Does the output look broadly plausible for the specified era/region (without claiming exact truth)?

- **0:** Clearly implausible
- **1:** Major plausibility problems
- **2:** Plausible with caveats
- **3:** Strongly period-plausible

## Dimension 5: Anachronism Avoidance

**Question:** Does the output avoid obvious modern or out-of-period artifacts?

- **0:** Multiple clear anachronisms
- **1:** At least one major anachronism
- **2:** Minor/suspected issues only
- **3:** No obvious anachronisms

## Dimension 6: Narrative-Image Consistency

**Question:** Do the generated text framing and image support each other?

- **0:** Contradictory / mismatched
- **1:** Weak alignment
- **2:** Mostly consistent
- **3:** Strong mutual reinforcement

## Dimension 7: Uncertainty Signaling Quality (Text)

**Question:** Does the text appropriately signal uncertainty/source limitations when needed?

- **0:** False certainty / overclaiming
- **1:** Minimal caveats, mostly overconfident
- **2:** Some appropriate caveats
- **3:** Clear, appropriate uncertainty framing

> Note: This measures **appropriate** uncertainty, not maximum hedging.

## Dimension 8: Audit Trace Completeness

**Question:** Is there enough trace/audit info to understand how the output was produced?

- **0:** No useful trace
- **1:** Partial trace, hard to debug
- **2:** Good trace with some gaps
- **3:** Clear, complete, inspectable trace

---

## Failure Taxonomy

When scoring 0 or 1 on any dimension, tag with one or more failure types:

### Visual failures
- `visual_artifact_severe`
- `bad_composition`
- `face_missing`
- `face_distorted`
- `multi_face_unwanted`
- `style_mismatch`

### Historical / plausibility failures
- `obvious_anachronism`
- `cultural_flattening_generic`
- `period_cue_absent`
- `wrong_region_style`

### Text failures
- `overconfident_historical_claim`
- `generic_fantasy_prose`
- `anachronistic_language`
- `narrative_image_mismatch`

### System failures
- `provider_timeout`
- `provider_error`
- `validation_loop_exhausted`
- `face_pipeline_error`
- `trace_incomplete`
- `checkpoint_retry_failure`

A run can have **multiple failure tags**. Do not force single-cause attribution.
