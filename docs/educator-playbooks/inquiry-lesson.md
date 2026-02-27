# Using Audit Logs as Lesson Artifacts

An inquiry-based lesson plan where students inspect ChronoCanvas audit trails, critique AI reasoning, and compare generated portraits against textbook accounts.

## Learning Objectives

- Analyze AI-generated historical portraits by examining each step of the generation pipeline
- Evaluate the accuracy of AI reasoning about clothing, cultural context, and temporal details
- Compare AI-generated visual interpretations with primary and secondary source descriptions
- Develop critical media literacy skills around AI-generated imagery

## Prerequisites

- A running ChronoCanvas instance (see `docs/development.md` for local setup)
- At least 2–3 completed generation requests with varied historical figures
- Students should have basic familiarity with the historical period(s) being examined
- Access to textbook or reference materials on the same figures

## Activity (45–50 minutes)

### Part 1: Orientation (10 min)

1. Open the **Gallery** page and select a completed generation request.
2. Walk students through the **Audit Detail** page, highlighting:
   - The **Pipeline Timeline** showing each processing step
   - The **LLM Calls** section where the AI's reasoning is visible
   - The **Validation** section with category scores
3. Explain that every portrait goes through extraction → research → prompt generation → image generation → validation. Each step leaves a trace.

### Part 2: Investigation (20 min)

Divide students into groups of 3–4. Assign each group a different generation request.

Each group should:

1. **Read the Extraction step** — What facts did the AI extract from the input? Are any missing or incorrect?
2. **Read the Research step** — What historical context did the AI gather? Cross-reference with your textbook. Note agreements and disagreements.
3. **Read the Prompt Generation step** — How did the AI translate research into a visual prompt? What choices did it make about clothing, setting, pose?
4. **Examine the Validation scores** — Which categories scored highest/lowest? Do you agree with the AI's self-assessment?
5. **Leave feedback** — Use the "Add comment" feature on each step to record your group's observations.

### Part 3: Debrief (15 min)

Each group presents their findings:

- What did the AI get right? What did it miss?
- Where did the AI's reasoning diverge from your textbook?
- If you could adjust the validation weights (see the **Admin > Validation Rules** page), which categories would you prioritize and why?

### Extension Activity

Have students use the **Admin > Validation Rules** page to adjust category weights, then re-generate the same figure using the **Retry** feature. Compare the before/after validation scores and discuss how changing evaluation criteria affects outcomes.

## Discussion Prompts

- "How does the AI decide what someone from the 15th century should wear? What sources might it be drawing on?"
- "The validation score for cultural accuracy was low. Looking at the reasoning, do you agree? What would you change?"
- "If this portrait were used in a textbook, what disclaimers would you add?"
- "How might the AI's training data create biases in how it depicts people from different cultures or time periods?"

## Assessment Rubric Alignment

This activity maps to the ChronoCanvas evaluation rubric dimensions (see `eval/evalset/rubric.md`):

| Rubric Dimension | Student Task |
|-------------------|-------------|
| Prompt Adherence | Evaluate whether the generated image matches the input description |
| Visual Coherence | Assess composition and anatomical accuracy |
| Historical Plausibility | Cross-reference AI research with textbook sources |
| Cultural Sensitivity | Discuss representation choices and potential biases |

## Feature References

- **Audit Detail page**: `/audit/{request_id}` — full pipeline trace with LLM calls and state snapshots
- **Validation section**: weighted category scores with pass/fail per dimension
- **Step feedback**: inline comment system on each pipeline step for student annotations
- **Admin > Validation Rules**: adjustable weights and pass threshold
- **Retry from step**: re-run the pipeline from any step with adjusted parameters
