# Complete Project Memory Management System — Full Plan

## Context

The current memory manager stores extracted requirements as JSON files (`all_requirements.json`, `category_stats.json`). This works for programmatic queries but is unusable by the LLM for document generation. The LLM needs **structured, human-readable, topic-organized markdown knowledge** — one file per requirement, grouped by category — plus **linking between related memories** so the Content Knowledge Agent can assemble rich context for each generation call.

This plan restructures the entire memory system into a **knowledge-first architecture** where every extracted requirement becomes a markdown memory file, categories organize them, and the Content Knowledge Agent fetches the right memories before each LLM call.

---

## 1. How It's Going to Work — End-to-End Flow

```
┌─ Phase A: Requirement Extraction + LLM Memory Enrichment ────────────────────────┐
│                                                                                    │
│  PDF Upload → Pipeline (stages 1-8) → 57 requirements as JSON                     │
│                                                                                    │
│  When requirements land in knowledge_base/all_requirements.json:                   │
│    1. MemoryManagementAgent.run(project_id) — synchronous after pipeline                   │
│    2. MemoryManagementAgent calls LLM 75 times (batched, ~57+8+8+1+1 reqs):               │
│       - 57 x enrich_requirement_memory() → requirements/*.md                    │
│       - 8 x enrich_category_memory() → categories/*.md                          │
│       - 8 x enrich_subcategory_memory() → subcategories/*.md                    │
│       - 1 x enrich_project_overview() → overview.md                             │
│       - 1 x enrich_generation_map() → generation_map.md                         │
│    3. _create_relationships() — rule-based → relationships.md                   │
│    4. _update_memory_index() → MEMORY.md                                        │
│                                                                                    │
│  Result: 78 markdown files + 1 relationships file + 1 overview                  │
│          All enriched by LLM with structured formatting, links, and context      │
│          ready for the Content Knowledge Agent to read before any generation     │
└────────────────────────────────────────────────────────────────────────────────────┘

┌─ Phase B: Document Generation ───────────────────────────────────────────────────┐
│                                                                                    │
│  User: "Generate FPGA Tests section" with req_ids=[REQ-0001, HAR-0004, ...]       │
│                                                                                    │
│  1. ContentKnowledgeAgent.collect_knowledge()                                      │
│     a) Loads direct requirement .md files (topic reqs)                             │
│     b) Loads related requirement .md files (semantic similarity)                   │
│     c) Loads category context .md files (broader category scope)                   │
│     d) Loads project index .md (overall stats, structure)                          │
│     e) Reads SRS Template .md for target section                                  │
│     f) Merges all into structured context prompt                                   │
│                                                                                    │
│  2. LLM API Call with assembled context → generates markdown section              │
│                                                                                    │
│  3. Store generated content in knowledge_memory_manager                            │
│     → versioned with tags, linked to source requirements                            │
│                                                                                    │
│  4. Update memory links (generation traceability)                                  │
└────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. How Requirements Are Used by Agent to Build Understanding Memory

### The MemoryManagementAgent — "Understanding Agent"

A new module: `backend/Memory_Management/memory_management_agent.py`

This agent runs **immediately after requirement extraction** and **uses LLM calls to transform raw JSON requirements into rich, structured markdown memory files** that the LLM can understand and reason about.

### MemoryManagementAgent Architecture

```python
# memory_management_agent.py

