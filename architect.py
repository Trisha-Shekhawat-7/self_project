"""Assemble the final case file after the interrogations finish.

The architect takes the reasoner's evidence and the interrogation log and turns
them into a human readable report.
"""

import json
from datetime import datetime


class CaseArchitect:
    def __init__(self, model_client, model_name: str):
        self.client = model_client
        self.model_name = model_name

    def _time_to_minutes(self, time_str: str) -> int:
        """Convert '6:30 PM' → minutes since midnight for sorting. Returns 9999 if unparseable."""
        if not time_str:
            return 9999
        try:
            t = datetime.strptime(time_str.strip(), "%I:%M %p")
            return t.hour * 60 + t.minute
        except ValueError:
            return 9999

    def build_master_timeline(self, reasoner) -> list[dict]:
        """Flatten all suspects' claims into one sorted timeline."""
        events: list[dict] = []

        for profile in reasoner.suspect_profiles.values():
            for testimony in profile.get("testimonies", []):
                for claim in testimony.get("claims", []):
                    if not claim.get("start_time"):
                        continue
                    events.append({
                        "_sort_key": self._time_to_minutes(claim["start_time"]),
                        "suspect":       profile["name"],
                        "start_time":    claim["start_time"],
                        "end_time":      claim.get("end_time", "Unknown"),
                        "location":      claim.get("location", "Unknown"),
                        "action":        claim.get("action", ""),
                        "alibis_claimed": claim.get("alibi_characters", []),
                    })

        events.sort(key=lambda e: e["_sort_key"])
        for e in events:
            del e["_sort_key"]
        return events

    def generate_case_file(
        self, reasoner, interrogation_log: list[dict], victim_name: str
    ) -> str:
        """Stream the final report to stdout and return the full text."""
        print("\n" + "=" * 50)
        print("The final case file is being compiled")
        print("=" * 50)

        timeline = self.build_master_timeline(reasoner)

        contradictions = [e for e in reasoner.alibi_ledger if e["status"] == "contradicted"]

        case_data = {
            "victim": victim_name,
            "murder_window_starts_at": reasoner.murder_window_start,
            "master_timeline": timeline,
            "caught_lies_and_contradictions": contradictions,
            "interrogation_strategy_log": interrogation_log,
        }

        system_prompt = (
            "You are the chief inspector writing the final case report.\n"
            "Use the evidence gathered by the interrogation loop to write a clear,\n"
            "professional summary.\n\n"
            "REQUIRED SECTIONS:\n"
            "## Investigative Strategy\n"
            "  Explain why each round of questions was asked, using the topics in the "
            "interrogation log.\n\n"
            "## Master Timeline\n"
            "  Summarise the events in the master timeline and point out the contradictions.\n\n"
            "## Official Conclusion\n"
            "  Use the evidence to name the murderer and explain why.\n\n"
            "Write in a formal police-report style and use Markdown headings."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    "Compile the final Case File from this structured data:\n"
                    + json.dumps(case_data, indent=2)
                ),
            },
        ]

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=0.4,
            stream=True,
        )

        print("\n### OFFICIAL CASE FILE ###\n")
        full_text = ""
        for chunk in response:
            delta = chunk.choices[0].delta.content
            if delta:
                print(delta, end="", flush=True)
                full_text += delta

        print("\n\n" + "=" * 50)
        return full_text

