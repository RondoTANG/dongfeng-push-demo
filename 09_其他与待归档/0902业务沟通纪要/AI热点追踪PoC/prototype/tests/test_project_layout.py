"""目录迁移及显示组件回归；不调用搜索、不修改业务数据库。"""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from service.settings import HOTSPOT_RULE_PATH, POC_ROOT
from service.config_loader import load_configs


class ProjectLayoutTest(unittest.TestCase):
    def test_only_current_config_is_loaded(self):
        self.assertEqual(HOTSPOT_RULE_PATH, POC_ROOT / "config" / "热点总控配置.yaml")
        self.assertTrue(HOTSPOT_RULE_PATH.is_file())
        self.assertFalse((POC_ROOT / "热点采集规则_v0.2.yaml").exists())
        self.assertFalse((POC_ROOT / "热点采集规则_v0.1.yaml").exists())
        self.assertTrue((POC_ROOT / "archive/config/热点采集规则_v0.1.yaml").is_file())
        self.assertTrue((POC_ROOT / "archive/planning/_module-plan.md").is_file())
        for ref in load_configs()["hotspot"]["config_refs"].values():
            self.assertTrue((HOTSPOT_RULE_PATH.parent / ref).is_file())

    def test_validator_independent_of_working_directory(self):
        with tempfile.TemporaryDirectory() as cwd:
            result = subprocess.run(["python3", str(POC_ROOT / "validate_config.py")], cwd=cwd, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["success"])

    def test_rendering_preserves_distinct_evidence_and_escapes_content(self):
        common = POC_ROOT / "prototype/js/common.js"
        script = r"""
const fs = require('fs'), vm = require('vm'), assert = require('assert');
global.window = {};
vm.runInThisContext(fs.readFileSync(process.argv[1], 'utf8'));
const common = window.AppCommon;
const excerpt = '同一来源明确说明事件事实。'.repeat(15);
const html = common.renderRelationEvidence({reason:'依据', relations:[
  {brand_name:'东风汽车', evidence_excerpt:excerpt},
  {brand_name:'东风日产', evidence_excerpt:excerpt + '补充'},
  {brand_name:'岚图汽车', evidence_excerpt:'独立的另一段事实，不得误合并'}
]});
assert.equal((html.match(/relation-evidence-group/g)||[]).length, 2);
assert(html.includes('东风汽车') && html.includes('东风日产') && html.includes('岚图汽车'));
const brief = common.renderTaskBrief('说明\n\n一、作业详情\n1. 核心命题：真实内容\n\n二、平台指引\n- 微博：原创表达\n<script>alert(1)</script>');
assert.equal((brief.match(/<h4>/g)||[]).length, 2);
assert(brief.includes('brief-item-label'));
assert(!brief.includes('<script>'));
assert(brief.includes('&lt;script&gt;'));
assert(common.renderTaskBrief('普通文字').includes('普通文字'));
"""
        result = subprocess.run(["node", "-e", script, str(common)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_access_control_and_configurable_automation_are_wired(self):
        prototype = POC_ROOT / "prototype"
        automation = json.loads((prototype / "config/automation.json").read_text(encoding="utf-8"))
        nav = json.loads((prototype / "config/nav.json").read_text(encoding="utf-8"))
        self.assertFalse(automation["enabled"])
        self.assertEqual(automation["interval_hours"], 3)
        self.assertIn("管理员开启", automation["schedule"])
        access_item = next(item for section in nav["menu"] for item in section["children"] if item["key"] == "access-keys")
        self.assertTrue(access_item["adminOnly"])
        css = (prototype / "assets/css/app.css").read_text(encoding="utf-8")
        self.assertIn("body.nav-open .app-sidebar", css)
        self.assertNotIn("min-width: 720px", css)
        app_source = (prototype / "service/app.py").read_text(encoding="utf-8")
        self.assertIn('pattern="^manual$"', app_source)
        self.assertIn('/api/automation/config', app_source)
        self.assertIn('/api/config/queries', app_source)

    def test_server_delivery_is_self_contained_and_persistent(self):
        prototype = POC_ROOT / "prototype"
        for name in ("README.md", "runtime.env.example", "ai-hotspot-poc.service", "cloudflared-ingress.example.yml", "deploy.env.example", "deploy_from_mac.sh"):
            self.assertTrue((prototype / "deployment" / name).is_file())
        settings_source = (prototype / "service/settings.py").read_text(encoding="utf-8")
        self.assertIn("AI_HOTSPOT_DATA_DIR", settings_source)
        self.assertIn("AI_HOTSPOT_CONFIG_DIR", settings_source)
        search_source = (POC_ROOT / "run_doubao_search.py").read_text(encoding="utf-8")
        self.assertIn("prototype\" / \"service\" / \"doubao_result_processor.py", search_source)
        self.assertNotIn("03_审核与AI中台", search_source)
        self.assertTrue((prototype / "service/doubao_result_processor.py").is_file())
        effects_source = (prototype / "js/pages/effects.js").read_text(encoding="utf-8")
        self.assertIn("data-mobile-effect-back", effects_source)
        self.assertIn("effect-workspace", effects_source)
        css = (prototype / "assets/css/app.css").read_text(encoding="utf-8")
        self.assertIn(".event-detail-head > .page-head__actions:not(:empty)", css)
        self.assertIn("env(safe-area-inset-bottom)", css)


if __name__ == "__main__":
    unittest.main()