class MemoryManagementAgent:
    """
    Runs after requirement extraction to create the full
    markdown knowledge store from extracted requirements JSON.

    Uses an LLM (ContentEnricher) to transform raw requirement JSON
    into well-structured, human-readable markdown files that serve
    as background knowledge for future Content Knowledge Agent calls.

    Pipeline:
      Raw JSON (57 reqs)
        → Step 1: LLM-enrich each requirement into .md (57 LLM calls, batched)
        → Step 2: LLM-enrich category groupings into .md (8 LLM calls)
        → Step 3: LLM-enrich sub-category groupings into .md (8 LLM calls)
        → Step 4: Build relationships graph (no LLM — uses related_ids + keyword overlap)
        → Step 5: LLM-enrich project overview into .md
        → Step 6: LLM-enrich generation map
        → Step 7: Update MEMORY.md index
    """

    def run(self, project_id: str, user_id: str | None = None) -> dict:
        """Entry point — called after pipeline completes. Returns progress stats."""
        reqs = project_memory.get_all_requirements(project_id)

        # Phase A: LLM-enrich individual requirement memories
        result = self._enrich_requirement_memories(project_id, reqs)

        # Phase B: LLM-enrich category memories (with context from enriched reqs)
        result.update(self._enrich_category_memories(project_id, reqs))

        # Phase C: LLM-enrich sub-category memories
        result.update(self._enrich_subcategory_memories(project_id, reqs))

        # Phase D: Build relationships (rule-based, no LLM needed)
        self._create_relationships(project_id, reqs)

        # Phase E: LLM-enrich project overview
        result.update(self._enrich_project_overview(project_id, reqs))

        # Phase F: LLM-enrich generation map
        result.update(self._enrich_generation_map(project_id, reqs))

        # Phase G: Update MEMORY.md index
        self._update_memory_index(project_id)

        return result

    def _enrich_requirement_memory(self, project_id: str, req: dict, all_reqs: list) -> str:
        """
        Use LLM to transform a raw requirement JSON into a rich .md memory file.

        The LLM receives:
        - The raw requirement (text, explanation, keywords, etc.)
        - Context: all related requirements + category peers
        - A system prompt: "You are an SRS knowledge base writer.
          Transform this requirement into a well-structured markdown
          memory file that other LLM agents can use as background
          knowledge for document generation."

        The LLM outputs a complete .md file with:
        - Frontmatter metadata
        - A meaningful title (derived from category + content)
        - Well-formatted requirement text
        - Enhanced explanation (if the LLM deems it useful)
        - Structured attribute table
        - Keyword sections
        - Source citation
        - Related requirement links

        Writes to: knowledge/<project_id>/requirements/REQ-0001.md
        Returns: file path
        """

    def _enrich_category_memory(self, project_id: str, category: str, reqs: list) -> str:
        """
        Use LLM to create a category overview .md.

        The LLM receives:
        - All requirements in this category (as enriched .md content)
        - Category name
        - A system prompt: "You are an SRS knowledge base writer.
          Create a category overview that groups these requirements
          logically and provides context for document generation."

        The LLM outputs a complete .md with:
        - Category summary paragraph
        - Grouped sub-sections (e.g., for Hardware/Interface: group by
          PCIe, ARINC 818, DVI, DisplayPort, VGA)
        - Links to individual requirement .md files
        - Sub-category breakdown table

        Writes to: knowledge/<project_id>/categories/category_Hardware.md
        """

    def _enrich_subcategory_memory(self, project_id: str, sub_category: str, reqs: list) -> str:
        """
        Use LLM to create a sub-category .md.

        More focused than category memory — only one sub-category.
        Provides detailed grouping and context.
        """

    def _enrich_project_overview(self, project_id: str, reqs: list) -> str:
        """
        Use LLM to create the project overview .md.

        The LLM receives:
        - All requirement IDs and categories
        - Category distribution stats
        - Extraction metadata (source files, dates)

        The LLM writes a structured index that helps the Content
        Knowledge Agent quickly navigate the knowledge base.
        """

    def _enrich_generation_map(self, project_id: str, reqs: list) -> str:
        """
        Use LLM to create the generation map.

        The LLM receives:
        - All requirements with their category/sub_category
        - The SRS template structure (from Document_Section/)
        - A system prompt: "Map these requirements to SRS sections.
          For each section, list which requirements belong there,
          how they should be grouped, and what context the Content
          Knowledge Agent should provide."

        Output: generation_map.md — a lookup table for the Content
        Knowledge Agent to know which knowledge files to load for
        each document generation section.
        """

    # --- Rule-based helpers (no LLM) ---
    def _extract_categories(self, reqs: list) -> dict[str, list]:
        """Group requirements by top-level category."""

    def _create_relationships(self, project_id: str, reqs: list) -> None:
        """Build relationships graph using related_ids + keyword overlap."""

    def _update_memory_index(self, project_id: str) -> None:
        """Update MEMORY.md index with all knowledge files."""
