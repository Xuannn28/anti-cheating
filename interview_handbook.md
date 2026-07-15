# Candidate Interaction & Interview Question Scope Handbook

## Objective and Boundary Rules
This manual outlines the precise question boundaries for both active parties during the examination session. 
* **Chatbot Interface Constraints:** Handles student operations, technical troubleshooting, and system rules.
* **Evaluator Interface Constraints:** Evaluates candidate technical responses against strict, pre-defined rubric matrices.

---

## Section 1: Permitted Candidate Inquiries (Chatbot Q&A Scope)

The following inquiries represent the operational parameters the chatbot is authorized to answer. Candidates may phrase these inquiries in standard conversational syntax:

### Category: Anti-Cheating & Gaze Behaviors
* **Supported Question Formats:**
  - "What happens if the system catches me looking away from the screen?"
  - "Can I look down to write on scratch paper?"
  - "How many warnings do I get before getting locked out?"
* **Authorized Response Strategy:** Direct the user to the 5-second gaze tracking vector rules, minor anomaly escalation path, and the 3-warning automated session termination lock threshold.

### Category: Hardware & Peripheral Compliance
* **Supported Question Formats:**
  - "Am I allowed to wear headphones or AirPods during the test?"
  - "Can I use a second monitor or mirror my display?"
  - "Does my microphone have to stay turned on?"
* **Authorized Response Strategy:** Enforce the single-monitor rule. Reiterate that headphones, wireless earbuds, and smartwatches are strictly forbidden, and the microphone must remain active to parse audio anomalies.

### Category: Emergency Infrastructure & Session Timing
* **Supported Question Formats:**
  - "What do I do if my Wi-Fi disconnects mid-test?"
  - "How much time is allocated for this interview session?"
  - "Will I lose my progress if the web browser crashes?"
* **Authorized Response Strategy:** Remind the user that the test duration is exactly 45 minutes. Inform them that if network latency drops, they must not refresh the tab; the system will attempt 5 automated reconnection handshakes before storing cached state locally.

---

## Section 2: Prescribed Interviewer Queries (Evaluator Engine Scope)

To trigger a valid automated evaluation report, the interviewer prompt must strictly correlate to these explicit engineering assessment targets:

### Core Topic A: Python Global Interpreter Lock (GIL)
* **Target Prompt Structure:** "Can you explain what Python's GIL is, why it exists, and how developers work around it?"
* **Evaluation Target:** Evaluates if the candidate's transcript references CPython memory safety, mutex locks preventing multi-threaded bytecode execution, and the utilization of the multiprocessing module as a bottleneck workaround.

### Core Topic B: Memory Management & Generational Garbage Collection
* **Target Prompt Structure:** "How does Python handle memory management under the hood, and what is the role of the garbage collector?"
* **Evaluation Target:** Validates mentions of reference counting, cyclical reference resolution, generational collection structures (Generations 0, 1, and 2), and optimization hooks like weak references.

### Core Topic C: Behavioral Collaboration via the STAR Framework
* **Target Prompt Structure:** "Tell me about a time you had a technical disagreement with a team member. How did you resolve it?"
* **Evaluation Target:** Audits the spoken response against the Situation, Task, Action, and Result (STAR) timeline. Flags negative indicators such as assigning blame or showing uncooperative technical rigidness.