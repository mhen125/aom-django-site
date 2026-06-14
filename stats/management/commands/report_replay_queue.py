import json
from collections import Counter

from django.core.management.base import BaseCommand

from stats.models import ReplayParse
from stats.replay_builds import evaluate_replay_build


def _bucket_build(value):
    if value in (None, ""):
        return "unknown"
    return str(value)


class Command(BaseCommand):
    help = "Report replay queue readiness, parser outcomes, and build buckets for ReplayParse rows."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=25, help="How many replay rows to include in the detailed sample output.")
        parser.add_argument(
            "--status",
            action="append",
            default=[],
            help="Optional ReplayParse status filter. Repeat for multiple values.",
        )
        parser.add_argument("--json", action="store_true", help="Emit the full report as JSON.")

    def handle(self, *args, **options):
        statuses = [value.strip() for value in (options["status"] or []) if value and value.strip()]
        limit = max(1, int(options["limit"] or 25))

        queryset = ReplayParse.objects.select_related("match").order_by("status", "-updated_at", "-id")
        if statuses:
            queryset = queryset.filter(status__in=statuses)

        rows = list(queryset)
        status_counts = Counter()
        build_counts = Counter()
        patch_counts = Counter()
        replay_url_ready = 0
        replay_file_ready = 0
        replay_available_flagged = 0
        parsed_with_player_summaries = 0
        failed_with_errors = 0
        supported_build_rows = 0
        unsupported_build_rows = 0
        unknown_build_rows = 0
        detailed_rows = []

        for row in rows:
            facts = row.extracted_facts if isinstance(row.extracted_facts, dict) else {}
            build_value = facts.get("build_number") or row.match.patch_label or ""
            patch_value = row.match.patch_label or ""
            replay_url = row.replay_url or row.match.replay_url or ""
            replay_flag = bool(facts.get("replay_available")) or bool(row.match.replay_available)
            build_policy = evaluate_replay_build(row.match, row)

            status_counts[row.status] += 1
            build_counts[_bucket_build(build_value)] += 1
            patch_counts[_bucket_build(patch_value)] += 1

            if build_policy["known"]:
                if build_policy["eligible"]:
                    supported_build_rows += 1
                else:
                    unsupported_build_rows += 1
            else:
                unknown_build_rows += 1

            if replay_url:
                replay_url_ready += 1
                if replay_url.startswith("file://"):
                    replay_file_ready += 1
            if replay_flag:
                replay_available_flagged += 1
            if row.status == ReplayParse.STATUS_PARSED and row.player_summaries.exists():
                parsed_with_player_summaries += 1
            if row.status == ReplayParse.STATUS_FAILED and row.error_text:
                failed_with_errors += 1

            if len(detailed_rows) < limit:
                detailed_rows.append(
                    {
                        "match_id": row.match.external_match_id,
                        "status": row.status,
                        "match_type_label": row.match.match_type_label,
                        "map_name": row.match.map_name,
                        "started_at": row.match.started_at.isoformat() if row.match.started_at else None,
                        "patch_label": row.match.patch_label,
                        "build_number": facts.get("build_number"),
                        "build_policy_reason": build_policy["reason"],
                        "build_eligible": build_policy["eligible"],
                        "replay_url_present": bool(replay_url),
                        "replay_url_is_file": replay_url.startswith("file://") if replay_url else False,
                        "replay_available": replay_flag,
                        "player_summaries": row.player_summaries.count(),
                        "error_text": row.error_text[:240] if row.error_text else "",
                    }
                )

        report = {
            "ok": True,
            "status_filter": statuses,
            "total_rows": len(rows),
            "status_counts": dict(status_counts),
            "build_counts": dict(build_counts),
            "patch_counts": dict(patch_counts),
            "replay_url_ready": replay_url_ready,
            "replay_file_ready": replay_file_ready,
            "replay_available_flagged": replay_available_flagged,
            "parsed_with_player_summaries": parsed_with_player_summaries,
            "failed_with_errors": failed_with_errors,
            "supported_build_rows": supported_build_rows,
            "unsupported_build_rows": unsupported_build_rows,
            "unknown_build_rows": unknown_build_rows,
            "sample_rows": detailed_rows,
        }

        if options["json"]:
            self.stdout.write(json.dumps(report, indent=2, sort_keys=True))
            return

        self.stdout.write(
            self.style.SUCCESS(
                (
                    f"Replay queue: {report['total_rows']} row(s) | "
                    f"URL-ready: {report['replay_url_ready']} | "
                    f"parsed with summaries: {report['parsed_with_player_summaries']} | "
                    f"failed with errors: {report['failed_with_errors']} | "
                    f"unsupported builds: {report['unsupported_build_rows']}"
                )
            )
        )
        self.stdout.write(f"Status counts: {json.dumps(report['status_counts'], sort_keys=True)}")
        self.stdout.write(f"Build counts: {json.dumps(report['build_counts'], sort_keys=True)}")

        if options["verbosity"] >= 2:
            self.stdout.write("Sample rows:")
            for row in detailed_rows:
                self.stdout.write(f"  - {json.dumps(row, sort_keys=True)}")
