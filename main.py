"""Run the interrogation loop from start to finish.

The program loads one case, questions each suspect for a few rounds, and then
hands the collected evidence to the case architect for the final report.
"""

import json
import os

import config
from architect import CaseArchitect
from interrogator import InterrogatorAgent, stream_llm_response
from openai import OpenAI
from reasoner import InvestigativeReasoner

CASE_INDEX = 0
MAX_TURNS = 3
SUSPECT_INDICES = None


class SuspectAgent:
    """Role-play a single suspect and keep that suspect's conversation history."""

    def __init__(self, suspect_data: dict, victim_name: str, model_client, model_name: str | None = None):
        self.client = model_client
        self.model_name = model_name or config.SUSPECT["model_name"]
        self.name = suspect_data.get("name", "Unknown")

        system_prompt = (
            f"You are {self.name}. Do not break character.\n\n"
            f"### BACKGROUND ###\n{suspect_data.get('introduction', '')}\n\n"
            f"### YOUR STORY & TIMELINE ###\n{suspect_data.get('story', '')}\n\n"
            f"### CASE CONTEXT ###\n"
            f"A detective is interrogating you regarding the murder of {victim_name}.\n\n"
            f"### YOUR BEHAVIOURAL DIRECTIVE ###\n{suspect_data.get('task', 'Answer questions truthfully.')}"
        )
        self.history = [{"role": "system", "content": system_prompt}]

    def respond(self, question: str) -> str:
        self.history.append({"role": "user", "content": question})
        answer = stream_llm_response(
            self.client, self.model_name, self.history,
            temperature=0.6, speaker_name=self.name,
        )
        self.history.append({"role": "assistant", "content": answer})
        return answer


def main() -> None:
    print("\nStarting the murder-mystery interrogation...")

    dataset_path = os.path.join(os.path.dirname(__file__), "dataset.json")
    try:
        with open(dataset_path, encoding="utf-8") as f:
            dataset = json.load(f)
    except FileNotFoundError:
        print(f"Error: {dataset_path} not found.")
        return

    case = dataset[CASE_INDEX]
    victim_name = case["victim"]["name"]
    print(f"Case loaded: murder of {victim_name}")
    print(f"Location: {case.get('location', 'Unknown')} | Time: {case.get('time', 'Evening')}")

    detective = InterrogatorAgent()
    suspect_client = OpenAI(
        base_url=config.SUSPECT["base_url"],
        api_key=config.SUSPECT["api_key"],
    )
    reasoner = InvestigativeReasoner(target_case=case)

    indices = SUSPECT_INDICES if SUSPECT_INDICES is not None else list(range(len(case["suspects"])))

    interrogation_log: list[dict] = []

    for suspect_idx in indices:
        suspect_data = case["suspects"][suspect_idx]
        print(f"\n{'=' * 50}")
        print(f"Interviewing {suspect_data['name'].upper()}")
        print("=" * 50)

        suspect = SuspectAgent(suspect_data, victim_name, suspect_client)
        detective.initialize_suspect(target_case=case, suspect_index=suspect_idx)
        reasoner.current_target_index = suspect_idx

        turn = 0
        while not reasoner.should_terminate(suspect_idx, turn, MAX_TURNS):
            print(f"\n--- {suspect_data['name']} | Question {turn + 1} ---")

            directive = reasoner.get_next_action()
            print(f"[Reasoner] Topic: {directive['topic']}")
            print(f"[Reasoner] Persona: {directive['persona']}")

            question = detective.generate_question(
                directive["topic"], directive["persona"], suspect_idx
            )
            answer = suspect.respond(question)
            parsed = detective.parse_response(answer, suspect_idx)

            print(f"[Parsed] {json.dumps(parsed, indent=2)}")

            interrogation_log.append({
                "suspect_name":     suspect_data["name"],
                "turn":             turn + 1,
                "reasoning_motive": directive["topic"],
                "question_asked":   question,
                "suspects_defense": answer,
            })

            reasoner.update_case_state(suspect_idx, parsed)
            turn += 1

        if turn < MAX_TURNS:
            print(f"\n[System] Interrogation of {suspect_data['name']} terminated early "
                  f"after {turn} turn(s)")

    print("\nAll interrogations are complete.")

    architect = CaseArchitect(model_client=detective.client, model_name=detective.model_name)
    architect.generate_case_file(
        reasoner=reasoner,
        interrogation_log=interrogation_log,
        victim_name=victim_name,
    )


if __name__ == "__main__":
    main()