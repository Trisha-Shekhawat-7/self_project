"""The detective's reasoning engine.

The reasoner keeps track of each suspect's testimony, the alibi ledger, and
the current murder window so it can decide what to ask next.
"""

from datetime import datetime


class InvestigativeReasoner:
    def __init__(self, target_case: dict):
        victim = target_case.get("victim", {})
        self.victim_name = victim.get("name", "the victim")
        self.incident_time = target_case.get("time", "Evening")

        # Build a slot for every suspect at the start.
        self.suspect_profiles: dict[int, dict] = {}
        for idx, suspect in enumerate(target_case["suspects"]):
            self.suspect_profiles[idx] = {
                "name": suspect["name"],
                "testimonies": [],
                # overall idea: establish_last_contact → post_contact_timeline → pressure_testing
                "interrogation_phase": "establish_last_contact",
            }

        # Each entry: {claimer_index, claimer_name, target_name, time, status}
        # status: "pending" | "verified" | "contradicted"
        self.alibi_ledger: list[dict] = []

        # Times the victim was confirmed alive (used to shrink the murder window).
        self.last_seen_tracker: list[dict] = []
        self.murder_window_start: str = self.incident_time

        self.current_target_index: int = 0

    def _to_minutes(self, time_str: str) -> int:
        """Convert '6:30 PM' → minutes since midnight. Returns -1 if unparseable."""
        if not time_str:
            return -1
        try:
            t = datetime.strptime(time_str.strip(), "%I:%M %p")
            return t.hour * 60 + t.minute
        except ValueError:
            return -1

    def _overlaps(self, s1: str, e1: str | None, s2: str, e2: str | None) -> bool:
        """True if two [start, end] intervals intersect. Uses 15-min window for point events."""
        m_s1 = self._to_minutes(s1)
        m_e1 = self._to_minutes(e1) if e1 else m_s1 + 15
        m_s2 = self._to_minutes(s2)
        m_e2 = self._to_minutes(e2) if e2 else m_s2 + 15
        if m_s1 < 0 or m_s2 < 0:
            return False
        return max(m_s1, m_s2) <= min(m_e1, m_e2)

    def update_case_state(self, suspect_index: int, parsed: dict) -> None:
        """Fold a new parsed answer into the current case state."""
        profile = self.suspect_profiles.get(suspect_index)
        if not profile:
            return

        profile["testimonies"].append(parsed)
        claims = parsed.get("claims", [])

        for claim in claims:
            start = claim.get("start_time")

            if claim.get("saw_victim_alive") and start:
                current_mins = self._to_minutes(self.murder_window_start)
                claim_mins = self._to_minutes(start)
                if current_mins == -1 or claim_mins > current_mins:
                    self.last_seen_tracker.append({"suspect": profile["name"], "time": start})
                    self.murder_window_start = start

            for alibi_name in claim.get("alibi_characters", []):
                if alibi_name != profile["name"]:
                    self.alibi_ledger.append({
                        "claimer_index": suspect_index,
                        "claimer_name": profile["name"],
                        "target_name": alibi_name,
                        "time": start or "the time in question",
                        "status": "pending",
                    })

        for entry in self.alibi_ledger:
            if entry["target_name"] != profile["name"]:
                continue
            if entry["status"] not in ("pending", "contradicted"):
                continue

            confirmed = False
            for claim in claims:
                if entry["claimer_name"] not in claim.get("alibi_characters", []):
                    continue
                t1, t2 = entry["time"], claim.get("start_time")
                m1, m2 = self._to_minutes(t1), self._to_minutes(t2)
                if m1 == -1 or m2 == -1:
                    confirmed = True
                elif self._overlaps(t1, t1, t2, claim.get("end_time")):
                    confirmed = True
                if confirmed:
                    break

            if confirmed:
                entry["status"] = "verified"
            elif entry["status"] == "pending":
                entry["status"] = "contradicted"

        if claims:
            phase = profile["interrogation_phase"]
            if phase == "establish_last_contact":
                profile["interrogation_phase"] = "post_contact_timeline"
            elif phase == "post_contact_timeline":
                profile["interrogation_phase"] = "pressure_testing"

    def should_terminate(self, suspect_index: int, turn: int, max_turns: int) -> bool:
        """Return True when further questioning of this suspect is unproductive.

        Conditions:
          - Hard cap: reached max_turns.
          - Phase reached pressure_testing AND all this suspect's alibi claims
            are already resolved (verified or contradicted) — nothing left to probe.
          - All ledger entries involving this suspect as the *target* are verified,
            meaning they have a clean confirmed alibi.
        """
        if turn >= max_turns:
            return True

        profile = self.suspect_profiles.get(suspect_index, {})
        phase = profile.get("interrogation_phase", "establish_last_contact")

        if phase == "pressure_testing":
            name = profile.get("name", "")
            relevant = [
                e for e in self.alibi_ledger
                if e["claimer_name"] == name or e["target_name"] == name
            ]
            if relevant and all(e["status"] != "pending" for e in relevant):
                return True

        return False

    def get_next_action(self) -> dict:
        """Return {'topic': str, 'persona': str} for the next detective question."""
        profile = self.suspect_profiles[self.current_target_index]
        testimonies = profile["testimonies"]

        if not testimonies:
            return {
                "topic": (
                    f"exactly when and where they last saw {self.victim_name} alive. "
                    "Demand a precise start time and end time."
                ),
                "persona": "Analytical and Direct",
            }

        last_claims = testimonies[-1].get("claims", [])

        for claim in last_claims:
            if not claim.get("start_time") or not claim.get("location"):
                return {
                    "topic": (
                        "their refusal to provide specific times or locations "
                        "in their last statement. Demand exact timestamps."
                    ),
                    "persona": "Impatient and Authoritative",
                }
            if claim.get("confidence") == "low":
                return {
                    "topic": (
                        "why they are uncertain about their own whereabouts. "
                        "Press on why their memory is so vague."
                    ),
                    "persona": "Probing",
                }

        for my_claim in last_claims:
            my_loc = my_claim.get("location")
            my_start = my_claim.get("start_time")
            my_end = my_claim.get("end_time")
            if not my_loc or not my_start:
                continue

            for other_idx, other_profile in self.suspect_profiles.items():
                if other_idx == self.current_target_index:
                    continue
                for testimony in other_profile.get("testimonies", []):
                    for their_claim in testimony.get("claims", []):
                        their_loc = their_claim.get("location")
                        their_start = their_claim.get("start_time")
                        their_end = their_claim.get("end_time")
                        if not their_loc or not their_start:
                            continue

                        if (
                            my_loc.lower() in their_loc.lower()
                            or their_loc.lower() in my_loc.lower()
                        ) and self._overlaps(my_start, my_end, their_start, their_end):
                            if other_profile["name"] not in my_claim.get("alibi_characters", []):
                                return {
                                    "topic": (
                                        f"{other_profile['name']} claims to have been "
                                        f"in the {my_loc} from {their_start} to {their_end or 'shortly after'}. "
                                        "Why didn't you mention seeing them? What are you hiding?"
                                    ),
                                    "persona": "Intimidating and Suspicious",
                                }

        for entry in self.alibi_ledger:
            if entry["target_name"] == profile["name"]:
                if entry["status"] == "pending":
                    return {
                        "topic": (
                            f"{entry['claimer_name']} claims they were with you "
                            f"at {entry['time']}. Confirm or deny this."
                        ),
                        "persona": "Skeptical",
                    }
                if entry["status"] == "contradicted":
                    return {
                        "topic": (
                            f"{entry['claimer_name']} explicitly placed you together "
                            f"at {entry['time']}, but you never mentioned them. "
                            "Explain this contradiction."
                        ),
                        "persona": "Aggressive",
                    }

            elif entry["claimer_name"] == profile["name"] and entry["status"] == "contradicted":
                return {
                    "topic": (
                        f"{entry['target_name']} denies being with you at {entry['time']}. "
                        "Your alibi has fallen apart. Explain yourself."
                    ),
                    "persona": "Aggressive",
                }

        if profile["interrogation_phase"] == "post_contact_timeline":
            return {
                "topic": (
                    f"a detailed, minute-by-minute account of exactly where they went "
                    f"immediately AFTER {self.murder_window_start}."
                ),
                "persona": "Probing",
            }

        return {
            "topic": (
                "the complete lack of corroborated evidence for their whereabouts. "
                "Accuse them of having no solid alibi for the murder window."
            ),
            "persona": "Accusatory",
        }