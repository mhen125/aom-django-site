from django.http import Http404, JsonResponse
from django.db.models import Prefetch
from django.shortcuts import render
from django.urls import reverse
from django.utils.text import slugify
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import user_passes_test
from django.conf import settings
from django.templatetags.static import static

import json
import re

from .models import BuildOrder, BuildOrderStep, MajorGod, Pantheon
from .fallback_data import FALLBACK_AOM_DATA


PANTHEON_ORDER = [
    "greek",
    "egyptian",
    "norse",
    "atlantean",
    "chinese",
    "japanese",
    "aztec",
]

GOD_ORDER = {
    "greek": [
        "zeus",
        "hades",
        "poseidon",
        "demeter",
    ],
    "egyptian": [
        "ra",
        "isis",
        "set",
    ],
    "norse": [
        "thor",
        "odin",
        "loki",
        "freyr",
    ],
    "atlantean": [
        "kronos",
        "oranos",
        "gaia",
    ],
    "chinese": [
        "fuxi",
        "nuwa",
        "shennong",
    ],
    "japanese": [
        "amaterasu",
        "tsukuyomi",
        "susanoo",
    ],
    "aztec": [
        "huitzilopochtli",
        "tezcatlipoca",
        "quetzalcoatl",
    ],
}

GOD_HUD_RING_FILES = {
    "gaia": "Hud_Ring_Atl_Gaia.png",
    "kronos": "Hud_Ring_Atl_Kronos.png",
    "oranos": "Hud_Ring_Atl_Oranos.png",
    "huitzilopochtli": "Hud_Ring_Azt_Huitzilopochtli.png",
    "huitlipochtli": "Hud_Ring_Azt_Huitzilopochtli.png",
    "quetzalcoatl": "Hud_Ring_Azt_Quetzalcoatl.png",
    "tezcatlipoca": "Hud_Ring_Azt_Tezcatlipoca.png",
    "fuxi": "Hud_Ring_Chi_Fuxi.png",
    "nuwa": "Hud_Ring_Chi_Nuwa.png",
    "nüwa": "Hud_Ring_Chi_Nuwa.png",
    "shennong": "Hud_Ring_Chi_Shennong.png",
    "isis": "Hud_Ring_Egy_Isis.png",
    "ra": "Hud_Ring_Egy_Ra.png",
    "set": "Hud_Ring_Egy_Set.png",
    "demeter": "Hud_Ring_Grk_Demeter.png",
    "hades": "Hud_Ring_Grk_Hades.png",
    "poseidon": "Hud_Ring_Grk_Poseidon.png",
    "zeus": "Hud_Ring_Grk_Zeus.png",
    "amaterasu": "Hud_Ring_Jpn_Amaterasu.png",
    "susanoo": "Hud_Ring_Jpn_Susanoo.png",
    "tsukuyomi": "Hud_Ring_Jpn_Tsukuyomi.png",
    "freyr": "Hud_Ring_Nor_Freyr.png",
    "loki": "Hud_Ring_Nor_Loki.png",
    "odin": "Hud_Ring_Nor_Odin.png",
    "thor": "Hud_Ring_Nor_Thor.png",
}

HUD_RING_BASE_PATH = "assets/images/pantheons/major_gods/hud/"
DEFAULT_GOAL_ICON_PATH = "assets/images/score_age_2.png"



PANTHEON_META = {
    "greek": {
        "name": "Greek",
        "description": "Olympian pantheon",
        "icon": "assets/images/pantheons/UI_god_pantheon_Greek.png",
        "background": "assets/images/backgrounds/background_greek.png",
    },
    "egyptian": {
        "name": "Egyptian",
        "description": "Desert pantheon",
        "icon": "assets/images/pantheons/UI_god_pantheon_egyptian.png",
        "background": "assets/images/backgrounds/background_egyptian.png",
    },
    "norse": {
        "name": "Norse",
        "description": "Northern pantheon",
        "icon": "assets/images/pantheons/UI_god_pantheon_Norse.png",
        "background": "assets/images/backgrounds/background_norse.png",
    },
    "atlantean": {
        "name": "Atlantean",
        "description": "Titan pantheon",
        "icon": "assets/images/pantheons/UI_god_pantheon_Atlantean.png",
        "background": "assets/images/backgrounds/background_atlantean.png",
    },
    "chinese": {
        "name": "Chinese",
        "description": "Celestial pantheon",
        "icon": "assets/images/pantheons/UI_god_pantheon_Chinese.png",
        "background": "assets/images/backgrounds/background_chinese.png",
    },
    "japanese": {
        "name": "Japanese",
        "description": "Heavenly Spear pantheon",
        "icon": "assets/images/pantheons/UI_god_pantheon_japanese.png",
        "background": "assets/images/backgrounds/background_japanese.png",
    },
    "aztec": {
        "name": "Aztec",
        "description": "Immortal Pillars pantheon",
        "icon": "assets/images/pantheons/UI_god_pantheon_Aztec.png",
        "background": "assets/images/backgrounds/background_aztec.png",
    },
}

