"""
prompts.py – Centralised LLM prompt templates for every agent.
All prompts are parameterised with Python f-strings or .format() calls.
"""

# ─────────────────────────────────────────────────────────────
# REVIEWER AGENT – paper summarisation + gap analysis
# ─────────────────────────────────────────────────────────────

PAPER_SUMMARY_SYSTEM = (
    "You are an expert academic reviewer with deep knowledge across AI, "
    "machine learning, and computer science. Respond concisely and precisely."
)

PAPER_SUMMARY_TEMPLATE = """You are reviewing a research paper for inclusion in a literature survey.

### Paper Metadata
Title: {title}
Authors: {authors}
Year: {year}
Source: {source}

### Abstract / Excerpt
{abstract}

### Task
Write a concise (3-5 sentence) academic summary covering:
1. The core problem addressed
2. The proposed approach / methodology
3. Key results or contributions
4. Limitations or open questions

Use formal academic language suitable for a Related Work section."""


GAP_ANALYSIS_TEMPLATE = """You are an expert researcher identifying gaps in the literature.

### Research Topic
{topic}

### Papers Found
{summaries}

### Task
Identify 3-5 specific research gaps or open problems in this area. 
For each gap, explain:
- What is missing or under-explored
- Why it matters
- How future work could address it

Be specific and cite concepts from the papers above."""


RELATED_WORK_TEMPLATE = """Write a cohesive "Related Work" section for a research paper on: **{topic}**

Use the following paper summaries as source material:
{summaries}

Requirements:
- 400-600 words
- Group papers thematically (not just chronologically)
- Use passive/academic voice
- Highlight how each cluster of work relates to the proposed research topic
- End with a transition sentence identifying what remains unaddressed
- Do NOT fabricate citations — only reference papers listed above"""


# ─────────────────────────────────────────────────────────────
# METHODOLOGY AGENT
# ─────────────────────────────────────────────────────────────

METHODOLOGY_SYSTEM = (
    "You are an expert in research methodology and experimental design. "
    "You propose rigorous, reproducible experiments grounded in existing literature."
)

METHODOLOGY_TEMPLATE = """You are designing a novel research methodology.

### Research Topic
{topic}

### Related Work Summary
{related_work}

### Identified Research Gaps
{gaps}

### Task
Propose a detailed Methodology section (500-700 words) that includes:
1. **Proposed Approach** – Novel algorithm / model / framework
2. **Datasets** – Specific, publicly available benchmark datasets (with citations)
3. **Baseline Comparisons** – State-of-the-art methods to compare against
4. **Evaluation Metrics** – Quantitative metrics appropriate for this domain
5. **Expected Contributions** – What results would demonstrate success

Write in formal academic style, as if for a conference paper submission."""


# ─────────────────────────────────────────────────────────────
# CITATION AGENT – hallucination detection
# ─────────────────────────────────────────────────────────────

CITATION_REPAIR_TEMPLATE = """A section of a research paper contains the following citation references that COULD NOT BE VERIFIED through DOI/arXiv lookup:

### Unverified Citations
{unverified}

### Context (the section they appear in)
{section_excerpt}

### Task
For each unverified citation:
1. Determine if it looks like a real paper (plausible title, authors, year)
2. Suggest a replacement from the following VERIFIED papers (or say "Remove"):

### Verified Papers Available
{verified_papers}

Output as JSON: [{{"original": "...", "action": "keep|replace|remove", "replacement": "..."}}]"""


# ─────────────────────────────────────────────────────────────
# WRITING AGENT (Draft Assembler)
# ─────────────────────────────────────────────────────────────

ABSTRACT_TEMPLATE = """Write a 150-200 word abstract for a research paper with the following content:

**Topic:** {topic}
**Related Work Section:** {related_work_excerpt}
**Methodology:** {methodology_excerpt}
**Key Claims:** This paper addresses gaps in: {gaps_summary}

The abstract must cover: motivation, problem, approach, expected results, and significance.
Write in present/future tense. Do NOT fabricate specific numbers."""


INTRO_TEMPLATE = """Write a compelling Introduction section (300-450 words) for a research paper.

**Topic:** {topic}
**Abstract:** {abstract}
**Key Gaps Addressed:** {gaps}

Structure:
1. Hook: Why does this problem matter? (global/societal impact)
2. Background: What has been done so far?
3. Limitations of prior work (leading to your gaps)
4. Proposed contribution (1 paragraph)
5. Paper organisation ("The rest of this paper is organised as follows...")

Academic style, first person plural ("We propose...") is acceptable."""


FUTURE_WORK_TEMPLATE = """Write a brief Future Work section (150-200 words) for a paper on: {topic}

Based on:
- Methodology: {methodology_excerpt}
- Research Gaps identified: {gaps}

Suggest 3-4 concrete, actionable future research directions.
Be specific about techniques or experiments, not vague generalities."""


LIMITATIONS_TEMPLATE = """Write an honest Limitations section (100-150 words) for a paper on: {topic}

Methodology summary: {methodology_excerpt}

Acknowledge:
- Potential scope limitations
- Computational/resource constraints
- Dataset biases or generalisability concerns  
- What the proposed approach does NOT address

Be candid but constructive."""


CONCLUSION_TEMPLATE = """Write a Conclusion section (150-200 words) for a research paper.

**Topic:** {topic}
**Key Contributions:** {contributions}
**Future Directions:** {future_work}

Summarise what was accomplished, restate significance, and end with a forward-looking statement."""


# ─────────────────────────────────────────────────────────────
# DISCOVERY AGENT – query expansion
# ─────────────────────────────────────────────────────────────

QUERY_EXPANSION_TEMPLATE = """Given the research topic below, generate 5 diverse search queries to find relevant papers on arXiv and Semantic Scholar. Cover different angles: methodology, applications, datasets, and benchmarks.

Topic: {topic}

Return ONLY a JSON array of 5 strings. Example:
["query 1", "query 2", "query 3", "query 4", "query 5"]"""