```

### The ContentEnricher — LLM Prompt for Memory Generation

A new prompt: `prompts/System_Prompts/SRS_writer_Prompts/enrich_requirement_memory.txt`

```
# @version: 1.0
# @category: system
# @template: true
# @source: memory_management_agent

You are an SRS Knowledge Base Architect.

Your task is to transform a raw extracted requirement into a
well-structured, comprehensive markdown memory file.

This file will serve as BACKGROUND KNOWLEDGE for future LLM
document generation calls. Other agents will read this file
to understand the requirement in context.

INPUT YOU RECEIVE:
1. The raw requirement (JSON fields: id, text, explanation, category,
   sub_category, priority, confidence, keywords, source, page, related_ids)
2. Context from related requirements (if any)
3. The project's category distribution (how many in this category)

RULES:
- Create a meaningful H1 title from the requirement's core subject
- Keep the original requirement text EXACT as-is (do not rewrite)
- You MAY enhance the explanation if the LLM-provided one is too brief
- Structure attributes in a clean table
- Group keywords into logical tags
- Create proper markdown links to related requirement files
- Include ALL metadata from the JSON
- If sub_category is "General" or empty, skip sub-category section
- Output ONLY the markdown — no code fences, no preamble

OUTPUT FORMAT:
Frontmatter YAML → H1 Title → Requirement text → Enhanced explanation →
Attributes table → Keywords → Source citation → Related links
```

### What MemoryManagementAgent creates (step by step):

**Phase A: LLM-enrich individual requirement memories (57 LLM calls):**
- For each requirement, an LLM call transforms the raw JSON into a rich `.md` file
- The LLM creates a meaningful title, well-structured content, and proper links
- Files are written in parallel (batched to avoid rate limits)
- File path: `knowledge/<project_id>/requirements/REQ-0001.md`
- This becomes the **single source of truth** for that requirement

**Phase B: LLM-enrich category memories (8 LLM calls):**
- For each top-level category, an LLM call creates a grouped overview
- The LLM intelligently sub-groups requirements within the category
- E.g., for `Hardware/Interface`, the LLM groups by interface type (PCIe, ARINC, DVI, etc.)
- File path: `knowledge/<project_id>/categories/category_Hardware.md`

**Phase C: LLM-enrich sub-category memories (8 LLM calls):**
- For each sub-category, an LLM call creates a focused overview
- E.g., for sub-category `FPGA`, the LLM lists all FPGA reqs with descriptions
- File path: `knowledge/<project_id>/subcategories/subcategory_FPGA.md`

**Phase D: Build relationships (rule-based, no LLM):**
- Uses `related_ids` from each requirement to build bidirectional links
- Also discovers implicit relationships through keyword overlap (3+ shared keywords)
- File: `knowledge/<project_id>/relationships.md`

**Phase E: LLM-enrich project overview (1 LLM call):**
- Creates a master index with stats, category distribution, and navigation
- The LLM organizes it in the most useful structure for the Content Knowledge Agent
- File: `knowledge/<project_id>/overview.md`

**Phase F: LLM-enrich generation map (1 LLM call):**
- Maps each SRS section to the requirements and knowledge files needed
- The LLM reads the SRS template structure and creates a smart lookup table
- File: `knowledge/<project_id>/generation_map.md`

**Phase G: Update MEMORY.md index:**
- Lists all created knowledge files for reference

---

## 3. Category-Based Memory Creation

### Directory Structure

```
output/memory/<project_id>/knowledge/
├── requirements/                          # One .md per requirement
│   ├── REQ-0001.md                        # Hardware/FPGA
│   ├── REQ-0002.md                        # Hardware
│   ├── REQ-0003.md                        # Hardware
│   ├── REQ-0007.md                        # Hardware/Memory
│   ├── REQ-0008.md                        # Hardware/Interface
│   └── ...                                # All 57 requirements
│
├── categories/                            # One .md per top-level category
│   ├── category_Hardware.md              # 25 Hardware + 17 HW/Interface + ...
│   ├── category_Software.md              # Software/Application + Software
│   └── category_Functional.md            # Functional
│
├── subcategories/                         # One .md per sub-category
│   ├── subcategory_FPGA.md               # FPGA sub-category
│   ├── subcategory_Interface.md          # Interface sub-category
│   ├── subcategory_Memory.md             # Memory sub-category
│   ├── subcategory_Power.md              # Power sub-category
│   ├── subcategory_Processor.md          # Processor sub-category
│   ├── subcategory_Environmental.md      # Environmental sub-category
│   ├── subcategory_Mechanical.md         # Mechanical sub-category
│   └── subcategory_ArINC.md              # ARINC sub-category
│
├── overview.md                            # Project master index
├── relationships.md                       # Inter-requirement links
└── generation_map.md                      # Maps categories → SRS sections
```

### File Content Format — Individual Requirement Memory

**File:** `knowledge/requirements/REQ-0001.md`

```markdown
---
id: REQ-0001
type: requirement
project_id: Sample_1_1
category: Hardware/FPGA
sub_category: FPGA
priority: High
confidence: 0.53
source: DP-XMC-5049-000-HRS-0V04.pdf
page: 3
created_at: 2026-05-27T11:17:58Z
---

