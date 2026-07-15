# Section 1: Exam Operations & Anti-Cheating Regulations

## Rule-01: Prohibited Hardware and Peripherals
Candidates are strictly forbidden from wearing headphones, wireless earbuds, or smartwatches during the examination session. The microphone must remain unmuted to capture ambient audio anomalies.

## Rule-02: Device Limitations and Interface Restrictions
The exam must be taken on a single monitor. Running secondary displays or mirroring screens is prohibited. Navigating away from the exam tab or opening external developer applications (e.g., local IDEs, ChatGPT, or StackOverflow) will trigger an immediate system violation warning.

## Rule-03: Suspicion Flag Escalation
* **Flag Threshold:** The camera system monitors eye-gaze vectors. Looking away from the display area for greater than 5 consecutive seconds triggers a minor anomaly flag.
* **Escalation Path:** 
  - Anomaly 1 & 2: Passive UI Warning shown to candidate.
  - Anomaly 3: The test instance is automatically locked, the session is terminated, and a cheat log is submitted to the evaluator.

---

# Section 2: Core Python Engineering Interview Matrix

## Question-01: The Python Global Interpreter Lock (GIL)
* **Prompt:** "Can you explain what Python's GIL is, why it exists, and how developers work around it?"
* **Target Concept:** Memory management safety in CPython.

### Evaluation Criteria & Grading Rubric
* **Developing Performance (Score: 1-2):** Candidate states the GIL stands for Global Interpreter Lock and notes that it slows down code, but cannot explain why it exists or how to bypass it.
* **Proficient Performance (Score: 3-4):** Candidate explains that the GIL is a mutex preventing multiple native threads from executing Python bytecodes at once. They note it ensures thread safety with reference counting but creates bottlenecks for CPU-bound tasks. They suggest using the `multiprocessing` library to bypass it.
* **Exceptional Performance (Score: 5):** All proficient criteria met, plus the candidate discusses alternative interpreters (like Jython or PyPy), explains the difference between CPU-bound and I/O-bound threading behavior, or details how modern Python versions are implementing optional GIL features (PEP 703).

---

# Section 3: Behavioral Evaluation Matrix

## Question-01: Technical Disagreement & Collaboration
* **Prompt:** "Tell me about a time you had a technical disagreement with a team member. How did you resolve it?"

### Evaluation Criteria & Grading Rubric
* **Target Methodology:** The response must clearly map to the **STAR Framework** (Situation, Task, Action, Result).
* **Red Flags:** Candidate blames the teammate, displays rigid behavior, or describes a solution where they simply gave up without resolving the fundamental engineering problem.
* **Exceptional Indicator:** The candidate describes using objective, data-driven mechanisms (like benchmark testing, profiling, or system documentation reviews) to resolve the argument dispassionately.

---

# Section 4: Operational System FAQs & Emergency Guidelines

## Rule-04: Network Disconnection or Latency Spikes
* **Policy:** If the internet connection drops or drops frames for more than 15 consecutive seconds, the interface pauses.
* **Resolution:** The candidate should not refresh the web page. The system will attempt to securely reconnect to the server 5 times before saving data local storage cache and logging an automated admin alert ticket.

## Rule-05: Exam Windows and Time Limits
* **Policy:** The general technical interview is allocated exactly 45 minutes from the moment the session token initializes. 
* **Resolution:** A system warning timer flags the user workspace at the 10-minute and 5-minute remaining marks. No extensions are permitted unless pre-authorized by administrative accommodations.

---

# Section 5: Advanced Engineering Matrix additions

## Question-02: Python Memory Management and Garbage Collection
* **Prompt:** "How does Python handle memory management under the hood, and what is the role of the garbage collector?"
* **Target Concept:** Reference counting mechanisms combined with cyclical isolation detection algorithms.

### Evaluation Criteria & Grading Rubric
* **Developing Performance (Score: 1-2):** Candidate states that Python frees memory automatically and mentions that variables disappear when no longer needed, but cannot describe structural tracking techniques.
* **Proficient Performance (Score: 3-4):** Candidate defines reference counting: every object counts how many names point to it. They outline that the Garbage Collector (GC) runs explicitly to detect cyclical structures (e.g., Object A pointing to Object B, and Object B pointing to Object A) where reference counts never hit zero.
* **Exceptional Performance (Score: 5):** All proficient criteria met. Additionally, the candidate breaks down generational collection tiers (Generations 0, 1, and 2), threshold tracking frequencies, or optimization techniques like utilizing weak references (`weakref`) to prevent cyclical leaks entirely.
* **Explicit Negative Indicators:** Candidate claims reference counting is completely managed by the OS kernel or misidentifies Python's memory model as identical to Java's JVM runtime environment.