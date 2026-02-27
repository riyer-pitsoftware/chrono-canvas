# ChronoCanvas for Cultural Heritage Teams

A demo script for presenting ChronoCanvas to museum technology teams, cultural heritage preservation programs, and heritage digitization initiatives.

## Audience Profile

- **Who**: Museum technologists, digital preservation officers, heritage program managers, cultural institution innovation leads (e.g., Smithsonian, British Museum Digital, UNESCO heritage documentation programs, national archive digitization teams)
- **Their goals**: Create engaging visual content for exhibits, educational materials, and digital collections; supplement gaps in visual archives; make heritage accessible to broader audiences
- **Their concerns**: Historical accuracy, cultural sensitivity, institutional credibility, community representation, rights and attribution
- **Their tech comfort**: Varies — some deeply technical, others more focused on curatorial and programmatic aspects

## Key Talking Points

1. **Filling visual gaps** — Many historical figures and periods lack visual records. ChronoCanvas generates plausible portraits that can supplement collections where photography didn't exist and paintings are scarce or lost.

2. **Built-in accuracy guardrails** — The validation pipeline scores every portrait across four plausibility dimensions. Nothing is published without assessment. The pass threshold and category weights are under institutional control.

3. **Full provenance chain** — Every generated portrait has a complete audit trail: what information was extracted, what research was gathered, how the visual prompt was constructed, and how the image scored on validation. This is the AI equivalent of provenance documentation.

4. **Human-in-the-loop review** — The admin review queue lets curators accept or reject AI-generated content before it enters any collection. The system is designed for human oversight, not autonomous publication.

5. **Educator integration** — The step-level feedback and annotation system lets educators and community members comment on the AI's reasoning, creating a dialogue between the technology and domain experts.

6. **Cultural sensitivity by design** — Validation includes cultural plausibility scoring. Institutions can increase this weight for projects involving underrepresented communities or sensitive cultural contexts.

## Live Demo Walkthrough

### 1. The Challenge (2 min)

Open with the scenario: "Your institution has a collection of 18th-century artifacts from West Africa, but no portraits of the artisans who created them. How do you create visual context for exhibit visitors without fabricating history?"

- **Talking point**: "ChronoCanvas doesn't claim to create 'real' portraits. It generates plausible visual interpretations based on historical research, with full transparency about how they were made."

### 2. Generate a Portrait (3 min)

- Navigate to the **Generate** page
- Enter a contextual prompt: *"An 18th-century Akan goldsmith from the Ashanti Empire, wearing traditional kente cloth, working with gold weights in a workshop setting"*
- Submit and wait for completion
- **Talking point**: "The input describes a historical type, not a specific individual. This is an important distinction for heritage contexts."

### 3. Walk Through the Audit Trail (5 min)

- Open the **Audit Detail** page for the completed generation
- Focus on these sections:
  - **Extraction**: "The AI identified the culture, time period, occupation, and material culture elements."
  - **Research**: "Here's the historical context the AI gathered — Ashanti goldworking traditions, kente cloth patterns, workshop settings. Your curators can evaluate whether this aligns with your collection's scholarship."
  - **Prompt Generation**: "The AI made specific choices about composition, lighting, and detail. These choices are documented and reviewable."
  - **Validation**: "Cultural plausibility scored here. Your institution controls how heavily this is weighted."
- **Talking point**: "This audit trail becomes part of the object's metadata. When a visitor asks 'how was this image made?', you have a complete answer."

### 4. Demonstrate Curatorial Review (3 min)

- Navigate to **Admin > Review Queue**
- Show how a curator can review a generation:
  - View the validation scores
  - See the generated image alongside its audit trail
  - Accept or reject with notes
- **Talking point**: "Nothing reaches your exhibit or digital collection without human review. The AI proposes; your curators decide."

### 5. Show Feedback in Action (2 min)

- Return to the Audit Detail page
- Add a comment on the Research step: *"The kente patterns described are more consistent with Ewe tradition than Ashanti. Consider adjusting the prompt to specify Ashanti-specific patterns."*
- **Talking point**: "Community advisors and cultural consultants can annotate the AI's reasoning. These comments are preserved as part of the record."

### 6. Discuss Institutional Controls (2 min)

- Show **Admin > Validation Rules**
- Demonstrate adjusting cultural plausibility weight upward
- **Talking point**: "For heritage projects, you might want cultural plausibility weighted at 0.40 or higher. The system adapts to your institution's standards."

## Follow-up Conversation Starters

- "What gaps exist in your visual collections? Which periods or communities are underrepresented?"
- "How does your institution currently handle AI-generated content? ChronoCanvas provides the transparency and audit trail your policies likely require."
- "Would your community advisory boards find the feedback system useful for reviewing AI-generated cultural content?"
- "The validation categories can be customized — are there additional dimensions your institution would want to evaluate? We can discuss extending the rubric."
- "How do you currently label AI-generated or digitally reconstructed content in your exhibits? The audit trail can support transparent labeling."
- "The batch generation feature could help your digitization team generate consistent visual contexts across an entire collection or exhibit."
- "What does your content review workflow look like today? The admin review queue can integrate with your existing approval processes."
