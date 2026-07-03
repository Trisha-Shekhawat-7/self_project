# Murder Mystery Interrogation Engine
## Overview

This is a complete system that generates detective questions, compiles the facts from suspect agents(also represented by AI agents), runs them through a logical reasoner and finally compiles a case report.
#Architecture
The basic architecture is -
1. interrogator.py - `generate_question` and `parse_response` methods. The former generates questions based on directive from reasoner and the latter resolves the supect responses into a json schema that is fed as structured data to the reasoner.py
2. reasoner.py - `update_case_state` and `get_next_action`. The former updates the suspect records, checks and verifies alibis mentioned in a gloabal alibi ledger, and flags contradictions or verifications. The latter runs through predefined questions and cross questioning and generates directives for the interrogator with varying personas. For example, it attacks low confidence answers and becomes accusatory when alibis dont match up.
3. architect.py - compiles the final case report using the complete logs and data gathered.
## Core Modules
1. config.py

Manages API credentials, allowing you to use different models or providers for the Detective and the Suspects.
interrogator.py

This module acts as the interface between the system and the models.

2. InterrogatorAgent: It handles generating questions based on the Reasoner's logic and parsing suspect answers into structured JSON using Pydantic.

Achieves different personas by dynamically using a trigger prompt made from the directive recieved from the reasoner.

Validation: It includes built-in normalization (standardizing time formats) and filters out hallucinated names, ensuring the reasoner only works with valid data

3. reasoner.py

The logical brain of the operation. It keeps the investigation on track using several key components:

suspect_profiles: Tracks what each suspect has said and which stage of interrogation they are in.

alibi_ledger: A cross-reference table that marks alibis as pending, verified, or contradicted.

Decision Tree: A priority-ranked system that decides the detective's next move. It begins from establishing a basic timeline to aggressive pressure-testing when a suspect is caught in a lie.

Basic State Machine - 
| P0 | First question ever | Analytical and Direct |

| P1 | Vague times or locations in last answer | Impatient and Authoritative |

| P1b | Low-confidence claim | Probing |

| P2 | Two suspects overlap in same location+time but don't mention each other | Intimidating and Suspicious |

| P3a | A pending alibi claim — target hasn't confirmed | Skeptical |

| P3b | A contradicted alibi — target denied it | Aggressive |

| P3c | This suspect's own alibi was contradicted by the target | Aggressive |

| P4 | Phase = `post_contact_timeline` | Probing |

| Fallback | No other trigger | Accusatory |

Also implements a dynamically shrinking murder window that uses the last_seen_alive tracker to update and become more accurate.


4. architect.py

Once all suspects have been interrogated, the CaseArchitect class is initialized. It flattens all collected claims into a single chronological timeline, cross-references any caught lies, and performs a final deduction to identify the murderer. It outputs a clean, human readable markdown report.

5. main.py

The main loop and entrypoint. It loads the dataset.json, initializes the agents, and runs the main interrogation loop. It manages the turn limits and calls the methods initialized in the other files.
Dataset Format (dataset.json)

## Setup & Running

    Install Dependencies: pip install openai python-dotenv pydantic

    Configure: Create a .env file and provide your DETECTIVE_API_KEY and SUSPECT_API_KEY.

    Execute: Run python main.py.

    Local LLMS can also be used, however they tend to not obey instructions exactly and hallucinate facts.

The system will stream the dialogue using stream_llm method, log the parsed JSON, and provide an early termination signal when a suspect has been interrogated and has nothing more to provide. Once the interrogation is completed, it provides a final case file using the CaseArchitect.

## Features

  -  Decoupling: The Detective and Suspects are separate agents. You can use a smart reasoning model for the Detective and a more character-focused model for the Suspects.

  -  Structured Parsing: By forcing the LLM to output JSON via Pydantic schemas, we turn a string of long text into structured data that can be processed logically

  -  State-Driven Logic: The reasoner prevents the detective from asking repetitive questions, focusing instead on tightening the net around suspects who have contradictory stories.

  -  Consistency: The Architect uses a low temperature setting (0.4) to ensure the final report is based on logical deduction rather than on inventing facts and being creative.