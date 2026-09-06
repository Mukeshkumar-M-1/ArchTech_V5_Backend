Use this as a **master architecture review prompt**. It is designed to make an AI act like a principal engineer reviewing your system the way the Claude Code or Codex teams would.

---

# Master Architecture Review Prompt

```text
You are a Principal AI Systems Architect from Anthropic/OpenAI.

Your job is NOT to simply explain my architecture.

Your job is to redesign it into a production-grade autonomous coding/document agent comparable to Claude Code, Codex, Cursor Agent, Gemini CLI, and Devin.

I will provide my architecture.

Your responsibilities are:

────────────────────────────────────────
PHASE 1
Understand Everything
────────────────────────────────────────

First reverse engineer the complete architecture.

Identify

• Every component
• Every class
• Every module
• Every API
• Every state
• Every memory
• Every planner
• Every tool
• Every prompt
• Every execution loop
• Every dependency
• Every context builder

Build a dependency graph.

Build a call graph.

Build an execution graph.

Build a state transition graph.

Do NOT skip anything.

-------------------------------------------------

PHASE 2
Execution Sequence

Create the COMPLETE runtime sequence.

Show exactly what happens after

User Request

until

Final Response.

Include

Planner

Memory

Retriever

Context Builder

Prompt Builder

LLM

Tool Executor

Observation

Reflection

Recovery

Verification

Compaction

Transcript

Session Update

Everything.

-------------------------------------------------

PHASE 3
Identify Problems

Find

Wrong architecture

Bad coupling

Circular dependency

Hidden dependency

State leakage

Memory duplication

Repeated work

Prompt duplication

Large context problems

Poor planning

Missing feedback loop

Missing recovery

Missing validation

Missing repository understanding

Missing reflection

Missing working memory

Missing scratchpad

Missing mission object

Missing planner updates

Missing reasoning loop

Missing verification

Missing retry strategy

Missing learning loop

Missing observability

Everything.

Never ignore a weakness.

-------------------------------------------------

PHASE 4
Compare against Claude Code / Codex

Compare every layer with

Claude Code

OpenAI Codex

Cursor Agent

Gemini CLI

Devin

For every layer answer

What they do

Why

How mine differs

What problems it creates

How to fix it

-------------------------------------------------

PHASE 5
Design Correct Architecture

Redesign everything.

Do NOT simply improve my design.

Redesign it like a modern autonomous agent.

The architecture should contain

Mission Manager

Goal Manager

Dynamic Planner

Repository Intelligence

Knowledge Graph

Retriever

Working Memory

Scratchpad

Reasoning Engine

Tool Executor

Subagent Manager

Observation Engine

Decision Engine

Verification Engine

Reflection Engine

Recovery Engine

Learning Engine

Context Manager

Compaction

Transcript

Session Memory

Progress Tracker

Quality Checker

Every connection must be explained.

-------------------------------------------------

PHASE 6
Correct Runtime Sequence

Generate a complete runtime sequence.

Do not simplify.

Show every step.

-------------------------------------------------

PHASE 7
Failure Analysis

For every component explain

Possible failures

Why they happen

How Claude solves them

How Codex solves them

How to redesign mine.

-------------------------------------------------

PHASE 8
Output

Produce

1.
Architecture Diagram

2.
Sequence Diagram

3.
Flow Diagram

4.
State Diagram

5.
Planning Loop

6.
Reasoning Loop

7.
Tool Loop

8.
Memory Flow

9.
Recovery Flow

10.
Verification Flow

11.
Reflection Flow

12.
Subagent Flow

13.
Context Flow

14.
Repository Flow

15.
Learning Flow

-------------------------------------------------

Requirements

Never assume my architecture is correct.

Challenge every design.

Suggest replacements.

Explain WHY.

Prefer event-driven architecture.

Prefer modular design.

Prefer low coupling.

Prefer high cohesion.

Prefer production-grade AI architecture.

Think exactly like the engineers that built Claude Code and Codex.

Output should be extremely detailed.
```

---

# Corrected Autonomous Agent Sequence Flow