GOD_META = {
    "zeus": {"name": "Zeus", "subtitle": "Lightning, pressure, and strong heroic timings.", "pantheon": "greek"},
    "hades": {"name": "Hades", "subtitle": "Defense, archers, and powerful scaling.", "pantheon": "greek"},
    "poseidon": {"name": "Poseidon", "subtitle": "Cavalry tempo, raids, and map control.", "pantheon": "greek"},
    "demeter": {"name": "Demeter", "subtitle": "Economy, myth support, and stable scaling.", "pantheon": "greek"},
    "ra": {"name": "Ra", "subtitle": "Empowered economy, priests, and scaling.", "pantheon": "egyptian"},
    "isis": {"name": "Isis", "subtitle": "Protection, monuments, and safe timings.", "pantheon": "egyptian"},
    "set": {"name": "Set", "subtitle": "Disruption, animals, and early pressure.", "pantheon": "egyptian"},
    "thor": {"name": "Thor", "subtitle": "Dwarven economy and powerful armory timing.", "pantheon": "norse"},
    "odin": {"name": "Odin", "subtitle": "Raiding, map control, and durable armies.", "pantheon": "norse"},
    "loki": {"name": "Loki", "subtitle": "Chaos pressure, myth tempo, and disruption.", "pantheon": "norse"},
    "freyr": {"name": "Freyr", "subtitle": "Fortified economy and strong late transitions.", "pantheon": "norse"},
    "kronos": {"name": "Kronos", "subtitle": "Ruler of the Titans.", "pantheon": "atlantean"},
    "oranos": {"name": "Oranos", "subtitle": "Lord of the Skies.", "pantheon": "atlantean"},
    "gaia": {"name": "Gaia", "subtitle": "Goddess of the Earth.", "pantheon": "atlantean"},
    "fuxi": {"name": "Fu Xi", "subtitle": "God of Civilization, Culture, and Heaven.", "pantheon": "chinese"},
    "nuwa": {"name": "Nüwa", "subtitle": "Goddess of Creation and the Earth.", "pantheon": "chinese"},
    "shennong": {"name": "Shennong", "subtitle": "God of Agriculture and Herbal Medicine.", "pantheon": "chinese"},
    "amaterasu": {"name": "Amaterasu", "subtitle": "Shrine economy, tempo, and polished scaling.", "pantheon": "japanese"},
    "tsukuyomi": {"name": "Tsukuyomi", "subtitle": "Fast pressure and aggressive openings.", "pantheon": "japanese"},
    "susanoo": {"name": "Susanoo", "subtitle": "Raids, disruption, and storm-driven attacks.", "pantheon": "japanese"},
    "huitzilopochtli": {"name": "Huitzilopochtli", "subtitle": "War pressure and decisive timings.", "pantheon": "aztec"},
    "tezcatlipoca": {"name": "Tezcatlipoca", "subtitle": "Favor tempo and volatile power spikes.", "pantheon": "aztec"},
    "quetzalcoatl": {"name": "Quetzalcoatl", "subtitle": "Flexible economy and myth support.", "pantheon": "aztec"},
}

GOD_ALIASES = {
    "nüwa": "nuwa",
    "nu-wa": "nuwa",
    "fu-xi": "fuxi",
    "huitlipochtli": "huitzilopochtli",
}


def is_build_order_admin(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)


def require_build_order_admin(user):
    if not is_build_order_admin(user):
        raise Http404

    return True


build_order_admin_required = user_passes_test(require_build_order_admin)


def normalize_slug(value):
    normalized = slugify(str(value or "").strip())
    return GOD_ALIASES.get(normalized, normalized)


def ensure_pantheon_exists(pantheon_slug):
    pantheon_slug = normalize_slug(pantheon_slug)
    meta = PANTHEON_META.get(
        pantheon_slug,
        {
            "name": pantheon_slug.replace("-", " ").title(),
            "description": "Age of Mythology: Retold pantheon",
            "icon": "",
            "background": "",
        },
    )

    pantheon, _created = Pantheon.objects.get_or_create(
        slug=pantheon_slug,
        defaults={
            "name": meta["name"],
            "description": meta.get("description", ""),
            "icon": meta.get("icon", ""),
            "background": meta.get("background", ""),
        },
    )

    return pantheon


def ensure_god_exists(god_slug):
    god_slug = normalize_slug(god_slug)

    existing_god = (
        MajorGod.objects
        .select_related("pantheon")
        .filter(slug=god_slug)
        .first()
    )

    if existing_god:
        return existing_god

    meta = GOD_META.get(god_slug)

    if not meta:
        return None

    pantheon = ensure_pantheon_exists(meta["pantheon"])

    god, _created = MajorGod.objects.get_or_create(
        slug=god_slug,
        defaults={
            "pantheon": pantheon,
            "name": meta["name"],
            "subtitle": meta.get("subtitle", ""),
            "title": meta.get("name", god_slug.replace("-", " ").title()),
            "focus": meta.get("focus", ""),
            "bonuses": meta.get("bonuses", []),
            "portrait": f"assets/images/gods/{god_slug}_portrait.png",
            "breakout_portrait": f"assets/images/gods/{god_slug}_breakoutportrait.png",
            "hud_ring": "",
        },
    )

    return god



