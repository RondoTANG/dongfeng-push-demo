import json
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from service import automation, config_admin, config_loader
from service.settings import POC_ROOT


class ConfigManagementTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.config_dir = Path(self.temporary.name) / "config"
        shutil.copytree(POC_ROOT / "config", self.config_dir)
        self.original_admin_dir = config_admin.SOURCE_CONFIG_DIR
        self.original_loader_dir = config_loader.SOURCE_CONFIG_DIR
        self.original_hotspot_path = config_loader.HOTSPOT_RULE_PATH
        config_admin.SOURCE_CONFIG_DIR = self.config_dir
        config_loader.SOURCE_CONFIG_DIR = self.config_dir
        config_loader.HOTSPOT_RULE_PATH = self.config_dir / "热点总控配置.yaml"
        config_loader.reload_configs()

    def tearDown(self):
        config_admin.SOURCE_CONFIG_DIR = self.original_admin_dir
        config_loader.SOURCE_CONFIG_DIR = self.original_loader_dir
        config_loader.HOTSPOT_RULE_PATH = self.original_hotspot_path
        config_loader.reload_configs()
        self.temporary.cleanup()

    def test_query_crud_writes_yaml_and_reloads_runtime(self):
        created = config_admin.upsert_query({
            "query_id": "T99", "query_group": "topic", "topic_id": "test_topic",
            "query": "测试行业主题 最新动态", "enabled": True,
        }, create_only=True)
        self.assertEqual(created["query_id"], "T99")
        self.assertIn("T99", {item["query_id"] for item in config_loader.query_catalog()})
        with self.assertRaisesRegex(ValueError, "已存在"):
            config_admin.upsert_query({
                "query_id": "T99", "query_group": "topic", "topic_id": "test_topic",
                "query": "重复编号", "enabled": True,
            }, create_only=True)
        config_admin.delete_query("T99")
        self.assertNotIn("T99", {item["query_id"] for item in config_loader.query_catalog()})

    def test_referenced_brand_and_platform_cannot_be_deleted(self):
        with self.assertRaisesRegex(ValueError, "品牌查询引用"):
            config_admin.delete_brand("BR001")
        with self.assertRaisesRegex(ValueError, "域名规则引用"):
            config_admin.delete_platform("douyin")
        with self.assertRaisesRegex(ValueError, "兜底平台"):
            config_admin.delete_platform("unknown")

    def test_enabled_brand_query_requires_active_brand(self):
        config_admin.upsert_brand({
            "brand_id": "BR099", "canonical_name": "测试停用品牌", "status": "inactive",
        }, create_only=True)
        with self.assertRaisesRegex(ValueError, "启用品牌"):
            config_admin.upsert_query({
                "query_id": "B99", "query_group": "brand", "brand_id": "BR099",
                "query": "测试停用品牌 最新动态", "enabled": True,
            }, create_only=True)


class AutomationConfigTest(unittest.TestCase):
    def test_automation_defaults_stopped_and_persists_interval(self):
        with tempfile.TemporaryDirectory() as cwd:
            path = Path(cwd) / "automation.json"
            seed = Path(cwd) / "seed.json"
            seed.write_text(json.dumps({"enabled": False, "interval_hours": 3}), encoding="utf-8")
            with patch.object(automation, "AUTOMATION_CONFIG_PATH", path), \
                    patch.object(automation, "AUTOMATION_SEED_PATH", seed), \
                    patch.object(automation, "add_audit"):
                initial = automation.load_automation_config()
                self.assertFalse(initial["enabled"])
                enabled = automation.update_automation_config(enabled=True, interval_hours=6, actor_id="test-admin")
                self.assertTrue(enabled["enabled"])
                self.assertEqual(enabled["interval_hours"], 6)
                self.assertIsNotNone(enabled["next_run_at"])
                stopped = automation.update_automation_config(enabled=False, interval_hours=6, actor_id="test-admin")
                self.assertFalse(stopped["enabled"])
                self.assertIsNone(stopped["next_run_at"])

    def test_scheduled_run_respects_full_run_cooldown(self):
        now = datetime.now().astimezone()
        next_allowed = (now + timedelta(hours=2)).isoformat(timespec="seconds")
        config = {
            "enabled": True,
            "interval_hours": 1,
            "mode": "full",
            "next_run_at": (now - timedelta(minutes=1)).isoformat(timespec="seconds"),
        }
        with patch.object(automation, "load_automation_config", return_value=config), \
                patch.object(automation, "_has_running_collection", return_value=False), \
                patch.object(automation, "run_cooldown", return_value={"allowed": False, "next_allowed_at": next_allowed}), \
                patch.object(automation, "_atomic_write") as write_config, \
                patch.object(automation, "reserve_collection_run") as reserve:
            self.assertIsNone(automation._claim_due_run())
        reserve.assert_not_called()
        self.assertEqual(config["next_run_at"], next_allowed)
        write_config.assert_called_once()


if __name__ == "__main__":
    unittest.main()
