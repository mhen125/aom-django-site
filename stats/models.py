from django.db import models


class Player(models.Model):
    PLATFORM_STEAM = "steam"
    PLATFORM_XBOX = "xbox"
    PLATFORM_UNKNOWN = "unknown"

    PLATFORM_CHOICES = [
        (PLATFORM_STEAM, "Steam"),
        (PLATFORM_XBOX, "Xbox"),
        (PLATFORM_UNKNOWN, "Unknown"),
    ]

    platform = models.CharField(max_length=16, choices=PLATFORM_CHOICES, default=PLATFORM_UNKNOWN)
    platform_id = models.CharField(max_length=64, blank=True, db_index=True)
    profile_id = models.BigIntegerField(null=True, blank=True, unique=True, db_index=True)
    alias = models.CharField(max_length=128, blank=True)
    display_name = models.CharField(max_length=160, blank=True)
    avatar_url = models.URLField(blank=True)
    country_code = models.CharField(max_length=8, blank=True)
    raw_identity = models.JSONField(default=dict, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["alias", "display_name", "profile_id", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["platform", "platform_id"],
                name="stats_player_unique_platform_id",
                condition=~models.Q(platform_id=""),
            ),
        ]

    def __str__(self):
        return self.alias or self.display_name or str(self.profile_id or self.pk)


class Match(models.Model):
    SOURCE_WORLDSEDGE = "worlds_edge"
    SOURCE_AOMSTATS = "aomstats"

    SOURCE_CHOICES = [
        (SOURCE_WORLDSEDGE, "World's Edge"),
        (SOURCE_AOMSTATS, "aomstats.io"),
    ]

    source = models.CharField(max_length=32, choices=SOURCE_CHOICES, default=SOURCE_WORLDSEDGE)
    external_match_id = models.CharField(max_length=64, unique=True, db_index=True)
    match_type_id = models.IntegerField(null=True, blank=True, db_index=True)
    match_type_label = models.CharField(max_length=64, blank=True)
    leaderboard_id = models.IntegerField(null=True, blank=True, db_index=True)
    is_ranked = models.BooleanField(default=False)
    is_team_game = models.BooleanField(default=False)
    team_size = models.PositiveSmallIntegerField(null=True, blank=True)
    map_name = models.CharField(max_length=128, blank=True, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.IntegerField(null=True, blank=True)
    winning_team = models.IntegerField(null=True, blank=True)
    patch_label = models.CharField(max_length=64, blank=True, db_index=True)
    replay_url = models.URLField(blank=True)
    replay_available = models.BooleanField(default=False)
    raw_payload = models.JSONField(default=dict, blank=True)
    imported_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-started_at", "-id"]

    def __str__(self):
        return self.external_match_id


class MatchParticipant(models.Model):
    RESULT_WIN = "win"
    RESULT_LOSS = "loss"
    RESULT_UNKNOWN = "unknown"

    RESULT_CHOICES = [
        (RESULT_WIN, "Win"),
        (RESULT_LOSS, "Loss"),
        (RESULT_UNKNOWN, "Unknown"),
    ]

    match = models.ForeignKey(Match, related_name="participants", on_delete=models.CASCADE)
    player = models.ForeignKey(Player, related_name="match_participations", null=True, blank=True, on_delete=models.SET_NULL)
    profile_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    alias = models.CharField(max_length=128, blank=True, db_index=True)
    team = models.IntegerField(null=True, blank=True)
    slot = models.PositiveSmallIntegerField(null=True, blank=True)
    civilization = models.CharField(max_length=64, blank=True, db_index=True)
    faction = models.CharField(max_length=64, blank=True)
    result = models.CharField(max_length=16, choices=RESULT_CHOICES, default=RESULT_UNKNOWN)
    won = models.BooleanField(null=True, blank=True)
    rating = models.IntegerField(null=True, blank=True)
    rating_change = models.IntegerField(null=True, blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["match_id", "team", "slot", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["match", "team", "slot"],
                name="stats_participant_unique_match_team_slot",
            ),
        ]

    def __str__(self):
        return f"{self.alias or self.profile_id or self.pk} @ {self.match.external_match_id}"


class StatWindow(models.Model):
    SCOPE_RANKED = "ranked"
    SCOPE_REPLAYS = "replays"
    SCOPE_META = "meta"

    SCOPE_CHOICES = [
        (SCOPE_RANKED, "Ranked"),
        (SCOPE_REPLAYS, "Replays"),
        (SCOPE_META, "Meta"),
    ]

    slug = models.SlugField(unique=True)
    label = models.CharField(max_length=160)
    scope = models.CharField(max_length=24, choices=SCOPE_CHOICES, default=SCOPE_RANKED)
    match_type_id = models.IntegerField(null=True, blank=True, db_index=True)
    patch_label = models.CharField(max_length=64, blank=True, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True, db_index=True)
    ended_at = models.DateTimeField(null=True, blank=True, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_active", "-started_at", "slug"]

    def __str__(self):
        return self.label


class ReplayParse(models.Model):
    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_PARSED = "parsed"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_PARSED, "Parsed"),
        (STATUS_FAILED, "Failed"),
    ]

    match = models.OneToOneField(Match, related_name="replay_parse", on_delete=models.CASCADE)
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    parser_version = models.CharField(max_length=64, blank=True)
    parser_binary = models.CharField(max_length=255, blank=True)
    replay_url = models.URLField(blank=True)
    replay_sha256 = models.CharField(max_length=64, blank=True, db_index=True)
    parsed_json = models.JSONField(default=dict, blank=True)
    extracted_facts = models.JSONField(default=dict, blank=True)
    error_text = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    enriched_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["status", "-created_at"]

    def __str__(self):
        return f"{self.match.external_match_id} [{self.status}]"


