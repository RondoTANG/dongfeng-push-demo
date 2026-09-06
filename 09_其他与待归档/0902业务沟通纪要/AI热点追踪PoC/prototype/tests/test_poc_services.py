from __future__ import annotations

import tempfile
import unittest
import json
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from service import database
from service.database import connection, init_database, json_text, now_iso
from service.drafts import review_event
from service.evidence_requests import confirm_evidence_request, create_evidence_plan, execute_evidence_request
from service.events import aggregate_run, get_event, split_event
from service.pipeline import execute_collection, run_cooldown
from service.collector import search_codex_batch
from service.source_time import resolve_publication_time, TZ
from service.pipeline import _invalid_reason
from service.business_relation import assess_business_relation
from service.config_loader import risk_rules, risk_display_text
from service.events import _risk_tags
from service.repositories import count_sources, get_run, list_sources
from service import access_control
from service.work_items import enqueue_analysis_work_item, claim_work_item, complete_work_item
from service.ai_executor import _run_codex, process_work_items
from service.doubao_result_processor import handler as process_doubao_result
from scripts.reprocess_local_run import reprocess


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
    def test_direct_fernet_key_can_be_used_for_server_migration(self) -> None:
        from cryptography.fernet import Fernet

        key = Fernet.generate_key()
        with patch.dict(os.environ, {"AI_HOTSPOT_KEY_ENCRYPTION_SECRET": key.decode("ascii")}):
            self.assertEqual(access_control._encryption_key(), key)

    def test_bundled_doubao_processor_parses_provider_envelope(self) -> None:
        payload = {
            "search_results": [{
                "status_code": 200,
                "body": {
                    "ResponseMetadata": {"RequestId": "REQ-1"},
                    "Result": {
                        "ErrorCode": 0,
                        "Documents": [{
                            "Rank": 1,
                            "Title": "岚图汽车发布公开信息",
                            "Url": "https://example.com/news#fragment",
                            "DocumentInfo": {"PublishTime": "2026-09-06T10:00:00+08:00"},
                            "Snippet": [{"Type": "text", "Text": "岚图汽车发布公开信息。"}],
                        }],
                    },
                },
            }]
        }
        result = process_doubao_result(payload)
        self.assertTrue(result["success"])
        items = json.loads(result["web_search_items_json"])
        self.assertEqual(items[0]["url"], "https://example.com/news")
        self.assertEqual(items[0]["provider_request_id"], "REQ-1")

    def test_access_keys_are_hashed_role_scoped_and_revocable(self) -> None:
        original_admin_file = access_control.ADMIN_KEY_FILE
        original_encryption_file = access_control.ACCESS_KEY_ENCRYPTION_FILE
        access_control.ADMIN_KEY_FILE = Path(self.temp_dir.name) / "admin_access.key"
        access_control.ACCESS_KEY_ENCRYPTION_FILE = Path(self.temp_dir.name) / "access_key_encryption.key"
        try:
            with patch.dict(os.environ, {"AI_HOTSPOT_ADMIN_KEY": "ADM-test-admin-secret"}):
                access_control.init_access_control()
                admin = access_control.authenticate_key("ADM-test-admin-secret")
                self.assertEqual(admin["role"], "admin")
                created = access_control.create_viewer_key("业务评审组", 30, "测试管理员")
                self.assertTrue(created["access_key"].startswith("VIS-"))
                with connection() as db:
                    stored = db.execute("SELECT secret_hash, salt, encrypted_secret FROM access_keys WHERE access_key_id=?", (created["access_key_id"],)).fetchone()
                    self.assertNotIn(created["access_key"], tuple(stored))
                with self.assertRaisesRegex(PermissionError, "管理员密钥验证失败"):
                    access_control.reveal_viewer_key(created["access_key_id"], "ADM-wrong-secret")
                revealed = access_control.reveal_viewer_key(created["access_key_id"], "ADM-test-admin-secret")
                self.assertEqual(revealed["access_key"], created["access_key"])
                self.assertTrue(access_control.list_access_keys()[0]["can_reveal"])
                viewer = access_control.authenticate_key(created["access_key"])
                self.assertEqual(viewer["role"], "viewer")
                token, _ = access_control.create_session(viewer)
                self.assertEqual(access_control.get_session(token)["role"], "viewer")
                self.assertTrue(access_control.revoke_access_key(created["access_key_id"]))
                self.assertIsNone(access_control.get_session(token))
                self.assertIsNone(access_control.authenticate_key(created["access_key"]))
        finally:
            access_control.ADMIN_KEY_FILE = original_admin_file
            access_control.ACCESS_KEY_ENCRYPTION_FILE = original_encryption_file

    def test_publication_sort_is_timezone_aware_and_stable(self) -> None:
        self.test_source_list_uses_server_side_pagination_and_inclusive_date_end()
        with connection() as db:
            db.execute("UPDATE source_items SET published_at=NULL")
            db.execute("UPDATE source_items SET published_at='2026-09-06T12:00:00+08:00', fetched_at='2026-09-06T13:00:00+08:00' WHERE source_id='SRC-PAGE-00'")
            db.execute("UPDATE source_items SET published_at='2026-09-06T06:00:00+00:00', fetched_at='2026-09-06T12:00:00+08:00' WHERE source_id IN ('SRC-PAGE-01','SRC-PAGE-02')")
        rows = list_sources(limit=3)
        self.assertEqual([r["source_id"] for r in rows], ["SRC-PAGE-01", "SRC-PAGE-02", "SRC-PAGE-00"])
        self.assertEqual(list_sources(limit=1, offset=1)[0]["source_id"], "SRC-PAGE-02")

    def _seed_two_source_event(self) -> str:
        event_id = self._seed_event()
        with connection() as db:
            db.execute("""INSERT INTO source_items (source_id,run_id,retrieved_by,query_ids_json,source_status,source_platform,
                original_url,canonical_url,title,snippet,published_at,fetched_at,first_seen_at,domain)
                VALUES ('SRC-SECOND','RUN-SEED','codex_web_search','[]','valid','industry_media',
                'https://second.example/news','https://second.example/news','东风本田召回公告','东风本田公布召回范围。',?,?,?,'second.example')""",
                (now_iso(), now_iso(), now_iso()))
            db.execute("""INSERT INTO event_evidence (evidence_id,event_id,source_id,evidence_type,evidence_text,provided_by,created_at)
                VALUES ('EVD-SECOND',?,'SRC-SECOND','source_excerpt','东风本田召回公告','source_pipeline',?)""", (event_id, now_iso()))
        return event_id

    def test_split_single_source_is_hidden_and_rejected(self) -> None:
        event_id = self._seed_event()
        self.assertFalse(get_event(event_id)["can_split"])
        with self.assertRaisesRegex(ValueError, "不足两条"):
            split_event(event_id, ["SRC-SEED"], "拆出的测试事件", "测试运营")
        self.assertEqual(len(get_event(event_id)["sources"]), 1)

    def test_split_requires_proper_subset_and_keeps_both_sides_consistent(self) -> None:
        event_id = self._seed_two_source_event()
        self.assertTrue(get_event(event_id)["can_split"])
        for ids in ([], ["SRC-OTHER"], ["SRC-SEED", "SRC-SECOND"]):
            with self.assertRaises(ValueError):
                split_event(event_id, ids, "东风本田召回公告", "测试运营")
        new = split_event(event_id, ["SRC-SECOND", "SRC-SECOND"], "东风本田召回公告", "测试运营")
        old = get_event(event_id)
        self.assertEqual(new["source_count"], 1)
        self.assertEqual(old["source_count"], 1)
        self.assertEqual(new["sources"][0]["source_id"], "SRC-SECOND")
        self.assertEqual(old["sources"][0]["source_id"], "SRC-SEED")
        self.assertEqual(new["source_platforms"], ["industry_media"])
        self.assertIn("recall", new["risk_tags"])
        self.assertNotIn("recall", old["risk_tags"])
        self.assertFalse(new["can_split"])
        self.assertFalse(old["can_split"])
        self.assertTrue(all("本田" in r["brand_name"] for r in new["brand_relations"]))
        self.assertEqual(new["work_items"][0]["input"]["source_ids"], ["SRC-SECOND"])

    def test_split_does_not_change_reviewed_or_running_event(self) -> None:
        event_id = self._seed_two_source_event()
        with connection() as db:
            db.execute("UPDATE events SET event_status='rejected' WHERE event_id=?", (event_id,))
        self.assertFalse(get_event(event_id)["can_split"])
        with self.assertRaisesRegex(ValueError, "已有审核"):
            split_event(event_id, ["SRC-SECOND"], "东风本田召回公告", "测试运营")

    def test_query_id_is_not_sent_as_search_text(self) -> None:
        catalog = [{"query_id": "T07", "query_group": "topic", "query": "汽车技术 测评 耐久 最新动态"}]
        with patch("service.pipeline.query_catalog", return_value=catalog), patch("service.pipeline.search_doubao", return_value={"items": [], "raw_response": {}}) as doubao, patch("service.pipeline.search_codex_batch", return_value={"T07": {"items": [], "raw_response": {}, "error": None}}) as codex:
            run_id = execute_collection(mode="full", idempotency_key="query-text-only")
        real_query = doubao.call_args.args[0]
        self.assertNotIn("T07", real_query)
        self.assertIn("汽车技术", real_query)
        self.assertEqual(codex.call_args.args[0][0]["query"], real_query)
        self.assertEqual(codex.call_args.args[0][0]["query_id"], "T07")
        self.assertTrue(all(job["query_text"] == real_query for job in get_run(run_id)["query_jobs"]))

    def test_competitor_topics_do_not_enter_workbench_or_events(self) -> None:
        titles = ["吉利汽车8月销量超27万辆 海外出口连续三月破10万辆", "比亚迪海狮08正式上市 售价22.99万元起", "宝马（中国）汽车贸易有限公司、华晨宝马汽车有限公司召回部分进口及国产汽车", "上汽通用汽车销售有限公司召回部分进口凯迪拉克SRX汽车"]
        items = [{**result_item(title, f"https://example.com/competitor/{i}"), "snippet": title + "。该品牌发布最新公告。"} for i, title in enumerate(titles)]
        for item in items:
            self.assertEqual(_invalid_reason(item, "topic", [])[0], "INV007")
        with patch("service.pipeline.query_catalog", return_value=[{"query_id": "T06", "query_group": "topic", "query": "汽车召回 监管 投诉 最新动态"}]), patch("service.pipeline.search_doubao", return_value={"items": items, "raw_response": {}}), patch("service.pipeline.search_codex_batch", return_value={"T06": {"items": items, "raw_response": {}, "error": None}}):
            run_id = execute_collection(mode="full", idempotency_key="competitor-regression")
        self.assertEqual(count_sources(run_id=run_id, status="valid"), 0)
        self.assertEqual(count_sources(run_id=run_id, status="invalid"), 4)
        self.assertEqual(aggregate_run(run_id)["events_created"], 0)
        with connection() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM source_discoveries WHERE run_id=?", (run_id,)).fetchone()[0], 8)

    def test_relevance_requires_content_evidence_not_query_or_footer(self) -> None:
        item = {"title": "比亚迪汽车新品上市", "snippet": "比亚迪公布配置。\n相关推荐：岚图汽车新动态", "query": "岚图汽车 最新"}
        self.assertFalse(assess_business_relation(item)["eligible"])
        item["snippet"] = "岚图汽车与比亚迪汽车共同参加此次技术讨论，公告列出了两家企业的参与内容。"
        result = assess_business_relation(item)
        self.assertTrue(result["eligible"])
        self.assertIn("岚图", result["relations"][0]["evidence_excerpt"])
        self.assertEqual(assess_business_relation({"title": "猛士新活动", "snippet": "同名含义尚不明确"})["status"], "pending_verification")
        self.assertFalse(assess_business_relation({"title": "其他品牌销量", "snippet": "其他品牌消息", "domain": "dfmc.com.cn"})["eligible"])

    def test_same_url_later_evidence_can_complete_relevance(self) -> None:
        first = {**result_item("汽车技术活动", "https://example.com/shared"), "snippet": "近期举办汽车技术活动"}
        second = {**first, "snippet": "岚图汽车参与汽车技术活动，并介绍具体验证方案。"}
        with patch("service.pipeline.search_doubao", return_value={"items": [first], "raw_response": {}}), patch("service.pipeline.search_codex_batch", return_value={"B01": {"items": [second], "raw_response": {}, "error": None}}):
            run_id = execute_collection(mode="quick", idempotency_key="relevance-upgrade")
        self.assertEqual(count_sources(run_id=run_id, status="valid"), 1)
        source = list_sources(run_id=run_id, status="valid")[0]
        self.assertEqual(len(source["discoveries"]), 2)
        self.assertIn("岚图", source["snippet"])
        self.assertTrue(source["business_relation"]["eligible"])

    def test_unverified_legacy_source_is_hidden_from_default_list(self) -> None:
        self._seed_event()
        self.assertEqual(count_sources(status="valid"), 0)

    def test_brand_negative_event_is_not_discarded_for_sentiment(self) -> None:
        item = {**result_item("东风本田公布召回公告", "https://example.com/recall"), "snippet": "东风本田公布产品召回范围及原因。"}
        self.assertIsNone(_invalid_reason(item, "topic", []))

    def test_approval_rechecks_source_business_relation(self) -> None:
        event_id = self._seed_event()
        with connection() as db:
            db.execute("UPDATE source_items SET title='宝马公布召回公告', snippet='仅涉及宝马产品' WHERE source_id IN (SELECT source_id FROM event_evidence WHERE event_id=?)", (event_id,))
        with self.assertRaisesRegex(ValueError, "目标品牌关联证据"):
            review_event(event_id, review_result="approved", event_status="brand_content_opportunity", reviewer="测试运营", review_note=None, evidence_summary="事件事实确认", risk_summary="已核验", recommended_action="生成原创", action_paths=["original_growth"], boost_source_ids=[])
        with connection() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM task_drafts").fetchone()[0], 0)

    def test_visible_old_publication_overrides_search_date(self) -> None:
        item = {"title": "汽车舆论事件", "url": "https://example.com/old", "publish_time": "2026-09-05T01:18:00+08:00", "snippet": "汽车舆论事件\n龙衍特种车工场\n35浏览 · 08-20 · 上海\n8 月 18 日，公安部发布消息。"}
        resolved = resolve_publication_time(item, datetime(2026, 9, 5, tzinfo=TZ))
        self.assertTrue(resolved["published_at"].startswith("2026-08-20"))
        self.assertTrue(resolved["conflict"])
        self.assertEqual(resolved["basis"], "正文头部发布时间")

    def test_narrative_date_is_not_publication_date(self) -> None:
        item = {"title": "汽车动态", "url": "https://example.com/undated", "snippet": "汽车动态\n8月29日发生的一场活动，今天仍值得讨论。", "publish_time": None}
        self.assertIsNone(resolve_publication_time(item)["published_at"])
        self.assertEqual(_invalid_reason(item, "topic", [])[0], "INV008")

    def test_risk_labels_and_matcher_share_config(self) -> None:
        self.assertIn("recall", _risk_tags("官方发布产品召回通知"))
        self.assertEqual(risk_display_text("事件风险标签：recall"), "事件风险标签：产品召回")
        self.assertEqual(len(risk_rules()), 9)

    def test_company_listing_is_not_a_single_recent_event(self) -> None:
        item = result_item("东风风神系列 了解更多有关东风风神系列的内容 09月06日更新", "https://example.com/s-tag")
        self.assertEqual(_invalid_reason(item, "topic", [])[0], "INV006")
        item = result_item("新车_汽车_中国网", "https://auto.china.com.cn/newcar/index.shtml")
        self.assertEqual(_invalid_reason(item, "topic", [])[0], "INV006")
        item = result_item("领克汽车_黑猫投诉_新浪网", "https://tousu.sina.com.cn/company/view/?couid=123")
        self.assertEqual(_invalid_reason(item, "topic", [])[0], "INV006")
        item = result_item("猛士m817 - 聚合所有猛士m817相关热门新闻快讯", "https://example.com/tag")
        self.assertEqual(_invalid_reason(item, "topic", [])[0], "INV006")
        item = result_item("80万以上小型SUV自主新车第7页-最新资讯-易车", "https://example.com/list")
        self.assertEqual(_invalid_reason(item, "topic", [])[0], "INV006")

    def test_reprocess_reuses_saved_data_without_search(self) -> None:
        event_id = self._seed_event()
        run_id = get_event(event_id)["run_id"]
        with patch("service.pipeline.search_doubao") as doubao, patch("service.pipeline.search_codex_batch") as codex:
            result = reprocess(run_id)
            self.assertEqual(result["external_search_calls"], 0)
            doubao.assert_not_called()
            codex.assert_not_called()

    def test_reprocess_preserves_reviewed_results(self) -> None:
        event_id = self._seed_event()
        with connection() as db:
            db.execute("UPDATE events SET event_status='rejected' WHERE event_id=?", (event_id,))
        with self.assertRaises(RuntimeError):
            reprocess(get_event(event_id)["run_id"])
        self.assertEqual(get_event(event_id)["event_status"], "rejected")

    def test_legacy_status_migration_is_idempotent(self) -> None:
        event_id = self._seed_event()
        with connection() as db:
            db.execute("UPDATE events SET event_status='needs_evidence' WHERE event_id=?", (event_id,))
        init_database()
        init_database()
        self.assertEqual(get_event(event_id)["event_status"], "pending_review")

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
        ), patch("service.evidence_requests.search_doubao", return_value={"items": [item]}), patch("service.evidence_requests.process_work_items", return_value={"completed": 1}):
            result = execute_evidence_request(plan["evidence_request_id"])
        self.assertEqual(result["status"], "completed")
        self.assertEqual({job["provider_id"] for job in result["jobs"]}, {"codex_web_search", "doubao_global_search"})
        self.assertEqual(get_event(event_id)["event_status"], "pending_review")

    def test_approved_event_generates_complete_original_brief(self) -> None:
        event_id = self._seed_event()
        self._seed_completed_ai_output(event_id)
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
        self.assertIn("Codex AI", brief)

    def test_approved_event_requires_completed_ai_blueprint(self) -> None:
        event_id = self._seed_event()
        with self.assertRaisesRegex(ValueError, "尚未生成Codex AI研判任务"):
            review_event(
                event_id, review_result="approved", event_status="relevant_event_clue",
                reviewer="测试运营", review_note=None, evidence_summary="已核验事件事实和来源链接。",
                risk_summary="未发现阻断性风险。", recommended_action="生成原创增长草案",
                action_paths=["original_growth"], boost_source_ids=[],
            )
        with connection() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM candidate_reviews").fetchone()[0], 0)

    def test_ai_executor_calls_codex_contract_and_clamps_model_output(self) -> None:
        event_id = self._seed_event()
        item = enqueue_analysis_work_item(event_id, reason="测试真实执行器")
        raw = {
            "work_item_id": item["work_item_id"], "summary": "事件摘要", "decision_reason": "事实与品牌关系可审核",
            "content_tone": "positive", "tone_reason": "产品信息", "evidence": [
                {"source_id": "SRC-SEED", "text": "岚图汽车发布产品信息。", "url": "https://example.com/seed", "type": "ai_fact"},
                {"source_id": "SRC-INVENTED", "text": "虚构证据", "url": None, "type": "ai_fact"},
            ],
            "risk_tags": ["invented_risk"],
            "entity_mentions": [{"entity_name": "测试车型", "entity_type": "model", "evidence_source_ids": ["SRC-SEED"]}],
            "entity_uncertainties": [],
            "original_growth_blueprint": {
                "recommended": True, "reason": "适合事实解读", "task_title": "原创作业｜岚图产品信息",
                "mandatory_topics": ["#证据中不存在的话题#"], "core_proposition": "解释产品价值", "evidence_summary": "岚图汽车发布产品信息。",
                "platforms": [{"platform_id": "toutiao", "reason": "适合解读", "content_form": "图文", "guidance": "仅引用证据"}],
                "creative_directions": ["普通用户视角"], "prohibited_claims": ["不得虚构销量"], "risk_notes": [],
            },
            "source_content_boost_blueprints": [],
            "evidence_resolution": {"resolved_items": [], "unresolved_items": ["缺少平台指标"]},
        }
        with patch("service.ai_executor._run_codex", return_value=({"results": [raw]}, {"executor": "codex_cli", "model": "test"})):
            result = process_work_items([item])
        self.assertEqual(result["completed"], 1)
        completed = get_event(event_id)["work_items"][-1]
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["output"]["brand_relations"][0]["brand_id"], "BR003")
        self.assertEqual(completed["output"]["risk_tags"], [])
        self.assertEqual(completed["output"]["original_growth_blueprint"]["mandatory_topics"], [])
        self.assertEqual([e["source_id"] for e in completed["output"]["evidence"]], ["SRC-SEED"])

    def test_ai_executor_isolates_failure_and_continues_next_item(self) -> None:
        first_event_id = self._seed_event("TIMEOUT")
        second_event_id = self._seed_event("SUCCESS")
        first = enqueue_analysis_work_item(first_event_id, reason="测试超时隔离")
        second = enqueue_analysis_work_item(second_event_id, reason="测试继续执行")
        raw = {
            "work_item_id": second["work_item_id"], "summary": "第二个事件完成", "decision_reason": "证据可供人工审核",
            "content_tone": "neutral", "tone_reason": "事实描述", "evidence": [], "risk_tags": [],
            "entity_mentions": [], "entity_uncertainties": [],
            "original_growth_blueprint": {
                "recommended": False, "reason": "暂不建议", "task_title": "", "mandatory_topics": [],
                "core_proposition": "", "evidence_summary": "", "platforms": [], "creative_directions": [],
                "prohibited_claims": [], "risk_notes": [],
            },
            "source_content_boost_blueprints": [],
            "evidence_resolution": {"resolved_items": [], "unresolved_items": ["缺少平台原生指标"]},
        }
        execution = {"executor": "codex_cli", "model": "test"}
        with patch(
            "service.ai_executor._run_codex",
            side_effect=[RuntimeError("Codex AI研判超过240秒，已停止当前事件；采集和事件数据不受影响，请稍后手工重试"), ({"results": [raw]}, execution)],
        ) as run_codex:
            result = process_work_items([first, second])
        self.assertEqual(run_codex.call_count, 2)
        self.assertTrue(all(len(call.args[0]) == 1 for call in run_codex.call_args_list))
        self.assertEqual((result["completed"], result["failed"]), (1, 1))
        failed = get_event(first_event_id)["work_items"][-1]
        completed = get_event(second_event_id)["work_items"][-1]
        self.assertEqual(failed["status"], "failed")
        self.assertIn("采集和事件数据不受影响", failed["error_message"])
        self.assertNotIn("Command '[", failed["error_message"])
        self.assertEqual(completed["status"], "completed")

    def test_codex_timeout_is_reported_without_command_details(self) -> None:
        with patch("service.ai_executor.Path.exists", return_value=True), patch(
            "service.ai_executor.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd=["codex"], timeout=240),
        ):
            with self.assertRaisesRegex(RuntimeError, "采集和事件数据不受影响") as raised:
                _run_codex([{"work_item_id": "WRK-TIMEOUT"}])
        self.assertNotIn("Command '[", str(raised.exception))

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
                        original_url,canonical_url,title,snippet,published_at,fetched_at,first_seen_at,business_relation_json
                    ) VALUES (?,?,?,'[]','valid','general_web',?,?,?,?,?,?,?,?)""",
                    (
                        f"SRC-PAGE-{index:02d}", "RUN-PAGE", "doubao_global_search",
                        f"https://example.com/page/{index}", f"https://example.com/page/{index}",
                        f"岚图分页线索 {index}", "岚图汽车分页验证", timestamp, timestamp, timestamp,
                        json_text(assess_business_relation({"title": "岚图汽车分页验证"})),
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

    def _seed_event(self, suffix: str = "SEED") -> str:
        timestamp = now_iso()
        run_id = f"RUN-{suffix}"
        source_id = f"SRC-{suffix}"
        event_id = f"EVT-{suffix}"
        source_url = f"https://example.com/{suffix.lower()}"
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
                (source_id, run_id, "doubao_global_search", source_url, source_url, "岚图汽车产品信息", "公开事实", timestamp, timestamp),
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
                (f"EVD-{suffix}", event_id, source_id, "source_excerpt", "岚图汽车发布产品信息。", source_url, "test", timestamp),
            )
        return event_id

    def _seed_completed_ai_output(self, event_id: str) -> str:
        item = enqueue_analysis_work_item(event_id, reason="测试AI研判")
        claim_work_item(item["work_item_id"], "test-ai")
        complete_work_item(item["work_item_id"], "test-ai", {
            "summary": "岚图汽车发布产品信息，事实可供运营审核。",
            "decision_reason": "来源正文直接涉及岚图汽车，但公开搜索不能证明真实热度。",
            "evidence": [], "risk_tags": [], "entity_mentions": [], "entity_uncertainties": [],
            "brand_relations": [{"brand_id": "BR003", "brand_name": "岚图汽车", "relation_status": "direct_mention"}],
            "content_tone": "positive", "tone_reason": "内容为产品发布信息。",
            "original_growth_blueprint": {
                "recommended": True, "reason": "具备品牌事实与可解释价值。", "task_title": "原创作业｜岚图汽车产品信息",
                "mandatory_topics": [], "core_proposition": "围绕已核验产品信息解释用户价值。",
                "evidence_summary": "岚图汽车发布产品信息。",
                "platforms": [{"platform_id": "toutiao", "reason": "适合完整事实解读", "content_form": "中短图文", "guidance": "先结论后依据，不扩大未核验信息"}],
                "creative_directions": ["从普通用户视角解释事件价值"],
                "prohibited_claims": ["不得补造销量"], "risk_notes": ["真实热点不可判定"],
            },
            "source_content_boost_blueprints": [],
            "evidence_resolution": {"resolved_items": [], "unresolved_items": ["缺少平台原生热度数据"]},
            "execution": {"executor": "test"},
        })
        return item["work_item_id"]


if __name__ == "__main__":
    unittest.main()
