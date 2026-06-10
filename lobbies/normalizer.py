import re
from typing import Any

from .decoder import decode_options, decode_slotinfo
from .mappings import (
    AI_DIFFICULTY,
    ENDING_AGE,
    GAME_MODE,
    GAME_SPEED,
    GOD_BY_RACE_ID,
    MAP_SIZE,
    MAP_VISIBILITY,
    STARTING_AGE,
    STARTING_RESOURCES,
    TEAM_MODE,
    VICTORY_CONDITION,
)



def first_present_value(source: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        if key in source and source.get(key) is not None:
            return source.get(key)

    return None


def label_or_none(mapping: dict[int, str], value: Any) -> str | None:
    if value is None:
        return None

    return label_from_mapping(mapping, value)


def normalize_game_type_label(game_mode_id: Any) -> str:
    label = label_from_mapping(GAME_MODE, game_mode_id)

    if label == "Supremacy":
        return "Standard"

    return label


def normalize_victory_condition(decoded_options: dict[str, Any]) -> tuple[str | None, Any]:
    direct_value = first_present_value(
        decoded_options,
        [
            "mGameVictoryCondition",
            "mVictoryCondition",
            "mVictoryMode",
            "mGameWinCondition",
            "mWinCondition",
            "mGameRules",
        ],
    )

    if direct_value is not None:
        return label_from_mapping(VICTORY_CONDITION, direct_value), direct_value

    if decoded_options.get("mRuleKoth") == 1:
        return "King of the Hill", "mRuleKoth"

    if decoded_options.get("mRuleRegicide") == 1:
        return "Regicide", "mRuleRegicide"

    if decoded_options.get("mRuleSuddenDeath") == 1:
        return "Sudden Death", "mRuleSuddenDeath"

    return "Standard", 0


def normalize_team_mode(decoded_options: dict[str, Any]) -> tuple[str | None, Any]:
    direct_value = first_present_value(
        decoded_options,
        [
            "mTeamMode",
            "mGameTeamMode",
            "mLobbyTeamMode",
            "mDiplomacyMode",
        ],
    )

    if direct_value is None:
        return None, None

    return label_from_mapping(TEAM_MODE, direct_value), direct_value

def label_from_mapping(
    mapping: dict[int, str],
    value: Any,
    unknown_prefix: str = "Unknown",
) -> str:
    if value in mapping:
        return mapping[value]

    return f"{unknown_prefix} ({value})"


def clean_display_name(value: str | None) -> str:
    if not value:
        return ""

    cleaned = re.sub(r"<color[^>]*>", "", value)
    return cleaned.strip()


def format_map_name(raw_map_name: str | None, decoded_map_name: str | None) -> str:
    candidate = decoded_map_name or raw_map_name or ""

    if candidate.startswith("rm_"):
        candidate = candidate[3:]

    if candidate.startswith("set_"):
        candidate = candidate[4:]

    candidate = candidate.replace("_", " ").strip()

    if not candidate:
        return "Unknown"

    return candidate.title()


def classify_slot(slot: dict[str, Any]) -> str:
    status = slot.get("status")
    profile_id = get_profile_id_from_slot(slot)

    if status == 1:
        return "Closed"

    if status == 2:
        return "AI"

    if status == 0 and profile_id is not None:
        return "Human player"

    if status == 0 and profile_id is None:
        return "Open human slot"

    return "Unknown"


def summarize_slots(slots: list[dict[str, Any]]) -> dict[str, int]:
    slot_types = [classify_slot(slot) for slot in slots]

    return {
        "human_players": slot_types.count("Human player"),
        "open_human_slots": slot_types.count("Open human slot"),
        "ai_players": slot_types.count("AI"),
        "closed_slots": slot_types.count("Closed"),
        "unknown_slots": slot_types.count("Unknown"),
    }


def build_avatar_lookup(data: dict[str, Any]) -> dict[int, dict[str, Any]]:
    avatars = data.get("avatars", [])

    return {
        avatar["profile_id"]: avatar
        for avatar in avatars
        if avatar.get("profile_id") is not None
    }


def build_matchmember_lookup(raw_lobby: dict[str, Any]) -> dict[int, dict[str, Any]]:
    members = raw_lobby.get("matchmembers", [])

    return {
        member["profile_id"]: member
        for member in members
        if member.get("profile_id") is not None
    }


def get_profile_id_from_slot(slot: dict[str, Any]) -> int | None:
    possible_values = [
        slot.get("profileInfo.id"),
        slot.get("profile_info.id"),
        slot.get("profile_id"),
        slot.get("profileId"),
        slot.get("profileID"),
        slot.get("user_id"),
        slot.get("userId"),
        slot.get("rlUserId"),
        slot.get("rl_user_id"),
    ]

    profile_info = slot.get("profileInfo")
    if isinstance(profile_info, dict):
        possible_values.extend(
            [
                profile_info.get("id"),
                profile_info.get("profile_id"),
                profile_info.get("profileId"),
            ]
        )

    profile_info_snake = slot.get("profile_info")
    if isinstance(profile_info_snake, dict):
        possible_values.extend(
            [
                profile_info_snake.get("id"),
                profile_info_snake.get("profile_id"),
                profile_info_snake.get("profileId"),
            ]
        )

    for value in possible_values:
        if value is None or value == "":
            continue

        try:
            profile_id = int(value)
        except (TypeError, ValueError):
            continue

        if profile_id >= 0:
            return profile_id

    return None


def get_ordered_matchmembers(raw_lobby: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        member
        for member in raw_lobby.get("matchmembers", [])
        if member.get("profile_id") is not None
    ]


def normalize_rating(raw_ranking: Any) -> int | None:
    if raw_ranking is None:
        return None

    try:
        ranking = int(raw_ranking)
    except (TypeError, ValueError):
        return None

    if ranking < 0:
        return None

    return ranking


def get_god_name(race_id: Any, participant_type: str) -> str:
    if participant_type == "Open":
        return "Any"

    if participant_type == "Closed":
        return ""

    if race_id is None:
        return "Unknown"

    return GOD_BY_RACE_ID.get(race_id, f"Unknown ({race_id})")


def build_participants(
    raw_lobby: dict[str, Any],
    decoded_slotinfo: dict[str, Any],
    avatars_by_profile_id: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    slots = decoded_slotinfo.get("slots", [])
    matchmembers_by_profile_id = build_matchmember_lookup(raw_lobby)
    ordered_matchmembers = get_ordered_matchmembers(raw_lobby)
    used_profile_ids: set[int] = set()
    next_matchmember_index = 0

    participants = []

    for index, slot in enumerate(slots, start=1):
        slot_type = classify_slot(slot)
        profile_id = get_profile_id_from_slot(slot)

        if slot_type == "Human player" and profile_id is None:
            while (
                next_matchmember_index < len(ordered_matchmembers)
                and ordered_matchmembers[next_matchmember_index].get("profile_id") in used_profile_ids
            ):
                next_matchmember_index += 1

            if next_matchmember_index < len(ordered_matchmembers):
                profile_id = int(ordered_matchmembers[next_matchmember_index]["profile_id"])
                next_matchmember_index += 1

        if profile_id is not None:
            used_profile_ids.add(profile_id)

        matchmember = matchmembers_by_profile_id.get(profile_id, {}) if profile_id is not None else {}
        avatar = avatars_by_profile_id.get(profile_id, {}) if profile_id is not None else {}

        raw_rating = matchmember.get("ranking")
        rating = normalize_rating(raw_rating)
        race_id = slot.get("raceID")

        if slot_type == "Human player":
            name = clean_display_name(avatar.get("alias")) or f"Player {profile_id}"
            participant_type = "Human"
        elif slot_type == "AI":
            name = f"AI Player {index}"
            participant_type = "AI"
        elif slot_type == "Open human slot":
            name = "Open Slot"
            participant_type = "Open"
        elif slot_type == "Closed":
            name = "Closed Slot"
            participant_type = "Closed"
        else:
            name = "Unknown Slot"
            participant_type = "Unknown"

        participants.append(
            {
                "slot_number": index,
                "name": name,
                "type": participant_type,
                "slot_type": slot_type,
                "profile_id": profile_id,
                "rl_user_id": profile_id,
                "team_id": slot.get("teamID"),
                "faction_id": slot.get("factionID"),
                "race_id": race_id,
                "god": get_god_name(race_id, participant_type),
                "rank_level": slot.get("rankLevel"),
                "rank_match_type_id": slot.get("rankMatchTypeID"),
                "is_ready": slot.get("isReady") == 1,
                "rating": rating,
                "raw_ranking": raw_rating,
                "statgroup_id": matchmember.get("statgroup_id"),
                "civilization_id": matchmember.get("civilization_id"),
                "matchmember_team_id": matchmember.get("teamid"),
                "country": avatar.get("country"),
                "platform_name": avatar.get("name"),
                "debug_slot_profile_id": get_profile_id_from_slot(slot),
            }
        )

    return participants


def normalize_lobby(
    raw_lobby: dict[str, Any],
    avatars_by_profile_id: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    decoded_options = decode_options(raw_lobby.get("options"))
    decoded_slotinfo = decode_slotinfo(raw_lobby.get("slotinfo"))

    slots = decoded_slotinfo.get("slots", [])
    slot_summary = summarize_slots(slots)
    participants = build_participants(raw_lobby, decoded_slotinfo, avatars_by_profile_id)

    host_profile_id = raw_lobby.get("host_profile_id")
    host_avatar = avatars_by_profile_id.get(host_profile_id, {})

    raw_name = raw_lobby.get("description")
    raw_host_alias = host_avatar.get("alias")

    raw_map_name = raw_lobby.get("mapname")
    decoded_map_name = (
        decoded_options.get("mGameFilename")
        or decoded_options.get("mGameMapName")
    )

    game_speed_id = decoded_options.get("mGameSpeed")
    game_mode_id = decoded_options.get("mGameMode")
    starting_resources_id = decoded_options.get("mGameStartingResources")
    map_size_id = decoded_options.get("mGameMapSize")
    map_visibility_id = decoded_options.get("mGameMapVisibility")
    difficulty_id = decoded_options.get("mGameDifficulty")
    starting_age_id = decoded_options.get("mGameStartingAge")
    ending_age_id = decoded_options.get("mGameEndingAge")

    human_players = slot_summary["human_players"]
    open_human_slots = slot_summary["open_human_slots"]
    ai_players = slot_summary["ai_players"]
    total_active_slots = human_players + open_human_slots + ai_players
    occupied_slots = human_players + ai_players

    king_of_the_hill_enabled = decoded_options.get("mRuleKoth") == 1
    treaty_time = decoded_options.get("mRuleTreatyTime")
    blockade_enabled = decoded_options.get("mRuleBlockade") == 1

    game_type_label = normalize_game_type_label(game_mode_id)
    victory_condition_label, victory_condition_id = normalize_victory_condition(decoded_options)
    team_mode_label, team_mode_id = normalize_team_mode(decoded_options)

    visible_participants = [
        participant
        for participant in participants
        if participant.get("type") != "Closed"
    ]

    human_participants = [
        participant
        for participant in participants
        if participant.get("type") == "Human"
    ]

    ai_participants = [
        participant
        for participant in participants
        if participant.get("type") == "AI"
    ]

    open_participants = [
        participant
        for participant in participants
        if participant.get("type") == "Open"
    ]

    host_participant = next(
        (
            participant
            for participant in participants
            if participant.get("profile_id") == host_profile_id
        ),
        None,
    )

    host_major_god = None
    host_major_god_id = None

    if host_participant and host_participant.get("type") == "Human":
        host_major_god = host_participant.get("god")
        host_major_god_id = host_participant.get("race_id")

    return {
        "id": raw_lobby.get("id"),
        "name": clean_display_name(raw_name),
        "host": clean_display_name(raw_host_alias),
        "host_profile_id": host_profile_id,
        "host_major_god": host_major_god,
        "host_major_god_id": host_major_god_id,
        "map": format_map_name(raw_map_name, decoded_map_name),
        "raw_mapname": raw_map_name,
        "region": decoded_options.get("mRegion") or raw_lobby.get("relayserver_region"),
        "relay_region": raw_lobby.get("relayserver_region"),

        "game_type": game_type_label,
        "game_type_id": game_mode_id,
        "game_mode": game_type_label,
        "game_mode_id": game_mode_id,
        "victory_condition": victory_condition_label,
        "victory_condition_id": victory_condition_id,
        "team_mode": team_mode_label,
        "team_mode_id": team_mode_id,
        "matchtype_id": raw_lobby.get("matchtype_id"),

        "speed": label_from_mapping(GAME_SPEED, game_speed_id),
        "speed_id": game_speed_id,

        "max_players_configured": decoded_options.get("mMaxPlayers"),
        "max_players_raw": raw_lobby.get("maxplayers"),

        "human_players": human_players,
        "open_human_slots": open_human_slots,
        "ai_players": ai_players,
        "closed_slots": slot_summary["closed_slots"],
        "unknown_slots": slot_summary["unknown_slots"],
        "total_active_slots": total_active_slots,
        "occupied_slots": occupied_slots,

        "password_protected": raw_lobby.get("passwordprotected") == 1,

        "titans_enabled": decoded_options.get("mAllowTitans") == 1,
        "cheats_enabled": decoded_options.get("mbGameAllowCheats") == 1,

        "starting_age": label_from_mapping(STARTING_AGE, starting_age_id),
        "starting_age_id": starting_age_id,

        "ending_age": label_from_mapping(ENDING_AGE, ending_age_id),
        "ending_age_id": ending_age_id,

        "starting_resources": label_from_mapping(
            STARTING_RESOURCES,
            starting_resources_id,
        ),
        "starting_resources_id": starting_resources_id,

        "map_size": label_from_mapping(MAP_SIZE, map_size_id),
        "map_size_id": map_size_id,

        "map_visibility": label_from_mapping(MAP_VISIBILITY, map_visibility_id),
        "map_visibility_id": map_visibility_id,

        "difficulty": label_from_mapping(AI_DIFFICULTY, difficulty_id),
        "difficulty_id": difficulty_id,

        "treaty_time": treaty_time,
        "king_of_the_hill": king_of_the_hill_enabled,
        "blockade": blockade_enabled,
        "controller_only": decoded_options.get("mControllerOnly") == 1,

        "observer_count": raw_lobby.get("observernum"),
        "observer_max": raw_lobby.get("observermax"),
        "observable": raw_lobby.get("isobservable") == 1,
        "observer_delay": raw_lobby.get("observerdelay"),
        "has_observer_password": raw_lobby.get("hasobserverpassword") == 1,
        "steam_lobby_id": raw_lobby.get("steamlobbyid"),
        "xbox_session_id": raw_lobby.get("xboxsessionid"),

        "participants": participants,
        "visible_participants": visible_participants,
        "human_participants": human_participants,
        "ai_participants": ai_participants,
        "open_participants": open_participants,
    }