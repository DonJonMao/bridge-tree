# ReAgent: A Reversible Multi-Agent Reasoning Framework (EMNLP 2025)

Welcome to **ReAgent**, a non-monotonic, multi-agent architecture for complex multi-hop reasoning.

## Table of Contents
1. [Introduction](#introduction)
2. [Key Innovations](#key-innovations)
3. [Repository Layout](#repository-layout)
4. [Execution Flow](#execution-flow)
5. [Getting Started](#getting-started)

---

## Introduction

**ReAgent** (Reversible Multi-Agent Reasoning) is designed to solve knowledge-intensive, multi-hop questions with a team of specialized agents. It bridges the gap between purely forward-chaining solutions (which can accumulate errors) and real-world needs for flexible, non-monotonic updates. Agents can locally backtrack or escalate to global supervisors if a contradiction arises, restoring the entire system to a previously consistent state.

This framework emphasizes:
- **Full Reversibility**: Mistakes at any stage can be rolled back—locally or globally—based on conflict signals.
- **Layered Modularity**: The code cleanly separates Execution, Supervisory, and Interaction layers, mapping directly to the theoretical constructs outlined in the accompanying paper.
- **Multi-Agent Concurrency**: Agents communicate through a shared message pool and can run in parallel time steps, enabling dynamic merging of partial inferences.
- **Adaptive Collaboration**: Roles such as **Thinker** or **BlackSheep** demonstrate how the system can incorporate adversarial or user-driven logic to enhance or stress-test the reasoning process.

---

## Key Innovations

1. **Non-Monotonic Architecture**  
   Supports partial or holistic rollback upon conflict detection, improving robustness in domains where incomplete or contradictory information is common.

2. **Multi-Temporal Concurrency**  
   Each agent operates in discrete time steps, saving snapshots for potential reversion. This design integrates with conflict resolution mechanisms in large-scale multi-hop tasks.

3. **Layered Design**  
   - **Execution Layer**: Agents that handle domain tasks (question decomposition, retrieval, verification, and assembling answers).  
   - **Supervisory Layer**: Agents that orchestrate conflict management (for example, Supervisor or Controller).  
   - **Interaction Layer**: Manages message buses and concurrency models for all message passing and event merging.

4. **Extensible Agent Roles**  
   Additional roles like **Human** (a human-in-the-loop agent) and **BlackSheep** (an adversarial agent) show how to integrate optional behaviors for testing or manual intervention.

---

## Repository Layout

```
ReAgent/
  ├── Agent/
  │    ├── agent.py
  │    ├── blacksheep.py
  │    ├── human.py
  │    ├── moderator.py
  │    ├── moderator2.py
  │    ├── thinker.py
  │    └── ... 
  ├── Environment/
  │    ├── environment.py
  │    ├── groupchat.py
  │    └── ...
  ├── Interaction/
  │    ├── message.py
  │    ├── messagepool.py
  │    └── ...
  ├── DataProcess/
  │    ├── Dataset.py
  │    ├── Document.py
  │    ├── Hotpotqa.py
  │    └── ...
  ├── backend/
  │    ├── api.py
  │    └── ...
  └── README.md
```

---

## Execution Flow

Below is a high-level scenario for a single run using `main.py`:

1. **Load Dataset** (e.g., HotpotQA)  
   A `HotpotqaDataset(...)` object is created to manage tasks containing questions, context paragraphs, and supporting facts.

2. **Initialize Agents**  
   The system creates baseline roles (Decomposer, Retriever, Verifier, AnswerAssembler, Supervisor, Controller) plus optional roles (**Thinker**, **BlackSheep**, **Human**).

3. **Set Up the Environment**  
   An `Environment` or `GroupChatEnvironment` is created with concurrency, message passing, and time-step snapshots.

4. **Run Moderator**  
   A **Moderator** (or **Moderator2**) agent coordinates stepwise chain-of-thought with partial or final answers.  
   - If **MAS** is enabled, it checks votes from other agents to decide whether a reasoning step needs revision.

5. **Conflict & Backtracking**  
   - If a conflict arises (e.g., an agent detects a contradiction), it attempts local backtracking or notifies the environment.  
   - The environment triggers a global revert if multiple conflicts occur or if a supervisory signal is raised.

6. **Conclude**  
   Once the system arrives at a final answer (or hits a time limit), the environment merges all partial results. The **AnswerAssembler** constructs the final solution.

---

## Getting Started

1. **Dependencies**  
   - Python 3.8+  
   - Basic Python libraries (for instance, `copy`, `time`, `json`)  
   - Optionally, advanced libraries for deep learning or LLM calls (such as `openai`, `requests`)

2. **Run**  
   ```bash
   python main.py
   ```
   This will build agents, initialize the environment, optionally load data, and then proceed through the chain-of-thought reasoning steps.

3. **Configuration**  
   - Modify the `Args` class in `main.py` to specify your dataset path (`args.dataset_path`) or adjust model names, concurrency flags, and trust disclaimers (`args.truth`).

4. **Adapting**  
   - For a simpler pipeline, omit **Human** or **BlackSheep**.
   - For advanced concurrency, use `run_time_step` or `run_until_stable` methods in the environment.
