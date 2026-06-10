from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag

from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from builds.models import BuildOrder, BuildOrderStep, MajorGod


DEFAULT_GOAL_ICON = "assets/images/score_age_2.png"

RESOURCE_NAMES = {"food", "wood", "gold", "favor"}


ICON_TOKEN_BY_KEYWORD: dict[str, str] = {
    # Resources render as text for readability.
    "cost_food": "Food",
    "food": "Food",
    "cost_wood": "Wood",
    "wood": "Wood",
    "cost_gold": "Gold",
    "gold": "Gold",
    "cost_favor": "Favor",
    "favor": "Favor",

    # Units
    "unit_type_villager": "[Villager]",
    "villager_icon": "[Villager]",
    "villager": "[Villager]",
    "villagers": "[Villager]",

    # Buildings
    "house_icon": "[House]",
    "house": "[House]",
    "temple_icon": "[Temple]",
    "temple": "[Temple]",
    "armory_icon": "[Armory]",
    "armory": "[Armory]",
    "granary_icon": "[Granary]",
    "granary": "[Granary]",
    "storehouse_icon": "[Storehouse]",
    "storehouse": "[Storehouse]",
    "military_academy_icon": "[Military Academy]",
    "military academy": "[Military Academy]",
    "barracks_icon": "[Barracks]",
    "barracks": "[Barracks]",
    "archery_range_icon": "[Archery Range]",
    "archery range": "[Archery Range]",
    "stable_icon": "[Stable]",
    "stable": "[Stable]",
    "market_icon": "[Market]",
    "market": "[Market]",
    "dock_icon": "[Dock]",
    "dock": "[Dock]",
    "monument_icon": "[Monument]",
    "monument": "[Monument]",
    "obelisk_icon": "[Obelisk]",
    "obelisk": "[Obelisk]",
    "longhouse_icon": "[Longhouse]",
    "longhouse": "[Longhouse]",
    "counter_barracks_icon": "[Counter Barracks]",
    "counter barracks": "[Counter Barracks]",
    "palace_icon": "[Palace]",
    "palace": "[Palace]",
    "town_center_icon": "[Town Center]",
    "town center": "[Town Center]",
    "tc_icon": "[Town Center]",

    # Economy / water terms
    "fishing_ship": "[Fishing Ship]",
    "fishing ship": "[Fishing Ship]",
    "fishing_ships": "[Fishing Ship]",
    "fs_icon": "[Fs]",
    "fs": "[Fs]",

    # Techs
    "hand_axe_icon": "[Hand Axe]",
    "hand axe": "[Hand Axe]",
    "pickaxe_icon": "[Pickaxe]",
    "pickaxe": "[Pickaxe]",
    "husbandry_icon": "[Husbandry]",
    "husbandry": "[Husbandry]",
    "plow_icon": "[Plow]",
    "plow": "[Plow]",
    "bow_saw_icon": "[Bow Saw]",
    "bow saw": "[Bow Saw]",
    "quarry_icon": "[Quarry]",
    "quarry": "[Quarry]",

    # Greek minor gods
    "athena_icon": "[Athena]",
    "athena": "[Athena]",
    "ares_icon": "[Ares]",
    "ares": "[Ares]",
    "hermes_icon": "[Hermes]",
    "hermes": "[Hermes]",
    "apollo_icon": "[Apollo]",
    "apollo": "[Apollo]",
    "dionysus_icon": "[Dionysus]",
    "dionysus": "[Dionysus]",
    "aphrodite_icon": "[Aphrodite]",
    "aphrodite": "[Aphrodite]",
    "hephaestus_icon": "[Hephaestus]",
    "hephaestus": "[Hephaestus]",
    "hera_icon": "[Hera]",
    "hera": "[Hera]",
    "artemis_icon": "[Artemis]",
    "artemis": "[Artemis]",

    # Egyptian minor gods
    "bast_icon": "[Bast]",
    "bast": "[Bast]",
    "ptah_icon": "[Ptah]",
    "ptah": "[Ptah]",
    "anubis_icon": "[Anubis]",
    "anubis": "[Anubis]",
    "hathor_icon": "[Hathor]",
    "hathor": "[Hathor]",
    "sekhmet_icon": "[Sekhmet]",
    "sekhmet": "[Sekhmet]",
    "nephthys_icon": "[Nephthys]",
    "nephthys": "[Nephthys]",
    "osiris_icon": "[Osiris]",
    "osiris": "[Osiris]",
    "horus_icon": "[Horus]",
    "horus": "[Horus]",
    "thoth_icon": "[Thoth]",
    "thoth": "[Thoth]",

    # Norse minor gods
    "freyja_icon": "[Freyja]",
    "freyja": "[Freyja]",
    "forseti_icon": "[Forseti]",
    "forseti": "[Forseti]",
    "heimdall_icon": "[Heimdall]",
    "heimdall": "[Heimdall]",
    "skadi_icon": "[Skadi]",
    "skadi": "[Skadi]",
    "bragi_icon": "[Bragi]",
    "bragi": "[Bragi]",
    "njord_icon": "[Njord]",
    "njord": "[Njord]",
    "baldr_icon": "[Baldr]",
    "baldr": "[Baldr]",
    "tyr_icon": "[Tyr]",
    "tyr": "[Tyr]",
    "hel_icon": "[Hel]",
    "hel": "[Hel]",

    # Atlantean minor gods
    "prometheus_icon": "[Prometheus]",
    "prometheus": "[Prometheus]",
    "oceanus_icon": "[Oceanus]",
    "oceanus": "[Oceanus]",
    "leto_icon": "[Leto]",
    "leto": "[Leto]",
    "hyperion_icon": "[Hyperion]",
    "hyperion": "[Hyperion]",
    "rheia_icon": "[Rheia]",
    "rheia": "[Rheia]",
    "theia_icon": "[Theia]",
    "theia": "[Theia]",
    "helios_icon": "[Helios]",
    "helios": "[Helios]",
    "atlas_icon": "[Atlas]",
    "atlas": "[Atlas]",
    "hekate_icon": "[Hekate]",
    "hekate": "[Hekate]",
}