GOD_DETAILS = {
    "zeus": {
        "focus": "Infantry and Heroes.",
        "bonuses": [
            "Starts with 10 Favor.",
            "Gains Favor 20% faster.",
            "Myth units cost 1 less population.",
            "Infantry do +60% damage to buildings.",
            "Hoplites move 15% faster.",
        ],
    },
    "hades": {
        "focus": "Ranged Soldiers and Buildings.",
        "bonuses": [
            "Chance for fallen humans to return as Shades.",
            "Myth units gain hit points each age.",
            "Ranged soldiers and heroes gain extra range and line of sight.",
            "Ranged fortifications gain extra range.",
            "Ballistics and Burning Pitch are researched instantly for free in their respective ages.",
        ],
    },
    "poseidon": {
        "focus": "Cavalry and Economy.",
        "bonuses": [
            "Militia spawn from razed buildings.",
            "Cavalry, Caravans, and Myth Units gain speed each age.",
            "Stables and Markets are cheaper.",
            "Market exchange rates are improved.",
            "A free Hippocampus respawns at the first Dock.",
        ],
    },
    "demeter": {
        "focus": "Expansion and Resource Gathering.",
        "bonuses": [
            "Herdables improve Favor gather rate when near a Temple.",
            "Town Centers and Village Centers spawn Herdables on age up.",
            "Buildings build faster when close to Gold mines.",
            "More Villagers can work on each Farm.",
            "Village Centers have additional hit points and increased attack per garrisoned Villager.",
        ],
    },
    "ra": {
        "focus": "Migdol Stronghold units and Empowerment.",
        "bonuses": [
            "Laborers gather from Berry Bushes faster.",
            "Camel Riders, Chariot Archers, and War Elephants gain hit points.",
            "Pharaoh-empowered Monuments empower nearby buildings.",
            "Priests can empower buildings.",
        ],
    },
    "isis": {
        "focus": "Technology.",
        "bonuses": [
            "Town Centers and Citadel Centers support +5 population.",
            "Monuments shield against enemy God Powers.",
            "Empowered Monuments heal nearby units and generate Favor faster.",
            "Technologies cost -10%.",
            "Obelisks cost -5 Gold and are built faster.",
        ],
    },
    "set": {
        "focus": "Barracks units.",
        "bonuses": [
            "Pharaohs can summon Animals of Set.",
            "Priests can convert wild animals.",
            "Spearmen, Axemen, and Slingers move faster.",
            "Barracks, Siege Works, and Migdol Strongholds cost less Gold.",
            "Monuments reduce the cost of units near Barracks and Migdol Strongholds.",
        ],
    },
    "thor": {
        "focus": "Dwarves and Armory.",
        "bonuses": [
            "Starts with Dwarves instead of Gatherers.",
            "Dwarves cost less Gold and gather Food and Wood efficiently.",
            "Dwarven Armory can be built and upgraded in any age.",
            "Armory upgrades cost less.",
            "Receives a free Dwarf for each Dwarven Armory upgrade.",
            "Can research extra Dwarven Armory upgrades.",
        ],
    },
    "odin": {
        "focus": "Great Hall units.",
        "bonuses": [
            "Gatherers and Dwarves hunt faster.",
            "Great Hall units generate Favor in battle.",
            "Human units and heroes regenerate hit points.",
            "Raven scouts spawn once the first Temple is built and respawn after being killed.",
        ],
    },
    "loki": {
        "focus": "Myth Units.",
        "bonuses": [
            "Damaging enemy units can spawn myth units.",
            "Human soldiers and heroes gain counter damage.",
            "Buildings are constructed faster.",
            "Ox Carts are cheaper.",
            "Transforming Gatherers and Dwarves into Berserks is cheaper.",
        ],
    },
    "freyr": {
        "focus": "Technology and Defense.",
        "bonuses": [
            "Has a defensive God Power that grows stronger each age.",
            "Technologies cost less Food, Wood, and Gold, but take longer to research.",
            "Hill Forts and Hill Fort units deal more damage.",
            "Repairing buildings is free.",
            "Gatherers and Dwarves can repair.",
        ],
    },
    "oranos": {
        "focus": "Vision and Mobility.",
        "bonuses": [
            "Citizens can build a new Sky Passage each age.",
            "Units can teleport between Sky Passages.",
            "All units have increased Line of Sight.",
            "Oracles generate more Favor at full Line of Sight.",
            "Damaged enemy units remain visible for a short duration.",
        ],
    },
    "gaia": {
        "focus": "Economy and Buildings.",
        "bonuses": [
            "Starts with Hero Citizens and promoting Citizens to heroes costs less.",
            "Economic Guild technologies are cheaper and can be researched an age earlier.",
            "Economic Buildings grow Lush.",
            "Lush heals friendly units and buildings.",
        ],
    },
    "kronos": {
        "focus": "Siege and Myth Units.",
        "bonuses": [
            "Can time-shift buildings to new locations.",
            "Buildings are constructed faster near Manors.",
            "Receives extra free myth units when advancing to the next age.",
            "Lost siege and myth units return part of their resource cost.",
        ],
    },
    "fuxi": {
        "focus": "Human Soldiers and Heroes.",
        "bonuses": [
            "God Blessing: Yin and Yang.",
            "On Favored Land, buildings research faster.",
            "On Favored Land, Military Camp and Machine Workshop additions cost less.",
            "Gains access to Nezha in the Classical Age.",
        ],
    },
    "nuwa": {
        "focus": "Peasants, Kuafus, and Defense.",
        "bonuses": [
            "God Blessing: Creator’s Auspice.",
            "On Favored Land, foundations automatically construct.",
            "Buildings spread Favored Land farther.",
            "Cavalry gain hit points.",
        ],
    },
    "shennong": {
        "focus": "Farming, Myth Units, and Healing.",
        "bonuses": [
            "God Blessing: Gift of Beasts.",
            "On Favored Land, Myth units regenerate hit points.",
            "Farms are available in the Archaic Age and build instantly on Favored Land.",
            "Farm upgrades are researched instantly for free in their respective ages.",
        ],
    },
    "amaterasu": {
        "focus": "Economy and Samurai.",
        "bonuses": [
            "Earns an increasing Gold trickle with each Bushido tier.",
            "Samurai and Onna-mushas earn 300% more XP outside of combat.",
            "Shrines increase the content of nearby resources, up to 140%.",
            "Samurai and Onna-mushas regenerate hit points, twice as fast in combat.",
        ],
    },
    "tsukuyomi": {
        "focus": "Technology, Shinobi, and Cavalry.",
        "bonuses": [
            "Increases Shinobi and Cavalry attack with each Bushido tier.",
            "Each technology researched grants Bushido XP.",
            "Advancing to the next Age is faster.",
            "A free Kitsune appears at the Temple each Age.",
        ],
    },
    "susanoo": {
        "focus": "Myth Units and God Powers.",
        "bonuses": [
            "Tributes a larger Favor reward with each Bushido tier.",
            "Myth units earn Bushido XP passively and through combat.",
            "Invoking a God Power makes others cheaper to reinvoke.",
            "Unit special abilities recharge faster.",
        ],
    },
    "huitzilopochtli": {
        "focus": "Conquest and Expansion.",
        "bonuses": [
            "Temples, Great Temples, Village Centers, and Town Centers refund part of their cost upon completion.",
            "Collecting tonalli earns resources in addition to Favor.",
            "Shorn Ones have more hit points and generate more tonalli in combat.",
        ],
    },
    "huitlipochtli": {
        "focus": "Conquest and Expansion.",
        "bonuses": [
            "Temples, Great Temples, Village Centers, and Town Centers refund part of their cost upon completion.",
            "Collecting tonalli earns resources in addition to Favor.",
            "Shorn Ones have more hit points and generate more tonalli in combat.",
        ],
    },
    "quetzalcoatl": {
        "focus": "Warrior Priests and Nobles Hut Warriors.",
        "bonuses": [
            "Warrior Priests generate Favor by performing Bloodletting at Temples.",
            "Calpullis and their additions cost less.",
            "Nobles Hut units gain hit points.",
            "Eagle Warriors gain range.",
        ],
    },
    "tezcatlipoca": {
        "focus": "Defense and Myth Units.",
        "bonuses": [
            "Lost Myth Units can spawn an Obsidian Shard that summons a free Myth Unit if it survives.",
            "Tzompantli Towers and Traps are built faster and inflict more damage.",
            "Devoting Settlers grants more Favor each age.",
            "Jaguar Riders are unlocked an age earlier.",
        ],
    },
}


