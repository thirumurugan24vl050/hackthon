# Hydro Mind Product Vision & Guidelines

When working on the Hydro Mind dashboard (bhavani-river-water-quality), strictly adhere to the following product vision, UI/UX guidelines, and anti-goals to ensure the strongest presentation.

## Core Dashboard Story
The dashboard must follow this logical flow:
**DATA → WHAT CHANGED → DETECTION → RISK → WHY → ACTION**

## Required Features & UI Representations

### 1. Data Provenance
- Every live number must show its source and last updated time.
- Add a small `LIVE • Updated 2 min ago` indicator.
- Clearly separate data types: LIVE, FORECAST, SATELLITE, SIMULATED.

### 2. "What Changed?" (Top-Level Intelligence)
- Add a top-level section summarizing 24-hour environmental changes.
- Show metrics like: `Water level: ↓ 0.42 ft`, `Storage: ↓ 1.8%`, `Rainfall: ↑ 24 mm`, `Turbidity: ↑ 31%`.
- Include an **AI interpretation** summarizing the situation (e.g., "Reservoir storage is declining while...").

### 3. AI Analyst (Hero Feature)
- The AI should not just be a chatbot. It must be able to answer specific questions:
  - "Is water stress increasing?"
  - "Why is the risk high?"
  - "What changed in the last 24 hours?"
  - "What should authorities check first?"
- **Rule:** Every AI answer must explicitly show the data evidence used.

### 4. Trend Intelligence
- Display compact 24h / 7-day trends for: Water level, Storage, Rainfall, Turbidity, DO, Water extent.
- The user/judge must immediately see what is changing, not just the absolute number.

### 5. Risk Explanation
- Do not just show a raw score (e.g., `WATER STRESS — 62`).
- Show context: `HIGH — 62/100` and list **Main contributors** (e.g., Low reservoir storage, Falling water level).
- Make the AI/risk engine explainable.

### 6. Early-Warning Timeline
- Visually represent the condition on a scale: `NORMAL → WATCH → ELEVATED → HIGH → CRITICAL` and indicate the current status.

### 7. Environmental Event Detection
- Highlight potential events (e.g., "Possible Runoff / Pollution Event").
- List checklists of evidence:
  - Heavy rainfall [✓]
  - Water level rise [✓]
  - Turbidity increase [✓]
  - Satellite anomaly [✓]
- Show Evidence Count (e.g., `4 / 4`) and Confidence Level (`HIGH`).
- Provide a **Recommended action** (e.g., "Prioritize field sampling...").

### 8. Multi-language (Tamil ↔ English)
- The language switch must change: Dashboard headings, KPI labels, Risk explanations, Alert descriptions, AI responses, and Action recommendations.
- **Do not translate:** Numbers, units, graphs, and scientific names.

## Anti-Goals (Strict Constraints)
**DO NOT** build, suggest, or add any of the following features. The focus is on polishing the story, not expanding the scope:
- ❌ Blockchain
- ❌ AR (Augmented Reality)
- ❌ Mobile app
- ❌ 3D digital twin
- ❌ 10 more ML models
- ❌ 30 water-quality parameters
- ❌ Complicated multi-agent architecture
- ❌ Unnecessary login/authentication
- ❌ Decorative animations everywhere
