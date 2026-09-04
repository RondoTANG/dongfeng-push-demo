from __future__ import annotations

import tempfile
import unittest
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from service import database
from service.database import connection, init_database, json_text, now_iso
from service.drafts import review_event
from service.evidence_requests import confirm_evidence_request, create_evidence_plan, execute_evidence_request
from service.events import aggregate_run, get_event
from service.pipeline import execute_collection, run_cooldown
from service.collector import search_codex_batch
from service.repositories import count_sources, get_run, list_sources


def result_item(title: str, url: str, publish_time: str | None = None) -> dict[str, object]:
    return {
        "title": title,
        "url": url,
        "snippet": "岚图汽车发布新产品信息，公开页面提供事件事实。",
        "publish_time": publish_time or now_iso(),
        "domain": "example.com",
        "hostname": "example.com",
        "rank": 1,
    }


class ServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(prefix="ai-hotspot-test-")
        self.old_path = database.DATABASE_PATH
        database.DATABASE_PATH = Path(self.temp_dir.name) / "test.db"
        init_database()

    def tearDown(self) -> None:
        database.DATABASE_PATH = self.old_path
        self.temp_dir.cleanup()

    def test_quick_run_executes_both_providers_and_keeps_discoveries(self) -> None:
        item = result_item("岚图汽车发布产品更新", "https://example.com/news/1")
        with patch("service.pipeline.search_doubao", return_value={"items": [item], "processed": {"success": True}}), patch(
            "service.pipeline.search_codex_batch",
            return_value={"B01": {"items": [item], "raw_response": {"query_id": "B01"}, "error": None}},
        ):
            run_id = execute_collection(mode="quick", idempotency_key="dual-provider-test")
        run = get_run(run_id) or {}
        self.assertEqual(run["status"], "success")
        self.assertEqual(run["query_coverage"]["planned_query_count"], 1)
        self.assertEqual(run["query_coverage"]["provider_count"], 2)
        self.assertEqual(run["query_coverage"]["planned_job_count"], 2)
        self.assertEqual({job["provider_id"] for job in run["query_jobs"]}, {"doubao_global_search", "codex_web_search"})
        sources = list_sources(run_id=run_id)
        self.assertEqual(len(sources), 1)
        self.assertEqual(set(sources[0]["discovered_by"]), {"doubao_global_search", "codex_web_search"})
        self.assertEqual(len(sources[0]["discoveries"]), 2)

    def test_one_provider_failure_is_partial_success(self) -> None:
        item = result_item("岚图汽车发布产品更新", "https://example.com/news/2")
        with patch("service.pipeline.search_doubao", side_effect=RuntimeError("doubao failed")), patch(
            "service.pipeline.search_codex_batch",
            return_value={"B01": {"items": [item], "raw_response": {"query_id": "B01"}, "error": None}},
        ):
            run_id = execute_collection(mode="quick", idempotency_key="partial-provider-test")
        run = get_run(run_id) or {}
        self.assertEqual(run["status"], "partial_success")
        self.assertEqual(run["query_coverage"]["failed_job_count"], 1)
        self.assertEqual(run["provider_summary"]["doubao_global_search"]["failed"], 1)

    def test_old_result_is_filtered_before_event_workbench(self) -> None:
        old_time = (datetime.now().astimezone() - timedelta(days=120)).isoformat(timespec="seconds")
        item = result_item("从代步到玩车 汽车后市场观察", "https://example.com/old", old_time)
        with patch("service.pipeline.search_doubao", return_value={"items": [item], "processed": {"success": True}}), patch(
            "service.pipeline.search_codex_batch",
            return_value={"B01": {"items": [item], "raw_response": {"query_id": "B01"}, "error": None}},
        ):
            run_id = execute_collection(mode="quick", idempotency_key="old-news-test")
        self.assertEqual(count_sources(run_id=run_id, status="valid"), 0)
        self.assertEqual(count_sources(run_id=run_id, status="invalid"), 1)
        aggregation = aggregate_run(run_id)
        self.assertEqual(aggregation["events_created"], 0)

    def test_evidence_search_requires_confirmation_and_can_use_both_providers(self) -> None:
        event_id = self._seed_event()
        plan = create_evidence_plan(event_id, search_queries=["岚图汽车 官方 最新"])
        self.assertEqual(plan["status"], "pending_confirmation")
        with connection() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM evidence_jobs").fetchone()[0], 0)
        confirm_evidence_request(
            plan["evidence_request_id"],
            methods=["codex_web_search", "doubao_global_search"],
            confirmed_by="测试运营",
        )
        item = result_item("岚图汽车官方信息", "https://example.com/evidence")
        with patch(
            "service.evidence_requests.search_codex_batch",
            return_value={"E01": {"items": [item], "raw_response": {}, "error": None}},
        ), patch("service.evidence_requests.search_doubao", return_value={"items": [item]}):
            result = execute_evidence_request(plan["evidence_request_id"])
        self.assertEqual(result["status"], "completed")
        self.assertEqual({job["provider_id"] for job in result["jobs"]}, {"codex_web_search", "doubao_global_search"})
        self.assertEqual(get_event(event_id)["event_status"], "pending_review")

    def test_approved_event_generates_complete_original_brief(self) -> None:
        event_id = self._seed_event()
        result = review_event(
            event_id,
            review_result="approved",
            event_status="relevant_event_clue",
            reviewer="测试运营",
            review_note=None,
            evidence_summary="已核验事件事实和来源链接。",
            risk_summary="未发现阻断性风险。",
            recommended_action="生成原创增长草案",
            action_paths=["original_growth"],
            boost_source_ids=[],
        )
        brief = result["drafts"][0]["task_brief"]
        for heading in ("一、作业详情", "必带话题", "核心命题", "二、平台适配指引", "三、创作方向参考", "四、作业规则"):
            self.assertIn(heading, brief)

    def test_cooldown_uses_latest_run(self) -> None:
        with patch("service.pipeline.search_doubao", return_value={"items": [], "processed": {"success": True}}), patch(
            "service.pipeline.search_codex_batch",
            return_value={"B01": {"items": [], "raw_response": {}, "error": None}},
        ):
            execute_collection(mode="quick", idempotency_key="cooldown-test")
        result = run_cooldown("quick")
        self.assertFalse(result["allowed"])
        self.assertGreater(result["remaining_seconds"], 0)

    def test_codex_adapter_supports_offline_fixture(self) -> None:
        fixture = Path(self.temp_dir.name) / "codex.json"
        fixture.write_text(json.dumps({"results": [{
            "query_id": "B01", "query": "东风汽车 最新动态", "items": [
                result_item("东风汽车公开信息", "https://example.com/codex")
            ], "error": None,
        }]}, ensure_ascii=False), encoding="utf-8")
        with patch.dict(os.environ, {"CODEX_WEB_SEARCH_FIXTURE": str(fixture)}):
            result = search_codex_batch([{"query_id": "B01", "query": "东风汽车 最新动态"}])
        self.assertEqual(result["B01"]["provider"], "codex_web_search")
        self.assertEqual(result["B01"]["items"][0]["url"], "https://example.com/codex")

    def test_source_list_uses_server_side_pagination_and_inclusive_date_end(self) -> None:
        timestamp = now_iso()
        with connection() as db:
            db.execute(
                "INSERT INTO collection_runs (run_id,trigger_type,mode,status,started_at) VALUES ('RUN-PAGE','import','sample','success',?)",
                (timestamp,),
            )
            for index in range(25):
                db.execute(
                    """INSERT INTO source_items (
                        source_id,run_id,retrieved_by,query_ids_json,source_status,source_platform,
                        original_url,canonical_url,title,snippet,published_at,fetched_at,first_seen_at
                    ) VALUES (?,?,?,'[]','valid','general_web',?,?,?,?,?,?,?)""",
                    (
                        f"SRC-PAGE-{index:02d}", "RUN-PAGE", "doubao_global_search",
                        f"https://example.com/page/{index}", f"https://example.com/page/{index}",
                        f"分页线索 {index}", "分页验证", timestamp, timestamp, timestamp,
                    ),
                )
        first_page = list_sources(run_id="RUN-PAGE", status="valid", fetched_to=timestamp[:10], limit=10, offset=0)
        second_page = list_sources(run_id="RUN-PAGE", status="valid", fetched_to=timestamp[:10], limit=10, offset=10)
        self.assertEqual(count_sources(run_id="RUN-PAGE", status="valid", fetched_to=timestamp[:10]), 25)
        self.assertEqual(len(first_page), 10)
        self.assertEqual(len(second_page), 10)
        first_ids = {item["source_id"] for item in first_page}
        second_ids = {item["source_id"] for item in second_page}
        self.assertTrue(first_ids.isdisjoint(second_ids))

    def _seed_event(self) -> str:
        timestamp = now_iso()
        run_id = "RUN-SEED"
        source_id = "SRC-SEED"
        event_id = "EVT-SEED"
        with connection() as db:
            db.execute(
                "INSERT INTO collection_runs (run_id,trigger_type,mode,status,started_at) VALUES (?,?,?,'success',?)",
                (run_id, "import", "sample", timestamp),
            )
            db.execute(
                """INSERT INTO source_items (
                    source_id,run_id,retrieved_by,query_ids_json,source_status,source_platform,
                    original_url,canonical_url,title,snippet,fetched_at,first_seen_at
                ) VALUES (?,?,?,'[]','valid','general_web',?,?,?,?,?,?)""",
                (source_id, run_id, "doubao_global_search", "https://example.com/seed", "https://example.com/seed", "岚图汽车产品信息", "公开事实", timestamp, timestamp),
            )
            db.execute(
                """INSERT INTO events (
                    event_id,run_id,event_title,source_count,independent_source_count,
                    source_platforms_json,brand_relations_json,entity_mentions_json,
                    entity_uncertainties_json,risk_tags_json,missing_evidence_json,
                    hotspot_judgement_available,hotspot_status,hotspot_unavailable_reason_json,
                    event_status,decision_reason,created_at,updated_at
                ) VALUES (?,?,?,1,1,?,?,?,?,?,?,0,'unknown',?,'pending_review',?,?,?)""",
                (
                    event_id, run_id, "岚图汽车产品信息", json_text(["general_web"]),
                    json_text([{"brand_id": "BR003", "brand_name": "岚图汽车", "relation_status": "direct_mention"}]),
                    json_text([]), json_text([]), json_text([]), json_text(["缺少平台原生指标"]),
                    json_text(["缺少平台原生指标"]), "等待审核", timestamp, timestamp,
                ),
            )
            db.execute(
                "INSERT INTO event_evidence (evidence_id,event_id,source_id,evidence_type,evidence_text,evidence_url,provided_by,created_at) VALUES (?,?,?,?,?,?,?,?)",
                ("EVD-SEED", event_id, source_id, "source_excerpt", "岚图汽车发布产品信息。", "https://example.com/seed", "test", timestamp),
            )
        return event_id


if __name__ == "__main__":
    unittest.main()
