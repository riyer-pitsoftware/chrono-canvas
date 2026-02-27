# ChronoCanvas for Digital Humanities Labs

A demo script for presenting ChronoCanvas to digital humanities scholarship teams — computational historians, DH lab directors, and interdisciplinary researchers.

## Audience Profile

- **Who**: Digital humanities faculty, postdocs, and lab coordinators (e.g., UCL Centre for Digital Humanities, Yale DHLab, Stanford CESTA, King's Digital Lab)
- **Their goals**: Integrate computational methods into humanities research, produce digital scholarly outputs, teach DH methods to graduate students
- **Their concerns**: Scholarly rigor, reproducibility, bias in AI-generated content, integration with existing DH toolchains
- **Their tech comfort**: Comfortable with APIs and computational tools; may not be deep in ML specifics

## Key Talking Points

1. **Transparent AI pipeline** — Every generation is fully auditable. The audit trail shows extraction, research, prompt generation, image creation, and validation as discrete, inspectable steps. This isn't a black box.

2. **Configurable validation** — Validation categories (clothing plausibility, cultural plausibility, temporal plausibility, artistic style) can be weighted by the research team. A medieval European history project might weight clothing accuracy higher; a comparative cultures project might prioritize cultural plausibility.

3. **Research traceability** — The research step surfaces what contextual information the AI gathered. Scholars can evaluate whether the AI's "sources" are appropriate and compare them against their own bibliography.

4. **Feedback and annotation** — The step-level feedback system lets researchers annotate the AI's reasoning at each pipeline stage, creating a scholarly commentary layer over the computational process.

5. **Batch and comparative analysis** — Generate the same figure with different framings to explore how input description shapes visual output — a direct computational analogue to historiography studies.

6. **Evaluation framework** — The built-in eval system (`eval/evalset/`) provides a rubric-based scoring framework that aligns with DH assessment practices. Custom rubrics can be developed for specific projects.

## Live Demo Walkthrough

### 1. Generate a Portrait (3 min)

- Navigate to the **Generate** page
- Enter a historically specific prompt: *"Isabella d'Este, Marchioness of Mantua, patron of the arts, circa 1500, in her studiolo surrounded by her collection"*
- Submit and watch the progress indicator
- **Talking point**: "Note how the input is a natural language description — no prompt engineering required. The pipeline handles decomposition."

### 2. Explore the Audit Trail (5 min)

- Once complete, click through to the **Audit Detail** page
- Walk through each section:
  - **Pipeline Timeline**: "Every step is timed. You can see exactly where computational effort was spent."
  - **LLM Calls**: "Expand any step to see the AI's actual reasoning — the system prompt, user prompt, and response. This is the transparency layer."
  - **Research step**: "Here's what the AI gathered about Isabella d'Este. You can evaluate this against your own knowledge of Mantuan court culture."
  - **Prompt Generation**: "The AI translated its research into a specific visual prompt. Notice the choices about color palette, composition, and setting."
  - **Validation**: "Four plausibility dimensions, each scored. The weights are configurable to match your project's priorities."
- **Talking point**: "This audit trail is a first-class research artifact. It documents the AI's decision-making process, not just the output."

### 3. Demonstrate Feedback (2 min)

- Expand a pipeline step (e.g., Research)
- Click "Add comment" and enter a scholarly observation: *"The AI correctly identified the studiolo context but missed the grotta — Isabella's two distinct collecting spaces."*
- **Talking point**: "Your team can annotate the AI's reasoning directly. These comments persist and are tied to specific pipeline steps."

### 4. Show Admin Controls (3 min)

- Navigate to **Admin > Validation Rules**
- Adjust a weight (e.g., increase clothing plausibility to 0.40)
- Show the pass threshold gauge
- **Talking point**: "Your project lead controls the evaluation criteria. For a project on Renaissance material culture, you'd weight clothing accuracy higher. For a project on cross-cultural exchange, cultural plausibility might matter more."

### 5. Discuss Evaluation (2 min)

- Mention the eval framework in `eval/evalset/`
- Show that the rubric (`eval/evalset/rubric.md`) covers prompt adherence, visual coherence, historical plausibility, and cultural sensitivity
- **Talking point**: "The evaluation framework is designed for systematic assessment. You can extend it with project-specific test cases and scoring criteria."

## Follow-up Conversation Starters

- "What validation categories would matter most for your current project? We can configure them to match your research questions."
- "How do you currently document decision-making in your computational workflows? The audit trail could complement that."
- "Would batch generation be useful for your comparative studies? You could generate the same figure across different time periods or cultural contexts."
- "Your graduate students could use the feedback system to develop critical evaluation skills around AI-generated historical content."
- "The API is straightforward — if you have existing DH pipelines, ChronoCanvas can integrate as a generation service."
- "What does your assessment workflow look like? The admin review queue supports accept/reject decisions with notes."