def normalize_details(details):
    if not isinstance(details, dict):
        return None
    focus = str(details.get("focus") or "").strip()
    bonuses = [str(bonus).strip() for bonus in (details.get("bonuses") or []) if str(bonus).strip()]
    if not focus and not bonuses:
        return None
    return {"focus": focus, "bonuses": bonuses}


def fallback_details_for_god(god_slug):
    return normalize_details(GOD_DETAILS.get(normalize_slug(god_slug)))


def merged_details_for_god(god_slug, current_details=None, title=""):
    fallback = fallback_details_for_god(god_slug)
    current = normalize_details(current_details)
    if current:
        return {"title": title or current_details.get("title", ""), **current}
    if fallback:
        return {"title": title or "", **fallback}
    return {"title": title or "", "focus": "", "bonuses": []}

def absolute_url(request, path):
    return request.build_absolute_uri(path)


def strip_manifest_hash(path):
    value = str(path or "").strip()

    if not value:
        return ""

    head, separator, tail = value.rpartition("/")
    cleaned_tail = re.sub(r"\.([0-9a-f]{12})(\.[^.]+)$", r"\2", tail, flags=re.IGNORECASE)

    if not separator:
        return cleaned_tail

    return f"{head}{separator}{cleaned_tail}"


def safe_static_url(path):
    value = str(path or "").strip()

    if not value:
        return ""

    try:
        return static(value)
    except ValueError:
        return ""


def asset_url(path, fallback=""):
    value = str(path or "").strip()

    if not value:
        value = str(fallback or "").strip()

    if not value:
        return ""

    if value.startswith(("http://", "https://", "/static/")):
        return value

    if value.startswith("static/"):
        value = value.replace("static/", "", 1)

    while value.startswith("../"):
        value = value[3:]

    return safe_static_url(strip_manifest_hash(value).lstrip("/"))


def static_relative_path(path):
    value = str(path or "").strip()

    if not value or value.startswith(("http://", "https://", "data:")):
        return ""

    if value.startswith("/static/"):
        value = value.replace("/static/", "", 1)
    elif value.startswith("static/"):
        value = value.replace("static/", "", 1)

    while value.startswith("../"):
        value = value[3:]

    return strip_manifest_hash(value.lstrip("/"))


def resolve_static_asset_path(path):
    relative_path = static_relative_path(path)

    if not relative_path:
        return ""

    static_root = settings.BASE_DIR / "static"
    current_path = static_root
    resolved_parts = []

    for part in relative_path.split("/"):
        if not part:
            continue

        if not current_path.is_dir():
            return relative_path

        matches = {
            child.name.lower(): child.name
            for child in current_path.iterdir()
        }
        resolved_part = matches.get(part.lower())

        if not resolved_part:
            return relative_path

        resolved_parts.append(resolved_part)
        current_path = current_path / resolved_part

    return "/".join(resolved_parts)


def static_asset_url(path):
    relative_path = resolve_static_asset_path(path)
    return safe_static_url(relative_path) if relative_path else ""


def optimized_static_asset_url(path, variant=""):
    relative_path = resolve_static_asset_path(path)

    if not relative_path.startswith("assets/images/") or not relative_path.endswith(".png"):
        return ""

    optimized_path = relative_path.replace("assets/images/", "assets/optimized/images/", 1)
    optimized_path = optimized_path.removesuffix(".png") + f"{variant}.webp"

    if not (settings.BASE_DIR / "static" / optimized_path).exists():
        return ""

    return safe_static_url(optimized_path)


def god_portrait_url(god_slug):
    return static_asset_url(f"assets/images/gods/{god_slug}_portrait.png")


def god_hud_ring_url(god=None, god_slug=""):
    resolved_slug = normalize_slug(god.slug if god else god_slug)

    if resolved_slug in GOD_HUD_RING_FILES:
        return asset_url(f"{HUD_RING_BASE_PATH}{GOD_HUD_RING_FILES[resolved_slug]}")

    if god and god.hud_ring:
        return asset_url(god.hud_ring)

    return asset_url(f"{HUD_RING_BASE_PATH}Hud_Ring_Gauge.png")


def build_detail_url(build):
    return f"/builds/{build.slug}/?god={build.major_god.slug}"


def step_kind(step):
    value = normalize_slug(step.type or "step")

    if value in {"phase", "major", "major-milestone", "milestone-major"}:
        return "milestone"

    if value in {"minor", "minor-milestone", "milestone-minor"}:
        return "minor_milestone"

    if value == "milestone":
        return "milestone"

    return "step"


def build_step_rows(build):
    rows = []

    if not build:
        return rows

    for step in build.steps.all():
        kind = step_kind(step)

        resources = [
            {"key": "food", "label": "Food", "value": step.food},
            {"key": "wood", "label": "Wood", "value": step.wood},
            {"key": "gold", "label": "Gold", "value": step.gold},
            {"key": "favor", "label": "Favor", "value": step.favor},
            {"key": "pop", "label": "Pop", "value": step.pop},
        ]
        resources = [item for item in resources if str(item["value"] or "").strip()]

        split_items = [
            {"key": "food", "label": "Food", "value": step.split_food},
            {"key": "wood", "label": "Wood", "value": step.split_wood},
            {"key": "gold", "label": "Gold", "value": step.split_gold},
            {"key": "favor", "label": "Favor", "value": step.split_favor},
            {"key": "pop", "label": "Pop", "value": step.split_pop},
        ]
        split_items = [item for item in split_items if str(item["value"] or "").strip() and str(item["value"] or "") != "0"]

        rows.append(
            {
                "kind": kind,
                "is_step": kind == "step",
                "is_milestone": kind in {"milestone", "minor_milestone"},
                "is_minor_milestone": kind == "minor_milestone",
                "time": step.time,
                "label": step.label,
                "action": step.action,
                "note": step.note,
                "food": step.food,
                "wood": step.wood,
                "gold": step.gold,
                "favor": step.favor,
                "pop": step.pop,
                "resources": resources,
                "split_items": split_items,
            }
        )

    return rows