# REQ-0001 | FPGA Interface Support

## Requirement

The Kintex Ultrascale+ FPGA shall support STANAG3350, RGB, VGA, DVI, and ARINC818 interfaces. HDD/HRS/TP16/1.01

## Explanation

The Kintex Ultrascale+ FPGA must support five specific interface standards: STANAG3350, RGB, VGA, DVI, and ARINC818.

## Attributes

| Attribute | Value |
|-----------|-------|
| Category | Hardware/FPGA |
| Sub-Category | FPGA |
| Priority | High |
| Confidence | 0.53 |
| Has Unit | No |
| Has Directive | Yes |
| Rule Score | 1.0 |
| Character Count | 111 |

## Keywords

kintex ultrascale+, fpga, stanag3350, rgb, vga, dvi, arinc818

## Source

- **Document:** DP-XMC-5049-000-HRS-0V04.pdf
- **Page:** 3

## Related Requirements

- **[HAR-0010](HAR-0010.md)** — XMC PCIe video converter
- **[HAR-0014](HAR-0014.md)** — XMC PCIe based video converter module
```

### File Content Format — Category Memory

**File:** `knowledge/categories/category_Hardware.md`

```markdown
---
category: Hardware
total_requirements: 25
related_categories: [Hardware/FPGA, Hardware/Interface, Hardware/Memory, Hardware/Power, Hardware/Environmental, Hardware/Mechanical, Hardware/Processor]
---

# Hardware Requirements

## Summary

Total Hardware requirements: 25 (direct)
Related sub-categories: FPGA, Interface, Memory, Power, Environmental, Mechanical, Processor
Average Confidence: 0.46

## All Hardware Requirements

| ID | Sub-Category | Priority | Text Preview | Link |
|----|-------------|----------|-------------|------|
| HAR-0002 | Interface | High | XMC PCIe based video converter | [→](../requirements/HAR-0002.md) |
| HAR-0003 | Power | High | Clock generation and power supply | [→](../requirements/HAR-0003.md) |
| HAR-0004 | FPGA | High | VITA 42 Compliant XMC Module | [→](../requirements/HAR-0004.md) |
| ... | ... | ... | ... | ... |

