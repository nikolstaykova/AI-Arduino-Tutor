"""Loads part/tool cards from library/{parts,tools}/*.json into one id+alias index.

See TOOLS.md / PARTS.md for the card schema. `wokwi_type` may be a single
string or a list of strings (e.g. breadboard size variants) — find_by_wokwi_type
handles both.
"""
import functools
import json
from pathlib import Path

LIBRARY_ROOT = Path(__file__).resolve().parent.parent / "library"


class Library:
    def __init__(self, cards):
        self.cards = cards  # id -> card dict
        self.alias_index = {}
        for card_id, card in cards.items():
            self.alias_index[card_id.lower()] = card_id
            for alias in card.get("aliases", []):
                self.alias_index[alias.lower()] = card_id

    def get(self, id_or_alias):
        """Look up a card by its id or any of its aliases (case-insensitive).
        Anything that isn't actually a string (a stray dict/int/etc. from a
        malformed event — see handle_event's Phase 6 note) is just an
        unknown lookup, not a crash."""
        if not isinstance(id_or_alias, str) or not id_or_alias:
            return None
        card_id = self.alias_index.get(id_or_alias.lower())
        if card_id is None:
            return None
        return self.cards[card_id]

    def all_ids(self):
        return sorted(self.cards.keys())

    def find_by_wokwi_type(self, wokwi_type, wokwi_value=None):
        """Find library cards matching a Wokwi diagram part's type (+ value,
        for ambiguous types like resistors where the type alone doesn't say
        which real-world part it is)."""
        matches = []
        for card in self.cards.values():
            wt = card.get("wokwi_type")
            if wt is None:
                continue
            types = wt if isinstance(wt, list) else [wt]
            if wokwi_type not in types:
                continue
            if "wokwi_value" in card and card["wokwi_value"] != wokwi_value:
                continue
            matches.append(card)
        return matches


@functools.lru_cache(maxsize=1)
def load_library():
    """Cached: the JSON files on disk don't change mid-process, and this
    is now called far more often than before (checker.py's alias/connector
    lookups default to loading the real library when the caller doesn't
    have one handy — see checker.board_alias_map), so re-reading every
    file from disk on every call would be wasteful. Call
    load_library.cache_clear() first in the rare case a test needs to
    pick up a genuinely modified file on disk mid-run."""
    cards = {}
    for subdir in ("parts", "tools"):
        folder = LIBRARY_ROOT / subdir
        if not folder.exists():
            continue
        for path in sorted(folder.glob("*.json")):
            with open(path) as f:
                card = json.load(f)
            cards[card["id"]] = card
    return Library(cards)