def home(request):
    return render(
        request,
        "builds/home.html",
        {
            "canonical_url": absolute_url(request, reverse("builds:home")),
            "meta_description": (
                "Browse Age of Mythology: Retold build orders by pantheon and major god, "
                "including openings, timings, transitions, and strategy notes."
            ),
        },
    )


def god_detail(request, god_slug):
    god = (
        MajorGod.objects
        .select_related("pantheon")
        .filter(slug=god_slug)
        .first()
    )

    god_name = god.name if god else god_slug.replace("-", " ").replace("_", " ").title()
    pantheon_name = god.pantheon.name if god and god.pantheon else "Age of Mythology: Retold"
    description = (
        f"{god_name} build orders for Age of Mythology: Retold, including openings, "
        "timing attacks, economy plans, and matchup notes."
    )

    return render(
        request,
        "builds/god_detail.html",
        {
            "god_slug": god_slug,
            "god": god,
            "god_name": god_name,
            "pantheon_name": pantheon_name,
            "canonical_url": absolute_url(request, f"/gods/{god_slug}/"),
            "meta_description": description,
        },
    )


def build_detail(request, build_slug):
    requested_god_slug = normalize_slug(request.GET.get("god") or "")

    build_queryset = (
        BuildOrder.objects
        .select_related("major_god", "major_god__pantheon")
        .prefetch_related("steps")
        .filter(slug=build_slug, is_published=True)
    )

    if requested_god_slug:
        build_queryset = build_queryset.filter(major_god__slug=requested_god_slug)

    build = build_queryset.first()

    sibling_builds = []
    current_god = build.major_god if build else None

    if current_god:
        sibling_builds = list(
            BuildOrder.objects
            .select_related("major_god")
            .filter(major_god=current_god, is_published=True)
            .order_by("title")
        )

    if build:
        title = build.title
        god_name = build.major_god.name
        description = (
            build.summary
            or build.subtitle
            or f"{title} build order for {god_name} in Age of Mythology: Retold, with timings and villager assignments."
        )
        canonical_path = f"/builds/{build.slug}/"
        build_portrait = asset_url(
            build.portrait,
            f"assets/images/gods/{build.major_god.slug}_portrait.png",
        )
        goal_icon = asset_url(build.goal_icon, DEFAULT_GOAL_ICON_PATH)
        hud_ring = god_hud_ring_url(build.major_god)
        build_portrait_webp = optimized_static_asset_url(build_portrait, ".card")
        goal_icon_webp = optimized_static_asset_url(goal_icon)
        hud_ring_webp = optimized_static_asset_url(hud_ring)
        god_overview_url = f"/gods/{build.major_god.slug}/"
        back_to_builds_url = f"/build_orders/?pantheon={build.major_god.pantheon.slug}"
        editor_url = f"/editor/?id={build.slug}&god={build.major_god.slug}"
    else:
        title = build_slug.replace("-", " ").replace("_", " ").title()
        god_name = "Age of Mythology: Retold"
        description = f"Age of Mythology: Retold build order details for {title}."
        canonical_path = f"/builds/{build_slug}/"
        build_portrait = god_portrait_url(requested_god_slug) if requested_god_slug else ""
        goal_icon = asset_url(DEFAULT_GOAL_ICON_PATH)
        hud_ring = god_hud_ring_url(god_slug=requested_god_slug)
        build_portrait_webp = optimized_static_asset_url(build_portrait, ".card")
        goal_icon_webp = optimized_static_asset_url(goal_icon)
        hud_ring_webp = optimized_static_asset_url(hud_ring)
        god_overview_url = "/build_orders/"
        back_to_builds_url = "/build_orders/"
        editor_url = f"/editor/?id={build_slug}"

    return render(
        request,
        "builds/build_detail.html",
        {
            "build_slug": build_slug,
            "build_order": build,
            "build_title": title,
            "god_name": god_name,
            "canonical_url": absolute_url(request, canonical_path),
            "meta_description": description,
            "build_portrait_url": build_portrait,
            "build_portrait_webp_url": build_portrait_webp,
            "goal_icon_url": goal_icon,
            "goal_icon_webp_url": goal_icon_webp,
            "god_hud_ring_url": hud_ring,
            "god_hud_ring_webp_url": hud_ring_webp,
            "god_overview_url": god_overview_url,
            "back_to_builds_url": back_to_builds_url,
            "editor_url": editor_url,
            "sibling_builds": sibling_builds,
            "build_step_rows": build_step_rows(build),
        },
    )


@build_order_admin_required
def editor(request):
    return render(
        request,
        "builds/editor.html",
        {
            "canonical_url": absolute_url(request, "/editor/"),
            "meta_description": "Create and manage Age of Mythology: Retold build orders for Prostagma?",
            "meta_robots": "noindex, nofollow",
        },
    )



def normalize_fallback_build(build, god_slug, pantheon_slug):
    """Return a JSON-safe fallback build using the same shape as data_js()."""
    payload = dict(build or {})
    payload.setdefault("id", payload.get("slug") or "")
    payload.setdefault("slug", payload.get("id") or "")
    payload.setdefault("title", "Untitled Build Order")
    payload.setdefault("subtitle", payload.get("summary") or "")
    payload.setdefault("detailSubtitle", payload.get("subtitle") or payload.get("summary") or "")
    payload.setdefault("summary", "")
    payload.setdefault("meta", "")
    payload.setdefault("goalLabel", "Goal")
    payload.setdefault("goalText", payload.get("meta") or "Build Order")
    payload.setdefault("goalIcon", static_asset_url("assets/images/score_age_2.png"))
    payload.setdefault("portrait", static_asset_url(f"assets/images/gods/{god_slug}_portrait.png"))
    payload["goalIcon"] = static_asset_url(payload.get("goalIcon")) or payload.get("goalIcon", "")
    payload["portrait"] = static_asset_url(payload.get("portrait")) or payload.get("portrait", "")
    payload.setdefault("sourceGodId", god_slug)
    payload.setdefault("sourcePantheonId", pantheon_slug)
    payload.setdefault("steps", [])
    return payload


