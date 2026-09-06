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


if __name__ == "__main__":
    unittest.main()
