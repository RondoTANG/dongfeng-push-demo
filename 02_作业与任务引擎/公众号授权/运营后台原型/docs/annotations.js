// 护卫军原型工程 - 全局批注数据字典
// 【注意】此文件由 scripts/build.py 自动根据 docs/modules 下的 Markdown 文件生成，请勿手动修改！
const PRD_ANNOTATIONS = {
    "wizard_step3_cascade": {
        "title": "向导化新建作业 - 第三步关联控制",
        "definition": "限制只有当第一步明确为“公众号任务”并选择品牌后，才能在第三步打开图文选取弹窗。",
        "dataSource": "",
        "logic": "",
        "interaction": "若未选择，则此处“选取已群发文章”按钮 `disabled`，点击时冒泡提示“请先返回第一步选择品牌”。",
        "fields": ""
    },
    "wizard_step4_quota": {
        "title": "额度预估与发布控制",
        "definition": "作业发布前，根据受众与策略扣减虚拟额度。",
        "dataSource": "",
        "logic": "",
        "interaction": "发布前动态计算“预估覆盖人数”。若品牌通知额度不足，【发布作业】按钮不可用，并标红提示差额。",
        "fields": ""
    },
    "wechat_auth_status": {
        "title": "公众号授权状态监控",
        "definition": "展示当前绑定公众号的 Token 存活性。",
        "dataSource": "",
        "logic": "",
        "interaction": "正常监听为绿色。如 Token 失效或被解绑，标记为红色“已失效”，并高亮引导重新扫码的入口。",
        "fields": ""
    },
    "wechat_scan_auth": {
        "title": "新公众号扫码授权",
        "definition": "接入新的公众号矩阵，通过生成二维码引导管理员扫码。",
        "dataSource": "",
        "logic": "",
        "interaction": "扫码成功后的回调需二次确认是否包含“群发与发布权限”及“消息管理权限”，若缺项则前端抛出 Toast 弹窗报错。",
        "fields": ""
    },
    "article_link_status": {
        "title": "已群发文章的作业关联状态",
        "definition": "展示所有监听公众号的推文历史，并指示是否已经生成了推送作业。",
        "dataSource": "",
        "logic": "",
        "interaction": "分为“未关联”和“已关联”。未关联时主色调为原色，显示“生成推送作业”主操作；已关联时，整个卡片降低透明度至 80%，按钮变为次级的“查看作业看板”。",
        "fields": ""
    }
};