def normalize_fallback_god(god, god_slug):
    clean_god = dict(god or {})
    clean_god.setdefault("slug", god_slug)
    clean_god.setdefault("subtitle", clean_god.get("subtitle") or "")
    clean_god.setdefault("portrait", f"/static/assets/images/gods/{god_slug}_portrait.png")
    clean_god.setdefault("breakoutPortrait", f"/static/assets/images/gods/{god_slug}_breakoutportrait.png")
    clean_god.setdefault("hudRing", "")
    clean_god["portrait"] = static_asset_url(clean_god.get("portrait")) or clean_god.get("portrait", "")
    clean_god["breakoutPortrait"] = static_asset_url(clean_god.get("breakoutPortrait")) or clean_god.get("breakoutPortrait", "")
    clean_god["hudRing"] = static_asset_url(clean_god.get("hudRing")) or clean_god.get("hudRing", "")
    clean_god["details"] = merged_details_for_god(
        god_slug,
        clean_god.get("details"),
        clean_god.get("title") or clean_god.get("name") or "",
    )
    return clean_god


def normalize_fallback_pantheon(pantheon, pantheon_slug, gods):
    return {
        "id": pantheon_slug,
        "slug": pantheon_slug,
        "name": pantheon.get("name") or pantheon_slug.title(),
        "description": pantheon.get("description") or pantheon.get("subtitle") or "",
        "icon": static_asset_url(pantheon.get("icon") or pantheon.get("image") or ""),
        "background": static_asset_url(pantheon.get("background") or ""),
        "gods": gods,
    }


def merge_fallback_build_data(pantheons_payload, build_orders_payload):
    """
    Keep database-backed data as the source of truth, but fill holes from
    static/js/data.js so the archive never renders an empty carousel or empty
    god page just because the local DB has not been seeded yet.
    """
    fallback_pantheons = FALLBACK_AOM_DATA.get("pantheons") or []
    fallback_build_orders = FALLBACK_AOM_DATA.get("buildOrders") or {}

    if not pantheons_payload:
        fallback_payload = []
        fallback_build_payload = {}

        for pantheon in fallback_pantheons:
            pantheon_slug = pantheon.get("id") or pantheon.get("slug") or ""
            gods = []

            for god in pantheon.get("gods") or []:
                god_slug = god.get("id") or god.get("slug") or ""
                gods.append(normalize_fallback_god(god, god_slug))

                fallback_build_payload[god_slug] = [
                    normalize_fallback_build(build, god_slug, pantheon_slug)
                    for build in fallback_build_orders.get(god_slug, [])
                ]

            fallback_payload.append(normalize_fallback_pantheon(pantheon, pantheon_slug, gods))

        return fallback_payload, fallback_build_payload

    pantheon_lookup = {pantheon.get("id") or pantheon.get("slug"): pantheon for pantheon in pantheons_payload}

    for fallback_pantheon in fallback_pantheons:
        pantheon_slug = fallback_pantheon.get("id") or fallback_pantheon.get("slug") or ""
        existing_pantheon = pantheon_lookup.get(pantheon_slug)

        if not existing_pantheon:
            gods = []
            for god in fallback_pantheon.get("gods") or []:
                god_slug = god.get("id") or god.get("slug") or ""
                gods.append(normalize_fallback_god(god, god_slug))

                build_orders_payload.setdefault(
                    god_slug,
                    [normalize_fallback_build(build, god_slug, pantheon_slug) for build in fallback_build_orders.get(god_slug, [])],
                )

            pantheons_payload.append(normalize_fallback_pantheon(fallback_pantheon, pantheon_slug, gods))
            continue

        existing_gods = existing_pantheon.setdefault("gods", [])
        existing_god_slugs = {god.get("id") or god.get("slug") for god in existing_gods}

        for fallback_god in fallback_pantheon.get("gods") or []:
            god_slug = fallback_god.get("id") or fallback_god.get("slug") or ""

            if god_slug not in existing_god_slugs:
                existing_gods.append(normalize_fallback_god(fallback_god, god_slug))

            if not build_orders_payload.get(god_slug):
                fallback_builds = fallback_build_orders.get(god_slug, [])
                if fallback_builds:
                    build_orders_payload[god_slug] = [
                        normalize_fallback_build(build, god_slug, pantheon_slug)
                        for build in fallback_builds
                    ]

    for pantheon in pantheons_payload:
        for god in pantheon.get("gods") or []:
            god_slug = god.get("id") or god.get("slug") or ""
            god["details"] = merged_details_for_god(god_slug, god.get("details"), god.get("title") or god.get("name") or "")

    return pantheons_payload, build_orders_payload


def merge_fallback_pantheon_data(pantheons_payload):
    fallback_pantheons = FALLBACK_AOM_DATA.get("pantheons") or []

    if not pantheons_payload:
        fallback_payload = []

        for pantheon in fallback_pantheons:
            pantheon_slug = pantheon.get("id") or pantheon.get("slug") or ""
            gods = [
                normalize_fallback_god(god, god.get("id") or god.get("slug") or "")
                for god in pantheon.get("gods") or []
            ]
            fallback_payload.append(normalize_fallback_pantheon(pantheon, pantheon_slug, gods))

        return fallback_payload

    pantheon_lookup = {pantheon.get("id") or pantheon.get("slug"): pantheon for pantheon in pantheons_payload}

    for fallback_pantheon in fallback_pantheons:
        pantheon_slug = fallback_pantheon.get("id") or fallback_pantheon.get("slug") or ""
        existing_pantheon = pantheon_lookup.get(pantheon_slug)

        if not existing_pantheon:
            gods = [
                normalize_fallback_god(god, god.get("id") or god.get("slug") or "")
                for god in fallback_pantheon.get("gods") or []
            ]
            pantheons_payload.append(normalize_fallback_pantheon(fallback_pantheon, pantheon_slug, gods))
            continue

        existing_gods = existing_pantheon.setdefault("gods", [])
        existing_god_slugs = {god.get("id") or god.get("slug") for god in existing_gods}

        for fallback_god in fallback_pantheon.get("gods") or []:
            god_slug = fallback_god.get("id") or fallback_god.get("slug") or ""

            if god_slug not in existing_god_slugs:
                existing_gods.append(normalize_fallback_god(fallback_god, god_slug))

    for pantheon in pantheons_payload:
        for god in pantheon.get("gods") or []:
            god_slug = god.get("id") or god.get("slug") or ""
            god["details"] = merged_details_for_god(god_slug, god.get("details"), god.get("title") or god.get("name") or "")

    return pantheons_payload