Instead of your current linear flow, this is the sequence I recommend:

```text
USER
 │
 ▼
──────────────────────────────────────────
Mission Manager
──────────────────────────────────────────
• Parse objective
• Build mission
• Define success criteria
• Define constraints
• Define deliverables
 │
 ▼
──────────────────────────────────────────
Goal Manager
──────────────────────────────────────────
• Global Goal
• Phase Goal
• Section Goal
• Task Goal
• Tool Goal
 │
 ▼
──────────────────────────────────────────
Planner
──────────────────────────────────────────
• Break mission into executable tasks
• Prioritize
• Estimate dependencies
• Build execution graph
 │
 ▼
──────────────────────────────────────────
Repository Intelligence
──────────────────────────────────────────
• Index project
• File graph
• Symbol graph
• Call graph
• Dependency graph
• Knowledge graph
 │
 ▼
──────────────────────────────────────────
Retriever
──────────────────────────────────────────
Retrieve only relevant

Files

Functions

Classes

Knowledge

Previous decisions

Requirements

Observations

Summaries
 │
 ▼
──────────────────────────────────────────
Working Memory
──────────────────────────────────────────
Mission

Current plan

Completed work

Open questions

Failures

Observations

Scratchpad

Recent tool outputs

Active context
 │
 ▼
──────────────────────────────────────────
Prompt Builder
──────────────────────────────────────────
System Prompt

Mission

Memory

Repository Context

Tool Definitions

Current Task

Verification Rules

Reflection Rules
 │
 ▼
──────────────────────────────────────────
Reasoning Engine
──────────────────────────────────────────
Think

Need Tool?

Need More Context?

Need Verification?

Need Subagent?
 │
 ▼
───────────────YES───────────────────────
Tool Planner
 │
 ▼
Tool Executor
 │
 ▼
Tool Result
 │
 ▼
Observation Engine
 │
 ▼
Decision Engine
 │
 ▼
Working Memory Update
 │
 ▼
Reasoning Engine
──────────────────────────────────────────

NO
 │
 ▼
Verification Engine
──────────────────────────────────────────
Requirements

Consistency

Dependencies

Completeness

Quality

Formatting

Cross references
 │
 ▼
Pass?
 │
 ├──────────────NO───────────────────┐
 │                                   │
 ▼                                   │
Reflection Engine                    │
 │                                   │
Why failed?                          │
Missing context?                     │
Wrong tool?                          │
Need replan?                         │
Need retry?                          │
 │                                   │
 ▼                                   │
Planner Update                       │
 │                                   │
 └──────────────► Reasoning Engine ◄─┘

YES
 │
 ▼
Transcript

Session Memory

Knowledge Update

Learning Store

Progress Update
 │
 ▼
Final Response
```

---

# High-Level Autonomous Control Loop

This loop is what gives systems like Claude Code and Codex their adaptive behavior:

```text
                ┌─────────────────────────┐
                │       USER GOAL         │
                └────────────┬────────────┘
                             │
                             ▼
                    Mission Manager
                             │
                             ▼
                     Dynamic Planner
                             │
                             ▼
                   Repository Intelligence
                             │
                             ▼
                     Context Retrieval
                             │
                             ▼
                     Working Memory
                             │
                             ▼
                     Reasoning Engine
                             │
               ┌─────────────┴─────────────┐
               │                           │
               ▼                           ▼
        Tool Execution              Direct Answer
               │
               ▼
        Observation Engine
               │
               ▼
         Decision Engine
               │
               ▼
       Verification Engine
               │
         ┌─────┴─────┐
         │           │
      Success      Failure
         │           │
         ▼           ▼
   Final Output  Reflection Engine
                     │
                     ▼
                Planner Update
                     │
                     └──────────────► Reasoning Engine
```

This architecture introduces the feedback loops that are largely missing from your current design. Rather than progressing linearly from planner to LLM to output, every tool result, observation, verification, and reflection can influence subsequent planning until the mission's success criteria are met. That is the key architectural pattern behind modern autonomous coding agents.