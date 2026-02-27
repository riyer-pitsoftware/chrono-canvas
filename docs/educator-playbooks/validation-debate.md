# Running Classroom Debates on Validation Scores

A historical empathy activity where student teams argue for or against the AI's validation decisions, using the admin review queue to adjudicate.

## Learning Objectives

- Practice historical argumentation using evidence from AI-generated audit trails
- Develop empathy for diverse historical perspectives by debating validation criteria
- Understand how evaluation rubrics shape outcomes in both AI systems and historical scholarship
- Build persuasive speaking and evidence-based reasoning skills

## Prerequisites

- A running ChronoCanvas instance with 4–6 completed generations that include validation results
- Ideally, mix of passed and failed validations for richer debate material
- Students should have basic familiarity with the historical periods represented
- Access to the **Admin** page (teacher-controlled)

## Activity (50 minutes)

### Setup (5 min before class)

1. Open **Admin > Review Queue** and identify 3–4 generations with interesting validation results — look for borderline scores, disagreements between categories, or surprising pass/fail outcomes.
2. Note the request IDs for each case.

### Part 1: Case Assignment (5 min)

1. Divide the class into teams of 3–4.
2. Assign each team a generation request and a position:
   - **Team A (Prosecution)**: Argue that the AI's validation was too lenient — the portrait should have failed.
   - **Team B (Defense)**: Argue that the AI's validation was correct or too harsh — the portrait should have passed.
3. Give teams the request ID so they can view the full audit trail.

### Part 2: Evidence Gathering (15 min)

Teams examine their assigned generation:

1. **Review the Audit Detail page** — Read through extraction, research, and prompt generation steps.
2. **Examine validation category scores** — Note which categories passed/failed and the reasoning.
3. **Compare against reference sources** — Use textbooks or online resources to build their case.
4. **Record observations** — Use the step feedback feature to annotate key evidence points.

Teams should prepare:
- 2–3 specific evidence points from the audit trail
- At least 1 reference to a historical source that supports their position
- A proposal for which validation weights should be adjusted (and in which direction)

### Part 3: Debates (20 min)

For each case (5 min per case):

1. **Prosecution** (2 min): Present evidence that the portrait fails historical standards.
2. **Defense** (2 min): Present counter-evidence or argue the standards are met.
3. **Class vote** (1 min): Should this portrait be accepted or rejected?

### Part 4: Teacher Adjudication (10 min)

1. Open the **Admin > Review Queue** on the projector.
2. For each debated case, apply the class's verdict using the **Accept** or **Reject** buttons.
3. Discuss: How did the class's decisions compare to the AI's original scores?
4. Optionally adjust validation weights in **Admin > Validation Rules** based on class consensus, then re-run a generation to see the impact.

## Discussion Prompts

- "The AI gave 'cultural plausibility' a score of 55. What standard is it using? Is that the right standard?"
- "Team B argued the clothing was appropriate for the region. Team A pointed out it was wrong for the specific decade. Who decides the right level of specificity?"
- "If you were building this AI system, how would you decide what 'passing' means for historical accuracy?"
- "Historians disagree about how people in this period dressed. Should the AI pick one interpretation, or acknowledge the uncertainty?"

## Assessment Rubric Alignment

| Rubric Dimension | Debate Connection |
|-------------------|------------------|
| Prompt Adherence | Did the AI follow the original request faithfully? |
| Visual Coherence | Is the image usable as a historical illustration? |
| Historical Plausibility | Core of the debate — teams argue this point |
| Cultural Sensitivity | Discuss whether representations are respectful and informed |

See `eval/evalset/rubric.md` for the full scoring definitions.

## Feature References

- **Admin > Review Queue**: `/admin` (Review Queue tab) — teacher-controlled accept/reject workflow
- **Admin > Validation Rules**: adjustable weights and pass threshold
- **Audit Detail page**: `/audit/{request_id}` — full evidence trail for each generation
- **Step feedback**: annotate specific steps with debate notes
- **Validation categories**: clothing, cultural, temporal, and artistic plausibility scores