def god_payload(god):
    return {
        "id": god.slug,
        "slug": god.slug,
        "name": god.name,
        "subtitle": god.subtitle,
        "portrait": static_asset_url(god.portrait),
        "breakoutPortrait": static_asset_url(god.breakout_portrait),
        "hudRing": static_asset_url(god.hud_ring),
        "details": merged_details_for_god(
            god.slug,
            {
                "title": god.title,
                "focus": god.focus,
                "bonuses": god.bonuses or [],
            },
            god.title,
        ),
    }


def build_summary_payload(build, god):
    return {
        "id": build.slug,
        "slug": build.slug,
        "title": build.title,
        "subtitle": build.subtitle,
        "detailSubtitle": build.subtitle,
        "summary": build.summary,
        "meta": build.meta,
        "goalLabel": build.goal_label,
        "goalText": build.goal_text,
        "goalIcon": static_asset_url(build.goal_icon),
        "portrait": static_asset_url(build.portrait),
        "sourceGodId": god.slug,
        "sourcePantheonId": god.pantheon.slug,
    }


def build_full_payload(build, god):
    payload = build_summary_payload(build, god)
    payload["steps"] = [
        {
            "type": step.type,
            "label": step.label,
            "time": step.time,
            "food": step.food,
            "wood": step.wood,
            "gold": step.gold,
            "favor": step.favor,
            "pop": step.pop,
            "action": step.action,
            "note": step.note,
            "split": {
                "food": step.split_food,
                "wood": step.split_wood,
                "gold": step.split_gold,
                "favor": step.split_favor,
                "pop": step.split_pop,
            },
        }
        for step in build.steps.all()
    ]
    return payload


def pantheon_payload(pantheon, gods_payload):
    return {
        "id": pantheon.slug,
        "slug": pantheon.slug,
        "name": pantheon.name,
        "description": pantheon.description,
        "icon": static_asset_url(pantheon.icon),
        "background": static_asset_url(pantheon.background),
        "gods": gods_payload,
    }


def ordered_pantheon_queryset(prefetch=None):
    pantheon_order_lookup = {
        slug: index
        for index, slug in enumerate(PANTHEON_ORDER)
    }
    queryset = Pantheon.objects.all()

    if prefetch is not None:
        queryset = queryset.prefetch_related(prefetch)

    return sorted(
        queryset,
        key=lambda pantheon: pantheon_order_lookup.get(pantheon.slug, 999),
    )


def ordered_gods_for_pantheon(pantheon):
    god_order_lookup = {
        slug: index
        for index, slug in enumerate(GOD_ORDER.get(pantheon.slug, []))
    }

    return sorted(
        getattr(pantheon, "prefetched_major_gods", []),
        key=lambda god: god_order_lookup.get(god.slug, 999),
    )


def fallback_god_with_pantheon(god_slug):
    for pantheon in FALLBACK_AOM_DATA.get("pantheons") or []:
        pantheon_slug = pantheon.get("id") or pantheon.get("slug") or ""

        for god in pantheon.get("gods") or []:
            if (god.get("id") or god.get("slug")) == god_slug:
                return pantheon, pantheon_slug, god

    return None, "", None


def fallback_build_summaries(god_slug, pantheon_slug):
    return [
        {
            key: value
            for key, value in normalize_fallback_build(build, god_slug, pantheon_slug).items()
            if key != "steps"
        }
        for build in (FALLBACK_AOM_DATA.get("buildOrders") or {}).get(god_slug, [])
    ]


def home_data_json(request):
    major_gods = Prefetch(
        "major_gods",
        queryset=MajorGod.objects.all(),
        to_attr="prefetched_major_gods",
    )

    pantheons_payload = []

    for pantheon in ordered_pantheon_queryset(major_gods):
        gods_payload = [
            god_payload(god)
            for god in ordered_gods_for_pantheon(pantheon)
        ]
        pantheons_payload.append(pantheon_payload(pantheon, gods_payload))

    pantheons_payload = merge_fallback_pantheon_data(pantheons_payload)

    return JsonResponse({"pantheons": pantheons_payload})


def god_data_json(request, god_slug):
    resolved_god_slug = normalize_slug(god_slug)
    published_builds = Prefetch(
        "build_orders",
        queryset=(
            BuildOrder.objects
            .filter(is_published=True)
            .order_by("title")
        ),
        to_attr="published_build_orders",
    )

    god = (
        MajorGod.objects
        .select_related("pantheon")
        .prefetch_related(published_builds)
        .filter(slug=resolved_god_slug)
        .first()
    )

    if god:
        builds_payload = [
            build_summary_payload(build, god)
            for build in getattr(god, "published_build_orders", [])
        ]

        if not builds_payload:
            builds_payload = fallback_build_summaries(god.slug, god.pantheon.slug)

        return JsonResponse(
            {
                "pantheons": [pantheon_payload(god.pantheon, [god_payload(god)])],
                "buildOrders": {god.slug: builds_payload},
            }
        )

    fallback_pantheon, pantheon_slug, fallback_god = fallback_god_with_pantheon(resolved_god_slug)

    if not fallback_god:
        return JsonResponse({"pantheons": [], "buildOrders": {resolved_god_slug: []}})

    normalized_god = normalize_fallback_god(fallback_god, resolved_god_slug)
    normalized_pantheon = normalize_fallback_pantheon(
        fallback_pantheon or {},
        pantheon_slug,
        [normalized_god],
    )

    return JsonResponse(
        {
            "pantheons": [normalized_pantheon],
            "buildOrders": {
                resolved_god_slug: fallback_build_summaries(resolved_god_slug, pantheon_slug),
            },
        }
    )