COMMON_CLEANUPS: tuple[tuple[str, str], ...] = (
    ("Que ", "Queue "),
    (" que ", " queue "),
    ("Pre-que", "Pre-queue"),
    ("pre-que", "pre-queue"),
    ("Strangler Tree", "Straggler tree"),
    ("Strangler tree", "Straggler tree"),
    ("strangler tree", "straggler tree"),
    ("Stragler Tree", "Straggler tree"),
    ("stragler tree", "straggler tree"),
    ("ocassionally", "occasionally"),
    ("Ocassionally", "Occasionally"),
)


def is_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def fetch_url_html(url: str, timeout: int = 20) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            raw_bytes = response.read()
            content_type = response.headers.get("Content-Type", "")

    except HTTPError as error:
        raise RuntimeError(f"HTTP error while fetching URL: {error.code} {error.reason}") from error

    except URLError as error:
        raise RuntimeError(f"Network error while fetching URL: {error.reason}") from error

    charset = "utf-8"
    content_type_match = re.search(r"charset=([^;]+)", content_type, flags=re.IGNORECASE)

    if content_type_match:
        charset = content_type_match.group(1).strip()

    try:
        return raw_bytes.decode(charset, errors="replace")
    except LookupError:
        return raw_bytes.decode("utf-8", errors="replace")


def load_html(source: str) -> str:
    if is_url(source):
        return fetch_url_html(source)

    input_path = Path(source)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    return input_path.read_text(encoding="utf-8")


