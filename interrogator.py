"""The detective's question generator and response parser.

This module covers three jobs: stream a chat completion, ask suspects focused
questions, and turn their replies into structured testimony.
"""

import json
import re
import time
from typing import Any, List, Literal, Optional, cast

import openai
from openai import OpenAI
from pydantic import BaseModel, Field

import config


class Claim(BaseModel):
    location: Optional[str] = Field(
        description="Specific location mentioned. Null if evaded."
    )
    start_time: Optional[str] = Field(
        description="Start time in 12-hour format, e.g. '6:00 PM'. Null if unknown."
    )
    end_time: Optional[str] = Field(
        description="End time in 12-hour format. Null if unknown."
    )
    alibi_characters: List[str] = Field(
        description="Names of other official suspects who can vouch for them. "
                    "Never include the victim or the speaking suspect."
    )
    non_suspect_witnesses: List[str] = Field(
        description="NPC witnesses (e.g. librarians, staff). Empty if none."
    )
    action: str = Field(description="Brief summary of what they were doing.")
    confidence: Literal["high", "medium", "low"] = Field(
        description="How certain the suspect sounds about this timeframe."
    )
    saw_victim_alive: bool = Field(
        description="True only if they explicitly state they saw the victim alive here."
    )


class SuspectTestimony(BaseModel):
    suspect_name: str = Field(description="Name of the speaking suspect.")
    emotional_state: Literal["calm", "defensive", "aggressive", "nervous"] = Field(
        description="Perceived tone of the overall response."
    )
    claims: List[Claim] = Field(
        description="Chronological list of distinct events or movements."
    )


def stream_llm_response(
    client: OpenAI,
    model_name: str,
    messages: list,
    temperature: float = 0.7,
    speaker_name: str = "",
) -> str:
    """Stream a chat completion and print tokens as they arrive.

    The call retries a few times on rate-limit or API errors with a simple
    linear backoff.
    """
    max_retries = 5
    base_wait = 15  # seconds between retry attempts

    for attempt in range(max_retries):
        try:
            if speaker_name and attempt == 0:
                print(f"\n{speaker_name}: ", end="", flush=True)

            response = client.chat.completions.create(
                model=model_name,
                messages=cast(Any, messages),
                temperature=temperature,
                stream=True,
            )

            full_text = ""
            for chunk in response:
                delta = chunk.choices[0].delta.content
                if delta is not None:
                    print(delta, end="", flush=True)
                    full_text += delta

            print()  # newline after streaming ends
            return full_text

        except (openai.RateLimitError, openai.APIError) as exc:
            if attempt < max_retries - 1:
                wait = base_wait * (attempt + 1)
                print(
                    f"\n[System] Upstream busy. Retrying in {wait}s "
                    f"(attempt {attempt + 1}/{max_retries})…"
                )
                time.sleep(wait)
            else:
                print(f"\n[System] Fatal: upstream offline after {max_retries} attempts.")
                raise exc

    return ""  # unreachable, satisfies type checkers