def data_js(request):
    pantheons_payload = []
    build_orders_payload = {}

    pantheon_order_lookup = {
        slug: index
        for index, slug in enumerate(PANTHEON_ORDER)
    }

    published_builds = Prefetch(
        "build_orders",
        queryset=(
            BuildOrder.objects
            .filter(is_published=True)
            .prefetch_related("steps")
            .order_by("title")
        ),
        to_attr="published_build_orders",
    )

    major_gods = Prefetch(
        "major_gods",
        queryset=(
            MajorGod.objects
            .prefetch_related(published_builds)
        ),
        to_attr="prefetched_major_gods",
    )

    pantheon_queryset = sorted(
        Pantheon.objects.prefetch_related(major_gods),
        key=lambda pantheon: pantheon_order_lookup.get(pantheon.slug, 999),
    )

    for pantheon in pantheon_queryset:
        gods_payload = []

        god_order_lookup = {
            slug: index
            for index, slug in enumerate(GOD_ORDER.get(pantheon.slug, []))
        }

        god_queryset = sorted(
            getattr(pantheon, "prefetched_major_gods", []),
            key=lambda god: god_order_lookup.get(god.slug, 999),
        )

        for god in god_queryset:
            gods_payload.append(god_payload(god))

            build_orders_payload[god.slug] = [
                build_full_payload(build, god)
                for build in getattr(god, "published_build_orders", [])
            ]

        pantheons_payload.append(pantheon_payload(pantheon, gods_payload))

    pantheons_payload, build_orders_payload = merge_fallback_build_data(
        pantheons_payload,
        build_orders_payload,
    )

    return JsonResponse(
        {
            "pantheons": pantheons_payload,
            "buildOrders": build_orders_payload,
        }
    )



def clean_static_path(value):
    value = str(value or "").strip()

    if not value:
        return ""

    for prefix in ("/static/", "static/"):
        if value.startswith(prefix):
            return strip_manifest_hash(value.replace(prefix, "", 1))

    while value.startswith("../"):
        value = value[3:]

    if value.startswith("/"):
        value = value[1:]

    return strip_manifest_hash(value)


def safe_int(value):
    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return 0


def serialize_build_for_editor(build):
    return {
        "id": build.slug,
        "title": build.title,
        "subtitle": build.subtitle,
        "detailSubtitle": build.subtitle,
        "summary": build.summary,
        "meta": build.meta,
        "goalLabel": build.goal_label,
        "goalText": build.goal_text,
        "goalIcon": static_asset_url(build.goal_icon),
        "portrait": static_asset_url(build.portrait),
        "sourceGodId": build.major_god.slug,
        "sourcePantheonId": build.major_god.pantheon.slug,
        "steps": [
            {
                "type": step.type,
                "label": step.label,
                "time": step.time,
                "food": step.food,
                "wood": step.wood,
                "gold": step.gold,
                "favor": step.favor,
                "pop": step.pop,
                "action": step.action,
                "note": step.note,
                "split": {
                    "food": step.split_food,
                    "wood": step.split_wood,
                    "gold": step.split_gold,
                    "favor": step.split_favor,
                    "pop": step.split_pop,
                },
            }
            for step in build.steps.all().order_by("order")
        ],
    }


@build_order_admin_required
@require_POST
def api_save_build(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse(
            {
                "ok": False,
                "error": "Invalid JSON.",
            },
            status=400,
        )

    god_slug = data.get("sourceGodId") or request.GET.get("god")

    if not god_slug:
        return JsonResponse(
            {
                "ok": False,
                "error": "Missing sourceGodId.",
            },
            status=400,
        )

    god_slug = normalize_slug(god_slug)
    god = ensure_god_exists(god_slug)

    if not god:
        return JsonResponse(
            {
                "ok": False,
                "error": f"Unknown god: {god_slug}",
            },
            status=404,
        )

    title = str(data.get("title") or "").strip() or "Untitled Build Order"
    requested_slug = str(data.get("id") or data.get("slug") or "").strip()
    build_slug = slugify(requested_slug) or slugify(title) or "untitled-build-order"

    build, _created = BuildOrder.objects.update_or_create(
        major_god=god,
        slug=build_slug,
        defaults={
            "title": title,
            "subtitle": data.get("subtitle") or data.get("detailSubtitle") or "",
            "summary": data.get("summary") or "",
            "meta": data.get("meta") or "",
            "goal_label": data.get("goalLabel") or "Goal",
            "goal_text": data.get("goalText") or data.get("meta") or "Build Order",
            "goal_icon": clean_static_path(data.get("goalIcon") or "assets/images/score_age_2.png"),
            "portrait": clean_static_path(
                data.get("portrait") or f"assets/images/gods/{god.slug}_portrait.png"
            ),
            "is_published": True,
        },
    )

    build.steps.all().delete()

    for index, step_data in enumerate(data.get("steps") or [], start=1):
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

    build = (
        BuildOrder.objects
        .select_related("major_god", "major_god__pantheon")
        .prefetch_related("steps")
        .get(pk=build.pk)
    )

    return JsonResponse(
        {
            "ok": True,
            "build": serialize_build_for_editor(build),
        }
    )


@build_order_admin_required
@require_POST
def api_delete_build(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse(
            {
                "ok": False,
                "error": "Invalid JSON.",
            },
            status=400,
        )

    build_slug = data.get("id") or data.get("slug")
    god_slug = data.get("sourceGodId") or data.get("god")

    if not build_slug:
        return JsonResponse(
            {
                "ok": False,
                "error": "Missing build id.",
            },
            status=400,
        )

    query = BuildOrder.objects.filter(slug=build_slug)

    if god_slug:
        query = query.filter(major_god__slug=god_slug)

    deleted_count, _ = query.delete()

    return JsonResponse(
        {
            "ok": True,
            "deleted": deleted_count,
        }
    )
