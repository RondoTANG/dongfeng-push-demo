import json
import os

class StorageManager:
    def __init__(self, base_path):
        self.base_path = base_path
        self.accounts_file = os.path.join(base_path, 'accounts.json')
        self.jobs_file = os.path.join(base_path, 'jobs.json')
        self._init_files()

    def _init_files(self):
        if not os.path.exists(self.accounts_file):
            with open(self.accounts_file, 'w', encoding='utf-8') as f:
                json.dump([], f)
        if not os.path.exists(self.jobs_file):
            with open(self.jobs_file, 'w', encoding='utf-8') as f:
                json.dump([], f)

    def load_accounts(self):
        with open(self.accounts_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def save_accounts(self, accounts):
        with open(self.accounts_file, 'w', encoding='utf-8') as f:
            json.dump(accounts, f, ensure_ascii=False, indent=4)

    def load_jobs(self):
        with open(self.jobs_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def save_job(self, job):
        jobs = self.load_jobs()
        # 依据 ArticleUrl (即 job['url']) 发起全局去重校验
        if not any(j.get('url') == job.get('url') for j in jobs):
            jobs.append(job)
            with open(self.jobs_file, 'w', encoding='utf-8') as f:
                json.dump(jobs, f, ensure_ascii=False, indent=4)
            return True
        return False