## Sub-Category Breakdown

| Sub-Category | Count |
|-------------|-------|
| FPGA | 2 |
| Interface | 17 |
| Memory | 3 |
| Power | 3 |
| Environmental | 3 |
| Mechanical | 1 |
| Processor | 1 |

## Links to Sub-Categories

- [FPGA Requirements](../subcategories/subcategory_FPGA.md)
- [Interface Requirements](../subcategories/subcategory_Interface.md)
- [Memory Requirements](../subcategories/subcategory_Memory.md)
- [Power Requirements](../subcategories/subcategory_Power.md)
- [Environmental Requirements](../subcategories/subcategory_Environmental.md)
- [Mechanical Requirements](../subcategories/subcategory_Mechanical.md)
- [Processor Requirements](../subcategories/subcategory_Processor.md)
```

---

## 4. Complete Project Memory for Agent Understanding

### Master Overview File

**File:** `knowledge/overview.md`

```markdown
# Project Knowledge Base — Sample_1_1

## Project Overview

- **Project ID:** Sample_1_1
- **Source Document:** DP-XMC-5049-000-HRS-0V04.pdf
- **Extraction Date:** 2026-05-27T11:18:06Z
- **Total Requirements:** 57

## Requirements by Category

| Category | Count | Priority High | Avg Confidence |
|----------|-------|--------------|----------------|
| Hardware | 25 | 20 | 0.48 |
| Hardware/Interface | 17 | 15 | 0.45 |
| Hardware/Memory | 3 | 2 | 0.47 |
| Hardware/FPGA | 2 | 1 | 0.48 |
| Hardware/Power | 3 | 1 | 0.46 |
| Software/Application | 1 | 1 | 0.43 |
| Functional | 3 | 2 | 0.33 |
| Software | 2 | 0 | 0.27 |

## Knowledge Files Index

### Requirements
- [All 57 requirements](requirements/) — Individual .md files

### Category Groupings
- [Hardware (25 reqs)](categories/category_Hardware.md)
- [Software (3 reqs)](categories/category_Software.md)
- [Functional (3 reqs)](categories/category_Functional.md)

### Sub-Category Groupings
- [FPGA (2 reqs)](subcategories/subcategory_FPGA.md)
- [Interface (17 reqs)](subcategories/subcategory_Interface.md)
- [Memory (3 reqs)](subcategories/subcategory_Memory.md)
- [Power (3 reqs)](subcategories/subcategory_Power.md)

### Relationships
- [Relationships graph](relationships.md) — All requirement linkages

### Document Generation Map
- [SRS Section Mapping](generation_map.md) — How requirements map to SRS sections
```

### Generation Map — Requirements → SRS Sections

**File:** `knowledge/generation_map.md`

```markdown
# SRS Generation Map

Maps requirements to SRS document sections for content generation.

## Section 1: Introduction
- **Knowledge Source:** overview.md (acronyms table)
- **Requirements:** None (metadata from sources)

## Section 2: Overall Description
- **Knowledge Source:** categories/category_Hardware.md (constraints section)
- **Requirements:** Hardware, Power, Environmental, Mechanical
- **Generation Prompt:** Use power constraints + environmental specs + mechanical specs

## Section 3.2: Hardware Interfaces
- **Knowledge Source:** categories/category_Hardware.md (interfaces)
- **Requirements:** All sub_category=Interface requirements
- **Generation Prompt:** Group by interface type (PCIe, ARINC 818, DVI, etc.)

## Section 4: Functional Requirements
- **Knowledge Source:** Individual category .md files
- **Subsections:**
  - 4.1 Host Application → Software/Application requirements
  - 4.2 Target Application → Hardware sub_categories (DDR, FPGA, Storage)
  - 4.3 MCU Test → sub_category=Processor
  - 4.4 FPGA Tests → sub_category=FPGA
  - 4.5 Interface Tests → sub_category=Interface
  - 4.6 Memory Tests → sub_category=Memory
  - 4.7 Storage Tests → sub_category related to Flash/Storage

