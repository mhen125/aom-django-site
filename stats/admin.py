from django.contrib import admin

from .models import (
    GodMetaSnapshot,
    Match,
    MatchParticipant,
    MetaClaim,
    Player,
    ReplayParse,
    ReplayPlayerSummary,
    ReplayTag,
    StatWindow,
    UnitProductionSummary,
)


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ("id", "profile_id", "alias", "platform", "platform_id", "updated_at")
    list_filter = ("platform",)
    search_fields = ("profile_id", "alias", "display_name", "platform_id")


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ("external_match_id", "source", "match_type_id", "map_name", "started_at", "is_ranked")
    list_filter = ("source", "is_ranked", "is_team_game", "match_type_id")
    search_fields = ("external_match_id", "map_name", "patch_label")


@admin.register(MatchParticipant)
class MatchParticipantAdmin(admin.ModelAdmin):
    list_display = ("id", "match", "profile_id", "alias", "civilization", "team", "slot", "result")
    list_filter = ("result", "civilization", "team")
    search_fields = ("profile_id", "alias", "civilization", "match__external_match_id")


@admin.register(StatWindow)
class StatWindowAdmin(admin.ModelAdmin):
    list_display = ("slug", "label", "scope", "match_type_id", "patch_label", "is_active")
    list_filter = ("scope", "is_active", "match_type_id")
    search_fields = ("slug", "label", "patch_label")


@admin.register(ReplayParse)
class ReplayParseAdmin(admin.ModelAdmin):
    list_display = ("match", "status", "parser_version", "replay_sha256", "updated_at")
    list_filter = ("status",)
    search_fields = ("match__external_match_id", "replay_sha256", "parser_version")


@admin.register(ReplayPlayerSummary)
class ReplayPlayerSummaryAdmin(admin.ModelAdmin):
    list_display = ("participant", "eapm", "primary_unit", "primary_strategy", "updated_at")
    search_fields = ("participant__alias", "primary_unit", "primary_strategy")


@admin.register(UnitProductionSummary)
class UnitProductionSummaryAdmin(admin.ModelAdmin):
    list_display = ("replay_player_summary", "unit_name", "produced_count", "lost_count", "killed_count")
    list_filter = ("unit_name",)
    search_fields = ("unit_name", "replay_player_summary__participant__alias")


@admin.register(ReplayTag)
class ReplayTagAdmin(admin.ModelAdmin):
    list_display = ("tag", "match", "participant", "source", "confidence", "updated_at")
    list_filter = ("source", "tag")
    search_fields = ("tag", "match__external_match_id", "participant__alias")


@admin.register(GodMetaSnapshot)
class GodMetaSnapshotAdmin(admin.ModelAdmin):
    list_display = ("god_name", "stat_window", "elo_bracket", "match_type_id", "games", "win_rate")
    list_filter = ("match_type_id", "team_size", "elo_bracket")
    search_fields = ("god_name", "elo_bracket", "stat_window__slug")


@admin.register(MetaClaim)
class MetaClaimAdmin(admin.ModelAdmin):
    list_display = ("headline", "scope", "verdict", "subject", "is_public", "published_at")
    list_filter = ("scope", "verdict", "is_public")
    search_fields = ("headline", "subject", "claim_key")