class InterrogatorAgent:
    """Generate questions for each suspect and parse their answers."""

    def __init__(
        self,
        model_name: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        client: OpenAI | None = None,
    ):
        cfg = config.DETECTIVE
        self.model_name = model_name or cfg["model_name"]
        self.histories: dict[int, list] = {}          # per-suspect conversation log
        self.suspect_names: dict[int, str] = {}       # index → full name
        self.allowed_suspect_names: list[str] = []    # all suspects in this case

        self.client = client or OpenAI(
            base_url=base_url or cfg["base_url"],
            api_key=api_key or cfg["api_key"],
        )

    def initialize_suspect(self, target_case: dict, suspect_index: int) -> None:
        """Load the case file and dossier for one suspect."""
        suspect = target_case["suspects"][suspect_index]
        victim = target_case.get("victim", {})

        self.suspect_names[suspect_index] = suspect["name"]
        self.allowed_suspect_names = [s["name"] for s in target_case["suspects"]]

        bullets = "\n".join(f"- {s}" for s in suspect.get("suspicion", []))
        case_file = (
            f"### CASE FILE: THE MURDER OF {victim.get('name', 'the victim').upper()} ###\n"
            f"Estimated Time of Incident: {target_case.get('time', 'Evening')}\n"
            f"Incident Location: {target_case.get('location', 'Unknown')}\n"
            f"Cause of Death: {victim.get('cause_of_death', 'Unknown')}\n"
            f"Murder Weapon: {victim.get('murder_weapon', 'Unknown')}\n"
            f"Victim Profile: {victim.get('introduction', '')}\n\n"
            f"### SUSPECT DOSSIER: {suspect['name'].upper()} ###\n"
            f"Profile: {suspect.get('introduction', '')}\n"
            f"Evidence against them:\n{bullets}"
        )

        self.histories[suspect_index] = [{"role": "system", "content": case_file}]
        print(f"[System] Loaded dossier for {suspect['name']} (index {suspect_index}).")

    def generate_question(
        self, topic: str, persona: str, suspect_index: int
    ) -> str:
        """Ask one focused question in the current detective persona."""
        if suspect_index not in self.histories:
            self.histories[suspect_index] = []

        case_file_content = self.histories[suspect_index][0]["content"]

        system_prompt = (
            f"{case_file_content}\n\n"
            f"You are the Lead Detective. Persona: {persona.upper()}.\n"
            f"Ask ONE direct question focusing on: {topic}.\n"
            "RULE 1: Never invent timestamps. Only use times the suspect has already stated.\n"
            "RULE 2: Output ONLY raw spoken dialogue — no narration, stage directions, or labels.\n"
            "RULE 3: Never fabricate evidence or accuse the suspect of actions they haven't mentioned."
        )

        if len(self.histories[suspect_index]) <= 1:
            trigger = f"Begin the interrogation. First question focuses on: {topic}."
        else:
            trigger = f"Evaluate the last answer. Next question focuses on: {topic}."

        messages = (
            [{"role": "system", "content": system_prompt}]
            + self.histories[suspect_index][1:]
            + [{"role": "user", "content": trigger}]
        )

        question = stream_llm_response(
            self.client, self.model_name, messages, temperature=0.7, speaker_name="Detective"
        )
        self.histories[suspect_index].append({"role": "assistant", "content": question})
        return question

    def parse_response(self, raw_text: str, suspect_index: int) -> dict:
        """Convert raw suspect speech into structured testimony."""
        current_name = self.suspect_names.get(suspect_index, "Unknown Suspect")

        history_entry = {"role": "user", "content": f"Suspect: {current_name}\n{raw_text}"}
        self.histories[suspect_index].append(history_entry)

        schema = SuspectTestimony.model_json_schema()
        schema["$defs"]["Claim"]["properties"]["alibi_characters"]["items"] = {
            "type": "string",
            "enum": self.allowed_suspect_names,
        }

        system_prompt = (
            "You are a forensic data parser. Extract spatial, temporal, and social facts.\n"
            "If a suspect does not mention another suspect, leave alibi_characters EMPTY [].\n"
            "Format all times as '6:00 PM' (never 24-hour). "
            "Output valid JSON matching this schema exactly:\n"
            f"{json.dumps(schema, indent=2)}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": history_entry["content"]},
        ]

        raw_json = None
        for attempt in range(5):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=cast(Any, messages),
                    temperature=0.0,
                    response_format={"type": "json_object"},
                )
                raw_json = resp.choices[0].message.content
                break
            except (openai.RateLimitError, openai.APIError):
                if attempt < 4:
                    wait = 15 * (attempt + 1)
                    print(f"\n[Parser] Upstream busy. Waiting {wait}s…")
                    time.sleep(wait)
            except Exception as exc:
                print(f"\n[Parser] Unexpected error: {exc}")
                break

        if not raw_json:
            print("\n[Parser] Returning a blank template to keep the run moving.")
            return {"suspect_name": current_name, "emotional_state": "calm", "claims": []}

        # ── Decode + sanitise ────────────────────────────────────────────────
        try:
            clean = raw_json.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            data = json.loads(clean)
            text_lower = raw_text.lower()

            def normalise_time(t: str | None) -> str | None:
                """Coerce any time string to '6:00 PM' format."""
                if not t:
                    return None
                t_up = t.upper().strip()
                parts = re.findall(r"\d+", t_up)
                if len(parts) >= 2:
                    h, m = int(parts[0]), int(parts[1])
                    suffix = "AM" if "AM" in t_up else ("PM" if "PM" in t_up else ("PM" if h >= 12 else "AM"))
                    h12 = h % 12 or 12
                    return f"{h12}:{m:02d} {suffix}"
                return t_up

            for claim in data.get("claims", []):
                claim["start_time"] = normalise_time(claim.get("start_time"))
                claim["end_time"] = normalise_time(claim.get("end_time"))

                # Keep only alibi names that:
                #   (a) are not the speaker themselves
                #   (b) actually appear (first name) in the raw speech
                #   (c) are in the official suspect list
                valid_alibis: list[str] = []
                for name in claim.get("alibi_characters", []):
                    first = name.split()[0].lower()
                    if (
                        name != current_name
                        and name in self.allowed_suspect_names
                        and first in text_lower
                        and name not in valid_alibis
                    ):
                        valid_alibis.append(name)
                claim["alibi_characters"] = valid_alibis

            return data

        except Exception as exc:
            print(f"\n[Parser] JSON decode failed: {exc}. Returning blank template.")
            return {"suspect_name": current_name, "emotional_state": "calm", "claims": []}