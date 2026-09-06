"""离线重新清洗已完成批次，不重复调用搜索；拒绝覆盖人工审核与补证。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from datetime import datetime
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from service.database import connection, add_audit, json_text, new_id, now_iso
from service.config_loader import config_versions
from service.pipeline import _invalid_reason, _match_brands, _finish_run
from service.events import aggregate_run
from service.source_time import resolve_publication_time
from service.business_relation import assess_business_relation


def reprocess(run_id: str) -> dict:
    with connection() as db:
        run = db.execute('SELECT * FROM collection_runs WHERE run_id=?', (run_id,)).fetchone()
        if not run or run['status'] == 'running':
            raise RuntimeError('批次不存在或仍在运行，不允许重新处理')
        events = 'SELECT event_id FROM events WHERE run_id=?'
        for table in ('candidate_reviews', 'task_drafts', 'evidence_requests'):
            if db.execute(f'SELECT count(*) FROM {table} WHERE event_id IN ({events})', (run_id,)).fetchone()[0]:
                raise RuntimeError('本批次已有人工审核、草案或补证，禁止覆盖')
        if db.execute(f"SELECT count(*) FROM codex_work_items WHERE event_id IN ({events}) AND status!='pending'", (run_id,)).fetchone()[0]:
            raise RuntimeError('已有人工处理的工作项，禁止覆盖')
        if db.execute("SELECT count(*) FROM events WHERE run_id=? AND event_status!='pending_review'", (run_id,)).fetchone()[0]:
            raise RuntimeError('已有非待审核事件，禁止覆盖')
        db.execute(f'DELETE FROM event_evidence WHERE event_id IN ({events})', (run_id,))
        db.execute(f'DELETE FROM codex_work_items WHERE event_id IN ({events})', (run_id,))
        db.execute('UPDATE source_items SET event_id=NULL WHERE run_id=?', (run_id,))
        db.execute('DELETE FROM events WHERE run_id=?', (run_id,))
        db.execute('DELETE FROM invalid_logs WHERE run_id=?', (run_id,))
        counts = {'valid': 0, 'invalid': 0}
        for row in db.execute('SELECT * FROM source_items WHERE run_id=?', (run_id,)).fetchall():
            basis = json.loads(row['publication_time_basis_json'] or '{}')
            item = {'url': row['original_url'], 'title': row['title'], 'snippet': row['snippet'], 'publish_time': basis.get('provider_value') or row['published_at']}
            groups = db.execute('SELECT DISTINCT q.query_group FROM source_discoveries d JOIN query_jobs q ON q.query_job_id=d.query_job_id WHERE d.source_id=?', (row['source_id'],)).fetchall()
            group = 'topic' if any(g[0] == 'topic' for g in groups) else 'brand'
            reference = datetime.fromisoformat(run['started_at'])
            reason = _invalid_reason(item, group, _match_brands(f"{row['title']}\n{row['snippet']}"), reference)
            status = 'invalid' if reason else 'valid'
            resolved = resolve_publication_time(item, reference)
            db.execute('UPDATE source_items SET source_status=?,published_at=?,published_time_confidence=?,publication_time_basis_json=? WHERE source_id=?', (status, resolved['published_at'], resolved['confidence'], json_text(resolved), row['source_id']))
            counts[status] += 1
            db.execute('UPDATE source_items SET business_relation_json=? WHERE source_id=?', (json_text(assess_business_relation(item)), row['source_id']))
            if reason:
                db.execute('INSERT INTO invalid_logs(invalid_id,run_id,source_id_or_raw_result_id,invalid_rule_id,invalid_reason,discarded_at) VALUES(?,?,?,?,?,?)', (new_id('INV'), run_id, row['source_id'], reason[0], reason[1], now_iso()))
    # 原始响应、查询任务与发现记录完整保留。当前规则版本单独留痕，不冒充首次搜索版本。
    aggregated = aggregate_run(run_id)
    _finish_run(run_id, error_message=run['error_message'])
    with connection() as db:
        db.execute('UPDATE collection_runs SET finished_at=? WHERE run_id=?', (run['finished_at'], run_id))
    result = {'run_id': run_id, 'sources': counts, 'aggregation': aggregated, 'processing_config_versions': config_versions(), 'external_search_calls': 0}
    add_audit('reprocess', 'collection_run', run_id, actor_id='local-maintenance', after=result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--confirm-reprocess', action='store_true', required=True)
    args = parser.parse_args()
    print(json.dumps(reprocess(args.run_id), ensure_ascii=False, indent=2))