## Section 5: Software System Attributes
- **Knowledge Source:** Performance specs from Hardware requirements
- **Requirements:** Requirements with has_unit=true containing timing/data rate specs

## Section 7: Requirements Traceability
- **Knowledge Source:** relationships.md + all requirement .md files
- **Generation:** Auto-generated table mapping REQ-ID → Source HRS Ref ID
```

---

## 5. Requirement-to-MD File Mapping

### Mapping Rules

| Requirement Field | Maps To | File Location |
|---|---|---|
| `id` (e.g., `REQ-0001`) | Filename | `requirements/REQ-0001.md` |
| `category` (e.g., `Hardware`) | Category group | `categories/category_Hardware.md` |
| `sub_category` (e.g., `FPGA`) | Sub-category group | `subcategories/subcategory_FPGA.md` |
| `related_ids` (e.g., `[HAR-0010]`) | Links | Bidirectional in `requirements/*.md` + `relationships.md` |
| `keywords` | Tags/Sections | Inline in `requirements/*.md` |
| `source` + `page` | Citation | Footer of `requirements/*.md` |
| `category` + `sub_category` | SRS Section | `generation_map.md` |

### Filename Convention

```
requirements/<ID>.md              — Individual requirement memory
categories/category_<Cat>.md     — Top-level category memory
subcategories/subcategory_<Sub>.md — Sub-category memory
```

### Special Cases

1. **Multi-part categories** (`Hardware/Interface`):
   - Goes to `categories/category_Hardware.md` (top-level)
   - Also linked from `subcategories/subcategory_Interface.md`
   - The `/` in the category is used for sub-category grouping

2. **Requirements with no sub_category**:
   - Still get a `requirements/<ID>.md` file
   - Grouped into top-level category file

3. **Requirements with related_ids**:
   - Each related ID becomes a clickable link in the `.md` file
   - Also creates bidirectional entry in `relationships.md`

4. **Keywords-based implicit relationships**:
   - Requirements sharing 3+ common keywords get linked
   - Discovered by MemoryManagementAgent during the relationships phase

---

## 6. How Created Memories Are Linked for Future Generation Use

### MemoryLinker Module

A new module: `backend/Memory_Management/memory_linker.py`

This module manages the relationships between memory files and is used by the Content Knowledge Agent to assemble context.

```python
class MemoryLinker:
    """
    Manages linking between memory files for the Content Knowledge Agent.
    Three types of links:
    1. Direct links: requirement ↔ category file
    2. Relationship links: requirement ↔ related requirement
    3. Generation links: category ↔ SRS section
    """

    def get_topic_knowledge(self, project_id: str, requirement_ids: list[str]) -> dict:
        """
        Given a list of requirement IDs, assemble ALL linked knowledge:

        Returns: {
            "direct": [...],           # The requested .md files
            "relationships": [...],    # Linked requirement .md files via related_ids
            "category_context": [...], # Same category .md files
            "subcategory_context": [...], # Same sub-category .md files
            "project_overview": str,   # overview.md content
        }
        """

    def get_category_knowledge(self, project_id: str, category: str) -> dict:
        """
        Given a category, assemble all knowledge in that category.

        Returns: {
            "category_file": str,      # The category .md content
            "subcategory_files": [...], # Sub-category .md contents
            "requirement_files": [...], # Individual req .md contents
        }
        """

    def get_generation_context(self, project_id: str, heading_text: str,
                               requirement_ids: list[str]) -> dict:
        """
        Full context for a document generation call:

        Returns: {
            "system_prompt_vars": {    # Template variables for the prompt
                "heading_text": str,
                "topic_knowledge": str, # Formatted knowledge block
                "project_context": str,
            },
            "template_file": str,      # Path to Topic_Template .md
            "prior_sections": str,     # Previously generated content
        }
        """
```

### How Content Knowledge Agent Uses MemoryLinker

```python
# content_knowledge_agent.py

class ContentKnowledgeAgent:
    def collect_knowledge(self, project_id, requirement_ids, template_type,
                          heading_text, prev_doc_context=""):
        linker = MemoryLinker()

        # 1. Get all linked knowledge
        knowledge = linker.get_topic_knowledge(project_id, requirement_ids)

        # 2. Add generation map context
        gen_map = self._read_file(f"knowledge/{project_id}/generation_map.md")

        # 3. Read category context if available
        categories = set()
        for req_id in requirement_ids:
            req_md = self._read_file(f"knowledge/{project_id}/requirements/{req_id}.md")
            cat = self._extract_category(req_md)
            if cat:
                categories.add(cat)

        category_context = ""
        for cat in categories:
            cat_file = f"knowledge/{project_id}/categories/category_{cat}.md"
            category_context += self._read_file(cat_file) + "\n\n"

        # 4. Read project overview
        overview = self._read_file(f"knowledge/{project_id}/overview.md")

        # 5. Read template
        template = self._read_template(heading_text)

        return {
            "topic_knowledge": self._format_knowledge(knowledge),
            "category_context": category_context,
            "project_overview": overview,
            "generation_map": gen_map,
            "template": template,
            "prev_doc_context": prev_doc_context,
        }
```

### Knowledge Flow Diagram for Generation

```
Generation Call: req_ids=[REQ-0001, HAR-0004], heading="4.4 FPGA Tests"
                    │
                    ▼
        ┌─────────────────────────┐
        │ MemoryLinker            │
        │                         │
        │ GetTopicKnowledge():    │
        │                         │
        │  direct:                │
        │    ┌ REQ-0001.md ───┐   │
        │    └ HAR-0004.md ───┘   │  ← Direct requirement files
        │                         │
        │  relationships:         │
        │    ┌ HAR-0010.md ───┐   │  ← Linked via related_ids
        │    └ HAR-0014.md ───┘   │
        │                         │
        │  category_context:      │
        │    category_Hardware.md │  ← Full Hardware category
        │    subcategory_FPGA.md  │  ← FPGA sub-category
        │                         │
        │  project_overview:      │
        │    overview.md          │  ← Project stats
        └────────┬────────────────┘
                 │
                 ▼
        ┌─────────────────────────┐
        │ ContentKnowledgeAgent   │
        │                         │
        │ Assembles prompt:       │
        │                         │
        │ SYSTEM:                 │
        │   "You are filling 4.4  │
        │    FPGA Tests"          │
        │   topic_knowledge:      │
        │     [all .md content    │
        │      formatted as text] │
        │   project_overview:     │
        │     [57 reqs, 8 cats]   │
        │   template:             │
        │     [from Topic_Template│
        │      /04_functional_reqs│
        │      .md]               │
        │                         │
        │ USER:                   │
        │   [template with <!--  │
        │    comments to replace] │
        └────────┬────────────────┘
                 │
                 ▼
        ┌─────────────────────────┐
        │ LLM API Call            │
        │ sonnet46 / opus46       │
        │ max_tokens=4096         │
        └────────┬────────────────┘
                 │
                 ▼
        ┌─────────────────────────┐
        │ Generated Output        │
        │                         │
        │ Stored via:             │
        │ knowledge_memory_mngr   │
        │ .store_document()       │
        │ → knowledge/versions/   │
        │   REQ-0001_fpga_v1.md   │
        └─────────────────────────┘
```

---

## Files to Create

| File | Lines | Purpose |
|---|---|---|
| `Memory_Management/memory_management_agent.py` | ~400 | LLM-enriches requirements JSON into structured markdown memories (75 LLM calls batched) |
| `Memory_Management/memory_linker.py` | ~150 | Manages links between memory files, used by knowledge agent |
| `Memory_Management/content_knowledge_agent.py` | ~200 | Gathers topic knowledge for document generation LLM calls |
| `Memory_Management/knowledge_builder.py` | ~100 | Helper to build and format knowledge blocks from memory files |
| `prompts/System_Prompts/SRS_writer_Prompts/enrich_requirement_memory.txt` | ~30 | System prompt for LLM-enriching individual requirement .md files |
| `prompts/System_Prompts/SRS_writer_Prompts/enrich_category_memory.txt` | ~30 | System prompt for LLM-enriching category overview .md files |

## Files to Modify

| File | Lines | What Changes |
|---|---|---|
| `Memory_Management/project_memory.py` | ~50 | After `add_to_knowledge_base()`, call `MemoryManagementAgent.run(project_id)` to rebuild markdown knowledge |
| `generation_routes.py` | ~40 | Replace current `generate_document()` with new flow using `ContentKnowledgeAgent` |
| `prompts/System_Prompts/SRS_writer_Prompts/srs_writer.txt` | ~5 | Update template to use new knowledge variables |
| `system_config.py` | ~5 | Add `get_knowledge_dir(project_id)` function for knowledge base path |

## Existing Files to Reuse

| File | Function | Reuse As |
|---|---|---|
| `Memory_Management/project_memory.py` | `get_all_requirements()`, `search_requirements()` | Load raw requirement data |
| `Memory_Management/query_engine.py` | `get_related_requirements()` | Find semantically similar requirements |
| `Memory_Management/helpers.py` | `truncate_content()`, `ensure_directory()` | File I/O utilities |
| `Memory_Management/user_memory.py` | `load_all_user_memories()` | Load user preferences for generation |
| `knowledge_memory_manager.py` | `store_document()` | Store generated documents with versioning |
| `llm_api_handler.py` | `llm_request()` | Make LLM API calls with retry/fallback (used by MemoryManagementAgent) |
| `prompts/engine.py` | `prompts.render()` | Render SRS writer and enricher prompt templates |
| `Document_Section/SRS_Section/Topic_Template/` | Template .md files | Structural guidance for generation |

---

## Order of Implementation

1. **Enrichment prompts** (`enrich_requirement_memory.txt`, `enrich_category_memory.txt`) — Define LLM instructions first
2. **memory_management_agent.py** — LLM-enriches requirements JSON → 78 markdown memory files (uses `llm_request()` + `prompts.render()`)
3. **memory_linker.py** — Link management: connects memory files together
4. **knowledge_builder.py** — Formatting: formats knowledge into prompt-ready blocks
5. **content_knowledge_agent.py** — Orchestrator: assembles context for generation
6. **Integrate into project_memory.py** — Trigger MemoryManagementAgent after requirement save
7. **Update generation_routes.py** — Wire ContentKnowledgeAgent into generate flow
8. **Update srs_writer.txt prompt** — Adjust template for new knowledge format

---

## Verification

1. **Unit test MemoryManagementAgent**: Run on Sample_1_1 project → verify `knowledge/` directory has `requirements/` with 57 enriched .md files, `categories/` with 3 .md files, `subcategories/` with 8 .md files, `overview.md`, `generation_map.md`, `relationships.md`
2. **Verify LLM enrichment quality**: Spot-check 5 requirement .md files → verify they have meaningful titles, proper structure, and enhanced explanations (not just raw JSON dumped)
3. **Test MemoryLinker**: Call `get_topic_knowledge()` with `[REQ-0001, HAR-0004]` → verify it returns direct + related + category context
4. **Test ContentKnowledgeAgent**: Call with `heading="4.4 FPGA Tests"` → verify assembled prompt has correct template, knowledge, and context
5. **End-to-end generation**: POST to `/generate-document` with FPGA req_ids → verify LLM generates correctly structured markdown using the knowledge context
6. **Memory persistence**: Verify that after generation, the content is stored with proper versioning in `knowledge_memory_manager`
7. **Performance**: Measure time from extraction complete to `MemoryManagementAgent.run()` complete (75 LLM calls should batch to ~5-10 min depending on rate limits)
