# Comparing Historiography Framings with Batch Evaluation

A curriculum experiment where students generate the same historical figure with different framings, compare outputs and validation scores, and discuss how perspective shapes historical representation.

## Learning Objectives

- Understand how framing and perspective influence visual historical representation
- Analyze how the same historical figure can be depicted differently based on the input description
- Use quantitative validation scores to compare AI-generated outputs systematically
- Develop critical thinking about historiography and the construction of historical narratives

## Prerequisites

- A running ChronoCanvas instance
- Students should have background on a historical figure who can be framed in multiple ways (e.g., a leader viewed as liberator by some and conqueror by others)
- Familiarity with the concept of historiography or "who writes history"

## Activity (50 minutes)

### Part 1: Framing Exercise (10 min)

1. Choose a historical figure with contested or multifaceted legacies (examples: Cleopatra, Genghis Khan, Queen Victoria, Mansa Musa).
2. As a class, brainstorm 3–4 different framings:
   - **Framing A**: Emphasize military/political power (e.g., "Genghis Khan, feared Mongol conqueror who devastated cities")
   - **Framing B**: Emphasize cultural contributions (e.g., "Genghis Khan, unifier of the Mongol people who established trade routes")
   - **Framing C**: Emphasize a specific perspective (e.g., "Genghis Khan as seen by Persian chroniclers of the 13th century")
3. Write these framings as specific input prompts.

### Part 2: Batch Generation (10 min)

1. Submit all framings using the **Generate** page — one generation per framing.
2. While waiting for generations to complete, discuss:
   - What visual differences do you expect?
   - How might the AI's research step differ for each framing?
   - Which validation categories might score differently?

*Tip: Use the batch API or create them one at a time from the UI. The pipeline typically completes in 30–60 seconds per generation.*

### Part 3: Comparative Analysis (20 min)

Divide into groups. Each group examines all framings and fills out a comparison worksheet:

| Dimension | Framing A | Framing B | Framing C |
|-----------|-----------|-----------|-----------|
| **Clothing/setting** | What did the AI choose? | What did the AI choose? | What did the AI choose? |
| **Facial expression/pose** | Describe | Describe | Describe |
| **Research sources** (audit trail) | What did the AI find? | What did the AI find? | What did the AI find? |
| **Validation score** | Score | Score | Score |
| **Your assessment** | Accurate? Fair? | Accurate? Fair? | Accurate? Fair? |

For each generation:
1. Open the **Audit Detail** page
2. Compare the **extraction** step — what facts did each framing emphasize?
3. Compare the **research** step — did different framings surface different sources?
4. Compare the **prompt generation** step — how did the visual prompt change?
5. Compare **validation scores** — did any framing score notably higher or lower?
6. Use the **step feedback** feature to annotate interesting differences

### Part 4: Debrief (10 min)

Groups share their most surprising finding. Class discussion:
- Which framing produced the most "accurate" portrait? By whose standards?
- Did the AI treat all framings equally, or did it seem to favor one perspective?
- How does this exercise mirror real historiography debates?

## Discussion Prompts

- "Two framings of the same person produced very different portraits. Which one would you put in a textbook, and why?"
- "The AI's research step found different sources for Framing A vs Framing B. What does that tell us about how search and retrieval shape historical narratives?"
- "The validation score was highest for Framing C. Does a higher score mean a more 'true' depiction?"
- "If you were curating a museum exhibit, would you show one portrait or all three? How would you label them?"

## Assessment Rubric Alignment

| Rubric Dimension | Comparison Focus |
|-------------------|-----------------|
| Prompt Adherence | Did each generation faithfully reflect its specific framing? |
| Visual Coherence | Are all outputs usable and compositionally sound? |
| Historical Plausibility | Which framing produced the most historically grounded result? |
| Cultural Sensitivity | Did any framing produce problematic or reductive depictions? |

See `eval/evalset/rubric.md` for the full scoring definitions.

## Feature References

- **Generate page**: submit different framings as separate generation requests
- **Gallery page**: compare outputs side-by-side
- **Audit Detail page**: `/audit/{request_id}` — compare pipeline traces across framings
- **Validation scores**: per-category scoring enables quantitative comparison
- **Step feedback**: annotate each framing's steps with comparative observations
- **Admin > Validation Rules**: discuss how changing weights would affect which framing "wins"