def normalize_space(value: str) -> str:
    value = value.replace("\xa0", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def apply_common_cleanups(value: str) -> str:
    cleaned = value

    for old, new in COMMON_CLEANUPS:
        cleaned = cleaned.replace(old, new)

    return cleaned


def convert_to_arrow_marker(value: str) -> str:
    value = re.sub(r"\bto\b", "-", value, flags=re.IGNORECASE)
    value = re.sub(r"\s*(?:->|→)\s*", " - ", value)
    value = re.sub(r"\s+-\s+", " - ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def ensure_sentence_punctuation(value: str) -> str:
    value = value.strip()

    if not value:
        return ""

    if value.endswith((".", "!", "?", ":", ";")):
        return value

    if re.search(r"[A-Za-z0-9\]\)]$", value):
        return value + "."

    return value


def strip_sentence_punctuation(value: str) -> str:
    return value.strip().rstrip(".;:!?")


def clean_assignment_remainder(value: str) -> str:
    value = normalize_space(value)
    value = re.sub(r"^[,\s]+", "", value)
    value = re.sub(r"^(?:and|then)\s+", "", value, flags=re.IGNORECASE)
    value = normalize_space(value)
    return value


def icon_to_token(img: Tag) -> str:
    src = str(img.get("src") or "").strip()
    title = str(img.get("title") or "").strip()
    alt = str(img.get("alt") or "").strip()

    search_values = [
        src.lower(),
        Path(src).name.lower(),
        title.lower(),
        alt.lower(),
    ]

    for search_value in search_values:
        for keyword, token in ICON_TOKEN_BY_KEYWORD.items():
            if keyword in search_value:
                return token

    fallback = title or alt
    fallback = normalize_space(fallback)

    if fallback:
        return f"[{fallback.title()}]"

    return "[Icon]"


def html_fragment_to_text(node: Tag | None) -> str:
    if node is None:
        return ""

    parts: list[str] = []

    def walk(child: Any) -> None:
        if isinstance(child, NavigableString):
            text = str(child)
            if text:
                parts.append(text)
            return

        if not isinstance(child, Tag):
            return

        if child.name == "img":
            parts.append(f" {icon_to_token(child)} ")
            return

        if child.name == "br":
            parts.append(" ")
            return

        for nested in child.children:
            walk(nested)

    walk(node)

    text = "".join(parts)
    text = normalize_space(text)
    text = apply_common_cleanups(text)
    text = convert_to_arrow_marker(text)

    return text


def parse_distribution(value: str) -> dict[str, int] | None:
    value = normalize_space(value)

    if not value:
        return None

    match = re.fullmatch(
        r"(\d+)\s*/\s*(\d+)\s*/\s*(\d+)\s*/\s*(\d+)",
        value,
    )

    if not match:
        return None

    food, wood, gold, favor = match.groups()

    return {
        "food": int(food),
        "wood": int(wood),
        "gold": int(gold),
        "favor": int(favor),
    }


def empty_split() -> dict[str, int | str]:
    return {
        "food": 0,
        "wood": 0,
        "gold": 0,
        "favor": 0,
        "pop": "",
    }


def make_phase_step(label: str) -> dict[str, Any]:
    return {
        "type": "phase",
        "label": label,
        "time": "",
        "food": "",
        "wood": "",
        "gold": "",
        "favor": "",
        "pop": "",
        "action": "",
        "note": "",
        "split": empty_split(),
    }


def parse_resource_assignment_prefix(value: str) -> tuple[str, str, str] | None:
    original = normalize_space(value)

    if not original:
        return None

    cleaned = strip_sentence_punctuation(original)

    # Redistribution instructions are too risky to auto-place.
    if re.search(r"\bfrom\b", cleaned, flags=re.IGNORECASE):
        return None

    if re.search(r"\btake\b", cleaned, flags=re.IGNORECASE):
        return None

    patterns = [
        # Examples:
        # 3 Villagers - Food
        # Initial 4 [Villager] - Food, builds [Granary]
        # 2 [Villager] - Gold
        r"""
        ^(?:initial\s+)?
        (?P<count>\d+)
        \s*
        (?:
            (?:\[Villager\]|\[Villagers\]|villagers?|vills?)
            \s*
        )?
        (?:
            -|->|→
        )?
        \s*
        (?P<resource>Food|Wood|Gold|Favor)
        \b
        (?P<rest>.*)
        $
        """,

        # Examples:
        # 2 Wood [Villager] builds 2 Military buildings
        # 1 Gold villager builds Storehouse
        r"""
        ^
        (?P<count>\d+)
        \s+
        (?P<resource>Food|Wood|Gold|Favor)
        \b
        (?P<rest>.*)
        $
        """,
    ]

    for pattern in patterns:
        match = re.match(pattern, cleaned, flags=re.IGNORECASE | re.VERBOSE)

        if not match:
            continue

        count = match.group("count")
        resource = match.group("resource").title()
        resource_key = resource.lower()
        rest = match.group("rest") or ""

        if resource_key not in RESOURCE_NAMES:
            continue

        resource_text = f"{count} - {resource}"
        remaining_action = clean_assignment_remainder(rest)

        return resource_key, resource_text, remaining_action

    return None


def is_header_distribution_row(
    col_a_text: str,
    col_b_text: str,
    col_c_text: str,
    col_d_text: str,
) -> bool:
    combined = f"{col_a_text} {col_b_text} {col_c_text} {col_d_text}"
    combined = normalize_space(combined).lower()

    if not combined:
        return False

    has_all_resources = all(
        token in combined
        for token in ("food", "wood", "gold", "favor")
    )

    has_no_real_instruction = not any(
        keyword in combined
        for keyword in (
            "build",
            "send",
            "take",
            "upgrade",
            "queue",
            "pre-queue",
            "add",
            "spawn",
            "prioritize",
            "research",
        )
    )

    return has_all_resources and has_no_real_instruction


def parse_title_parts(raw_title: str) -> dict[str, str]:
    """
    Parse titles like:

      Zeus - Military Focus - [DoD]Cod1eh
      Set Fast Advance (Anti-Kronos) - Cajocu
      Greek - Standard Water Boom - Boit, [DoD]Mirez & [DoD]Godschalk

    into:
      god_or_pantheon
      title
      author

    Important:
      Split only on spaced hyphens: " - "
      This avoids breaking names like "Anti-Kronos".
    """
    raw_title = normalize_space(raw_title)

    if not raw_title:
        return {
            "god": "",
            "title": "Imported Build Order",
            "author": "",
        }

    parts = [part.strip() for part in re.split(r"\s+-\s+", raw_title) if part.strip()]

    if len(parts) >= 3:
        god_or_pantheon = parts[0]
        title = " - ".join(parts[1:-1]).strip()
        author = parts[-1]

        return {
            "god": god_or_pantheon,
            "title": title,
            "author": author,
        }

    if len(parts) == 2:
        first, second = parts

        known_gods_and_pantheons = {
            "zeus",
            "poseidon",
            "hades",
            "ra",
            "isis",
            "set",
            "thor",
            "odin",
            "loki",
            "kronos",
            "oranos",
            "gaia",
            "greek",
            "egyptian",
            "norse",
            "atlantean",
            "chinese",
            "japanese",
        }

        first_lower = first.lower()

        if first_lower in known_gods_and_pantheons:
            return {
                "god": first,
                "title": second,
                "author": "",
            }

        return {
            "god": "",
            "title": first,
            "author": second,
        }

    return {
        "god": "",
        "title": raw_title,
        "author": "",
    }

def infer_build_metadata(
    soup: BeautifulSoup,
    forced_id: str | None,
    forced_title: str | None,
    forced_author: str | None,
    forced_subtitle: str | None,
    forced_summary: str | None,
    forced_meta: str | None,
    forced_goal_text: str | None,
    forced_goal_icon: str | None,
) -> dict[str, str]:
    h1 = soup.select_one("h1")
    detail_subtitle = normalize_space(h1.get_text(" ", strip=True)) if h1 else ""

    parsed = parse_title_parts(detail_subtitle)

    title = forced_title or parsed["title"]
    author = forced_author or parsed["author"]
    god_or_pantheon = parsed["god"]

    if forced_id:
        build_id = forced_id
    else:
        id_source = f"{title} {author}".strip()
        build_id = slugify(id_source)

    if forced_subtitle is not None:
        subtitle = forced_subtitle
    elif god_or_pantheon and author:
        subtitle = f"{god_or_pantheon} build order by {author}"
    elif god_or_pantheon:
        subtitle = f"{god_or_pantheon} build order"
    else:
        subtitle = ""

    if forced_summary is not None:
        summary = forced_summary
    elif god_or_pantheon and title:
        summary = f"A {god_or_pantheon} {title.lower()} build order converted from the original source."
    elif title:
        summary = f"A {title.lower()} build order converted from the original source."
    else:
        summary = ""

    if forced_meta is not None:
        meta = forced_meta
    elif title:
        meta = title
    else:
        meta = ""

    if forced_goal_text is not None:
        goal_text = forced_goal_text
    elif title:
        goal_text = title
    else:
        goal_text = ""

    goal_icon = forced_goal_icon or DEFAULT_GOAL_ICON

    return {
        "id": build_id,
        "title": title or "Imported Build Order",
        "subtitle": subtitle,
        "detailSubtitle": detail_subtitle,
        "summary": summary,
        "meta": meta,
        "goalLabel": "Goal",
        "goalText": goal_text,
        "goalIcon": goal_icon,
    }


def make_content_step(
    split: dict[str, int] | None,
    action: str,
    note: str,
    auto_resource_columns: bool,
    debug_assignments: bool,
    stats: dict[str, int],
) -> dict[str, Any]:
    split_data = empty_split()

    if split is not None:
        split_data["food"] = split["food"]
        split_data["wood"] = split["wood"]
        split_data["gold"] = split["gold"]
        split_data["favor"] = split["favor"]

    step = {
        "type": "",
        "label": "",
        "time": "",
        "food": "",
        "wood": "",
        "gold": "",
        "favor": "",
        "pop": "",
        "action": action,
        "note": note,
        "split": split_data,
    }

    if not auto_resource_columns or not action:
        stats["fallback_steps"] += 1
        return step

    parsed_assignment = parse_resource_assignment_prefix(action)

    if not parsed_assignment:
        stats["fallback_steps"] += 1
        return step

    resource_key, resource_text, remaining_action = parsed_assignment

    step[resource_key] = resource_text
    step["action"] = ensure_sentence_punctuation(remaining_action)

    stats["auto_placed_assignments"] += 1

    if debug_assignments:
        print(
            f"[assignment] {action!r} -> {resource_key}={resource_text!r}, action={step['action']!r}",
            file=sys.stderr,
        )

    return step


def parse_build_order_from_html(
    html: str,
    forced_id: str | None = None,
    forced_title: str | None = None,
    forced_author: str | None = None,
    forced_subtitle: str | None = None,
    forced_summary: str | None = None,
    forced_meta: str | None = None,
    forced_goal_text: str | None = None,
    forced_goal_icon: str | None = None,
    auto_resource_columns: bool = True,
    debug_assignments: bool = False,
) -> tuple[dict[str, Any], dict[str, int]]:
    soup = BeautifulSoup(html, "html.parser")

    metadata = infer_build_metadata(
        soup=soup,
        forced_id=forced_id,
        forced_title=forced_title,
        forced_author=forced_author,
        forced_subtitle=forced_subtitle,
        forced_summary=forced_summary,
        forced_meta=forced_meta,
        forced_goal_text=forced_goal_text,
        forced_goal_icon=forced_goal_icon,
    )

    stats = {
        "phase_steps": 0,
        "content_steps": 0,
        "auto_placed_assignments": 0,
        "fallback_steps": 0,
    }

    steps: list[dict[str, Any]] = []
    sections = soup.select(".section")

    if not sections:
        raise ValueError(
            "No .section elements were found in the HTML. "
            "The page may not contain the build order in the raw HTML source, "
            "or the source structure may be different than expected."
        )

    for section in sections:
        section_title = section.select_one(".section-title")

        if section_title:
            phase_label = normalize_space(section_title.get_text(" ", strip=True))

            if phase_label:
                steps.append(make_phase_step(phase_label))
                stats["phase_steps"] += 1

        rows = section.select(".row")

        for row in rows:
            col_a_text = html_fragment_to_text(row.select_one(".col-a"))
            col_b_text = html_fragment_to_text(row.select_one(".col-b"))
            col_c_text = html_fragment_to_text(row.select_one(".col-c"))
            col_d_text = html_fragment_to_text(row.select_one(".col-d"))

            if is_header_distribution_row(col_a_text, col_b_text, col_c_text, col_d_text):
                continue

            distribution = parse_distribution(col_a_text)

            action = col_b_text
            note_parts = [part for part in (col_c_text, col_d_text) if part]

            if not action and note_parts:
                action = note_parts.pop(0)

            note = " ".join(note_parts)
            note = normalize_space(note)

            action = ensure_sentence_punctuation(action)
            note = ensure_sentence_punctuation(note)

            if distribution is None and not action and not note:
                continue

            steps.append(
                make_content_step(
                    split=distribution,
                    action=action,
                    note=note,
                    auto_resource_columns=auto_resource_columns,
                    debug_assignments=debug_assignments,
                    stats=stats,
                )
            )
            stats["content_steps"] += 1

    build_order = {
        **metadata,
        "steps": steps,
    }

    return build_order, stats


def read_source_list(source_list_path: str) -> list[str]:
    path = Path(source_list_path)

    if not path.exists():
        raise FileNotFoundError(f"Source list file not found: {path}")

    sources: list[str] = []

    for line in path.read_text(encoding="utf-8").splitlines():
        cleaned = line.strip()

        if not cleaned:
            continue

        if cleaned.startswith("#"):
            continue

        sources.append(cleaned)

    return sources


def safe_int(value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0

    return max(number, 0)


def clean_static_path(value: Any) -> str:
    value = str(value or "").strip()

    if not value:
        return ""

    for prefix in ("/static/", "static/"):
        if value.startswith(prefix):
            return value.replace(prefix, "", 1)

    while value.startswith("../"):
        value = value[3:]

    if value.startswith("/"):
        value = value[1:]

    return value


class Command(BaseCommand):
    help = "Convert old DoD/Wix AoM build order pages and import them directly into the database."

    def add_arguments(self, parser):
        parser.add_argument(
            "sources",
            nargs="*",
            help="One or more input HTML file paths or http/https URLs.",
        )

        parser.add_argument(
            "--source-list",
            help="Path to a text file containing one source URL/file path per line.",
        )

        parser.add_argument(
            "--god",
            dest="gods",
            action="append",
            required=True,
            help=(
                "Major god slug to import into. Can be used multiple times. "
                "Example: --god zeus --god poseidon --god hades"
            ),
        )

        parser.add_argument(
            "--id",
            dest="forced_id",
            help="Override the generated build order id. Only valid with one source and one god.",
        )

        parser.add_argument(
            "--title",
            dest="forced_title",
            help="Override the build title. Only valid with one source.",
        )

        parser.add_argument(
            "--author",
            dest="forced_author",
            help="Override the parsed author. Only valid with one source.",
        )

        parser.add_argument(
            "--subtitle",
            dest="forced_subtitle",
            help="Override subtitle. Pass an empty string with --subtitle '' if you want it blank.",
        )

        parser.add_argument(
            "--summary",
            dest="forced_summary",
            help="Override summary. Pass an empty string with --summary '' if you want it blank.",
        )

        parser.add_argument(
            "--meta",
            dest="forced_meta",
            help="Override meta. Pass an empty string with --meta '' if you want it blank.",
        )

        parser.add_argument(
            "--goal-text",
            dest="forced_goal_text",
            help="Override goalText. Pass an empty string with --goal-text '' if you want it blank.",
        )

        parser.add_argument(
            "--goal-icon",
            dest="forced_goal_icon",
            help=f"Override goalIcon. Default: {DEFAULT_GOAL_ICON}",
        )

        parser.add_argument(
            "--no-auto-resource-columns",
            action="store_true",
            help=(
                "Disable automatic placement of assignment prefixes like "
                "'2 - Gold, builds [Storehouse]' into the matching resource column."
            ),
        )

        parser.add_argument(
            "--debug-assignments",
            action="store_true",
            help="Print every automatic resource-column assignment.",
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Convert and summarize, but do not write anything to the database.",
        )


    def handle(self, *args, **options):
        sources: list[str] = []

        if options["source_list"]:
            sources.extend(read_source_list(options["source_list"]))

        sources.extend(options["sources"])

        if not sources:
            raise CommandError("No sources provided. Pass one or more URLs/files or use --source-list.")

        god_slugs = [slugify(god) for god in options["gods"]]
        gods = []

        for god_slug in god_slugs:
            try:
                gods.append(MajorGod.objects.get(slug=god_slug))
            except MajorGod.DoesNotExist as error:
                raise CommandError(f"MajorGod not found for slug: {god_slug}") from error

        multiple_sources = len(sources) > 1
        multiple_gods = len(gods) > 1

        has_single_source_only_overrides = any(
            value is not None
            for value in (
                options["forced_id"],
                options["forced_title"],
                options["forced_author"],
            )
        )

        if (multiple_sources or multiple_gods) and has_single_source_only_overrides:
            raise CommandError(
                "--id, --title, and --author are only safe when importing one source into one god. "
                "For batch imports, let the command infer metadata from each page."
            )

        auto_resource_columns = not options["no_auto_resource_columns"]

        total_sources = 0
        total_god_imports = 0
        total_builds = 0
        total_steps = 0
        total_auto_placed = 0
        total_fallback = 0
        total_phases = 0

        for source_index, source in enumerate(sources, start=1):
            self.stdout.write(f"Converting [{source_index}/{len(sources)}]: {source}")

            html = load_html(source)

            build_data, stats = parse_build_order_from_html(
                html=html,
                forced_id=options["forced_id"],
                forced_title=options["forced_title"],
                forced_author=options["forced_author"],
                forced_subtitle=options["forced_subtitle"],
                forced_summary=options["forced_summary"],
                forced_meta=options["forced_meta"],
                forced_goal_text=options["forced_goal_text"],
                forced_goal_icon=options["forced_goal_icon"],
                auto_resource_columns=auto_resource_columns,
                debug_assignments=options["debug_assignments"],
            )

            total_sources += 1
            total_auto_placed += stats["auto_placed_assignments"]
            total_fallback += stats["fallback_steps"]
            total_phases += stats["phase_steps"]

            for god in gods:
                total_god_imports += 1

                if options["dry_run"]:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  DRY RUN: would import '{build_data['title']}' into {god.name} "
                            f"({len(build_data.get('steps', []))} steps)"
                        )
                    )
                    continue

                build_count, step_count = self.import_build_order_for_god(
                    god=god,
                    build_data=build_data,
                )

                total_builds += build_count
                total_steps += step_count

                self.stdout.write(
                    self.style.SUCCESS(
                        f"  Imported '{build_data['title']}' into {god.name}: {step_count} steps"
                    )
                )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Import complete."))
        self.stdout.write(f"Sources converted: {total_sources}")
        self.stdout.write(f"God import targets: {total_god_imports}")
        self.stdout.write(f"Build orders imported/updated: {total_builds}")
        self.stdout.write(f"Steps imported: {total_steps}")
        self.stdout.write(f"Phase rows created: {total_phases}")
        self.stdout.write(f"Auto-placed resource assignments: {total_auto_placed}")
        self.stdout.write(f"Fallback action/note rows: {total_fallback}")

    def import_build_order_for_god(self, god: MajorGod, build_data: dict[str, Any]) -> tuple[int, int]:
        build_slug = build_data.get("id") or build_data.get("slug") or slugify(build_data.get("title", "build"))

        build, _created = BuildOrder.objects.update_or_create(
            major_god=god,
            slug=build_slug,
            defaults={
                "title": build_data.get("title") or build_slug.replace("-", " ").title(),
                "subtitle": build_data.get("detailSubtitle") or build_data.get("subtitle") or "",
                "summary": build_data.get("summary") or "",
                "meta": build_data.get("meta") or "",
                "goal_label": build_data.get("goalLabel") or "Goal",
                "goal_text": build_data.get("goalText") or build_data.get("meta") or "",
                "goal_icon": clean_static_path(build_data.get("goalIcon") or DEFAULT_GOAL_ICON),
                "portrait": clean_static_path(
                    build_data.get("portrait") or f"assets/images/gods/{god.slug}_portrait.png"
                ),
                "is_published": True,
            },
        )

        BuildOrderStep.objects.filter(build_order=build).delete()

        step_count = 0
        steps = build_data.get("steps") or []

        for index, step_data in enumerate(steps, start=1):
            split = step_data.get("split") or {}

            BuildOrderStep.objects.create(
                build_order=build,
                order=index,
                type=step_data.get("type") or "",
                label=step_data.get("label") or "",
                time=step_data.get("time") or "",
                food=step_data.get("food") or "",
                wood=step_data.get("wood") or "",
                gold=step_data.get("gold") or "",
                favor=step_data.get("favor") or "",
                pop=step_data.get("pop") or "",
                action=step_data.get("action") or "",
                note=step_data.get("note") or "",
                split_food=safe_int(split.get("food")),
                split_wood=safe_int(split.get("wood")),
                split_gold=safe_int(split.get("gold")),
                split_favor=safe_int(split.get("favor")),
                split_pop=str(split.get("pop") or ""),
            )

            step_count += 1

        return 1, step_count