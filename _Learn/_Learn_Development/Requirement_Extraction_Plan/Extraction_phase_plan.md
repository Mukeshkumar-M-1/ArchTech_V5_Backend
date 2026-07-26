
### **Phase 1: Foundation & The Hive Mind **

*Goal: Establish the asynchronous infrastructure and the central orchestrator without burning LLM tokens.*

* **1.1 Core Async Infrastructure:**
* Set up the Python `asyncio` event loop and graceful shutdown handlers (crucial for not losing data mid-flight).
* Implement robust, async-safe logging. Every agent must log its ID and current state (e.g., `[ReqArch-004] Normalizing...`).


* **1.2 The `ArchTechHive` Orchestrator:**
* Implement the `ArchTechHive` class with the dynamic Semaphore dictionaries (`ingest`, `llm`, `semantic`).
* Build the `id_lock` thread-safe counter mechanism to ensure no duplicate IDs are generated when agents report back concurrently.


* **1.3 Mock Agents & Dry Runs:**
* Create "dummy" versions of `LayoutAgent` and `RequirementArchitect` that simply use `asyncio.sleep()` and return hardcoded strings.
* **Milestone:** Successfully pass a 50-page dummy document through the Hive and watch the orchestrator spawn and reap 100+ tasks concurrently without memory leaks or deadlocks.



### **Phase 2: Agent Specialization **

*Goal: Build the "brains" of the individual agents and connect them to real APIs and logic.*

* **2.1 The `LayoutAgent` (Ingestion & Geometry):**
* Integrate your existing `_smart_segment` logic.
* Implement the `spawn_table_specialist` logic.
* *Testing constraint:* Feed it complex PDFs with nested tables to ensure it isolates tabular data correctly before passing it down the line.


* **2.2 The `RequirementArchitect` (NLP & Scoring):**
* Connect the LLM endpoints for the `_normalize` step.
* Implement the Classifier (`_classify`) and Evaluator (`_confidence`) logic.
* **Self-Healing Logic:** Add a `try/except` block inside the agent. If the LLM returns garbage JSON, the agent should automatically retry with a stronger prompt (up to 3 times) before gracefully failing.


* **2.3 The `QAAgent` (The Final Gatekeeper):**
* Integrate `RapidFuzz` for semantic deduplication.
* Build the logic to cross-link duplicate requirements and merge their page references (e.g., "Found on Page 4 and Page 12").



### **Phase 3: Integration & "Swarm" Tuning **

*Goal: Connect the agents and tune the system for speed, accuracy, and cost.*

* **3.1 End-to-End Pipeline Testing:**
* Run a real, moderately complex document (20-30 pages) through the full Hive.
* Validate the output JSON/CSV against a human-verified baseline.


* **3.2 Semaphore Tuning & Throttling:**
* Monitor API rate limits. Adjust your `asyncio.Semaphore` values. (e.g., If you hit a 429 Too Many Requests error, lower the `llm` semaphore; if CPU usage is low, increase the `ingest` semaphore).


* **3.3 Cost & Token Tracking:**
* Implement a global token counter. Every time a `RequirementArchitect` or `TableSpecialist` makes an LLM call, it must report the prompt/completion tokens back to the Hive to track costs per document.



### **Phase 4: Production Readiness **

*Goal: Harden the system for real-world usage and deployment.*

* **4.1 The `DeveloperAgent` (Ambiguity Resolution):**
* Implement the fallback logic you mentioned: If a requirement scores `< 0.30` confidence, spawn a secondary agent using a more capable (and expensive) model like GPT-4o or Claude 3.5 Sonnet to take a second look.


* **4.2 CI/CD & Deployment:**
* Dockerize the application.
* Set up unit tests for the deterministic parts (math formulas, layout segmenters) and integration tests for the LLM flows.



---

To ensure Phase 3 (Throttling and Tuning) goes smoothly, **which LLM provider (e.g., OpenAI, Anthropic, or local open-source models) are you planning to use for the `RequirementArchitect` and `TableSpecialist` agents?**