class ReplayPlayerSummary(models.Model):
    replay_parse = models.ForeignKey(ReplayParse, related_name="player_summaries", on_delete=models.CASCADE)
    participant = models.OneToOneField(MatchParticipant, related_name="replay_summary", on_delete=models.CASCADE)
    eapm = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    age_up_classical_seconds = models.IntegerField(null=True, blank=True)
    age_up_heroic_seconds = models.IntegerField(null=True, blank=True)
    age_up_mythic_seconds = models.IntegerField(null=True, blank=True)
    first_military_seconds = models.IntegerField(null=True, blank=True)
    first_tc_seconds = models.IntegerField(null=True, blank=True)
    first_dock_seconds = models.IntegerField(null=True, blank=True)
    first_market_seconds = models.IntegerField(null=True, blank=True)
    primary_unit = models.CharField(max_length=128, blank=True)
    primary_strategy = models.CharField(max_length=128, blank=True)
    raw_summary = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["participant_id"]

    def __str__(self):
        return f"{self.participant} replay summary"


class UnitProductionSummary(models.Model):
    replay_player_summary = models.ForeignKey(
        ReplayPlayerSummary,
        related_name="unit_summaries",
        on_delete=models.CASCADE,
    )
    unit_name = models.CharField(max_length=128, db_index=True)
    produced_count = models.IntegerField(default=0)
    lost_count = models.IntegerField(default=0)
    killed_count = models.IntegerField(default=0)
    first_created_seconds = models.IntegerField(null=True, blank=True)
    last_created_seconds = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-produced_count", "unit_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["replay_player_summary", "unit_name"],
                name="stats_unit_summary_unique_player_unit",
            ),
        ]

    def __str__(self):
        return f"{self.unit_name} x{self.produced_count}"


class ReplayTag(models.Model):
    SOURCE_REPLAY_PARSER = "replay_parser"
    SOURCE_RULE_ENGINE = "rule_engine"
    SOURCE_MANUAL = "manual"

    SOURCE_CHOICES = [
        (SOURCE_REPLAY_PARSER, "Replay Parser"),
        (SOURCE_RULE_ENGINE, "Rule Engine"),
        (SOURCE_MANUAL, "Manual"),
    ]

    match = models.ForeignKey(Match, related_name="replay_tags", on_delete=models.CASCADE)
    participant = models.ForeignKey(MatchParticipant, related_name="replay_tags", null=True, blank=True, on_delete=models.CASCADE)
    tag = models.CharField(max_length=64, db_index=True)
    source = models.CharField(max_length=24, choices=SOURCE_CHOICES, default=SOURCE_REPLAY_PARSER)
    confidence = models.DecimalField(max_digits=4, decimal_places=3, null=True, blank=True)
    note = models.TextField(blank=True)
    evidence = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["tag", "-created_at"]

    def __str__(self):
        return self.tag


class GodMetaSnapshot(models.Model):
    stat_window = models.ForeignKey(StatWindow, related_name="god_snapshots", on_delete=models.CASCADE)
    match_type_id = models.IntegerField(null=True, blank=True, db_index=True)
    team_size = models.PositiveSmallIntegerField(null=True, blank=True, db_index=True)
    elo_bracket = models.CharField(max_length=64, blank=True, db_index=True)
    god_name = models.CharField(max_length=64, db_index=True)
    games = models.IntegerField(default=0)
    wins = models.IntegerField(default=0)
    losses = models.IntegerField(default=0)
    play_rate = models.DecimalField(max_digits=7, decimal_places=3, null=True, blank=True)
    win_rate = models.DecimalField(max_digits=7, decimal_places=3, null=True, blank=True)
    mirrors_excluded = models.IntegerField(default=0)
    data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["god_name", "elo_bracket", "match_type_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["stat_window", "match_type_id", "team_size", "elo_bracket", "god_name"],
                name="stats_god_snapshot_unique_window_slice",
            ),
        ]

    def __str__(self):
        return f"{self.god_name} [{self.elo_bracket or 'all'}]"


class MetaClaim(models.Model):
    SCOPE_GOD = "god"
    SCOPE_MAP = "map"
    SCOPE_MATCHUP = "matchup"
    SCOPE_STRATEGY = "strategy"

    SCOPE_CHOICES = [
        (SCOPE_GOD, "God"),
        (SCOPE_MAP, "Map"),
        (SCOPE_MATCHUP, "Matchup"),
        (SCOPE_STRATEGY, "Strategy"),
    ]

    stat_window = models.ForeignKey(StatWindow, related_name="meta_claims", on_delete=models.CASCADE)
    scope = models.CharField(max_length=24, choices=SCOPE_CHOICES, default=SCOPE_GOD, db_index=True)
    claim_key = models.SlugField(max_length=128, db_index=True)
    headline = models.CharField(max_length=255)
    verdict = models.CharField(max_length=64, db_index=True)
    subject = models.CharField(max_length=128, blank=True, db_index=True)
    confidence = models.DecimalField(max_digits=4, decimal_places=3, null=True, blank=True)
    evidence = models.JSONField(default=dict, blank=True)
    is_public = models.BooleanField(default=False, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True)
    retired_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-published_at", "claim_key"]
        constraints = [
            models.UniqueConstraint(
                fields=["stat_window", "claim_key"],
                name="stats_meta_claim_unique_window_key",
            ),
        ]

    def __str__(self):
        return self.headline
