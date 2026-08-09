# 广东公考、事业编与国企招聘监控 Skill

面向广东省、重点覆盖广州市的公开招聘信息收集工具。仓库预置 **55 个来源入口**，包括国家与广东省主管平台、广东 21 个地级市、广州市主干栏目、广州 11 个区，以及教育、卫生健康、国资等高频行业来源。

它解决三件事：每天发现公告变化、保留来源健康证据、把已核验信息整理进可筛选的 Excel 台账。自动发现只是线索层；报名条件、具体时间和材料要求仍须打开官方公告及附件复核。

## 覆盖范围

- 公务员、选调生、参公人员；
- 事业单位在编招聘；
- 事业单位编外、雇员、劳务派遣等非编制岗位；
- 省属、市属国企公开招聘线索；
- 报名、更正、准考证、笔试、成绩、资格复审、面试、体检考察、拟录聘公示和补录。

不同用工性质不会混在一起。国企岗位不称为“企业编制”，编外岗位也不会误标为事业编。

## 直接使用

要求：Python 3.11 或更新版本。监控脚本只使用 Python 标准库。

```bash
python3 scripts/monitor.py \
  --sources references/official-sources.json \
  --data-dir data
```

首次自建仓库时使用 `--baseline`，把现有链接登记为历史基线，避免几百条旧公告触发首日报警。此仓库已经建立基线，日常运行不要再加该参数。

输出文件：

- `data/daily-report.md`：本次检查摘要与失败来源；
- `data/notices.csv`：网页发现层的候选公告；
- `data/source_health.csv`：每个来源的访问状态；
- `data/state.json`：去重状态。

Excel 主模板位于 `assets/广东公考事业编监控台账.xlsx`，包含使用说明、仪表盘、招考机会、关键时间点、信息源地图、材料清单、个人条件和字段说明。先复制一份再填写；已填写的个人条件和证件材料不要提交到公开仓库。

## 作为 Codex Skill 安装

把本仓库克隆到 Codex 的 Skills 目录，目录名保持为 `guangdong-public-jobs-monitor`：

```bash
git clone <本仓库地址> ~/.codex/skills/guangdong-public-jobs-monitor
```

然后可以这样使用：

> 使用 `$guangdong-public-jobs-monitor` 检查今天广东和广州的公务员、事业编、编外与国企招聘变化，先报告失败源，再列出新公告并提醒所有后续时间点。

完整执行规范见 [`SKILL.md`](SKILL.md)。

## 开启 GitHub 每日监控

仓库带有 `.github/workflows/daily-monitor.yml`：

- 北京时间每天 08:15、18:15 自动检查；
- 把公开监控数据提交回仓库；
- 发现基线之后的新链接时自动创建 GitHub Issue；
- 也支持在 Actions 页面手动运行。

Fork 后请在仓库的 **Actions** 页面启用工作流，并在 **Settings → Actions → General → Workflow permissions** 允许 GitHub Actions 读写仓库内容；Issues 也需要保持启用。定时任务可能延迟，因此临近截止的项目必须再打开官方页面确认。

## 信息完整性设计

“全”按可审计覆盖定义：主干汇总源兜底，广东 21 个地级市补齐自行招聘，广州 11 区加密属地流程，行业主管部门补齐教师、医疗卫生和国资岗位，再从每条新公告继续追踪招聘单位官网。每次运行都报告 A 级来源成功率、失联来源和人工补查入口，不把访问失败解释成“今天没有公告”。

来源地图与增删规则：

- [`references/source-map.md`](references/source-map.md)
- [`references/operations-plan.md`](references/operations-plan.md)
- [`references/official-sources.json`](references/official-sources.json)
- [`references/verification-rules.md`](references/verification-rules.md)
- [`references/data-schema.md`](references/data-schema.md)

## 安全边界

- 不绕过验证码、登录、限流或访问控制；
- 不把商业培训资料标为官方资料；
- 不在公开仓库保存身份证号、手机号、住址、证件扫描件或报名截图；
- 自动分类只用于初筛，最终以最新官方原文和附件为准。

## 许可

代码和模板采用 [MIT License](LICENSE)。政府公告与附件的权利归原发布机构所有，本仓库只保存公开链接和必要的结构化索引。
