#!/usr/bin/env python3
"""Polite, dependency-free link monitor for public recruitment source pages."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import ssl
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")
DATE_PATTERNS = [
    re.compile(r"(?P<y>20\d{2})[-/.](?P<m>\d{1,2})[-/.](?P<d>\d{1,2})"),
    re.compile(r"(?P<y>20\d{2})年(?P<m>\d{1,2})月(?P<d>\d{1,2})日"),
]
TRACKING_KEYS = {"from", "source", "utm_source", "utm_medium", "utm_campaign", "eqid"}
NOTICE_FIELDS = [
    "notice_id", "source_id", "source_name", "authority_level", "region",
    "source_category", "title", "url", "published_date", "inferred_job_type",
    "inferred_stage", "first_seen", "last_seen", "current_run_new",
    "verification_status",
]
HEALTH_FIELDS = [
    "checked_at", "source_id", "source_name", "authority_level", "region", "url",
    "status", "http_status", "elapsed_ms", "candidate_links", "error",
]


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        values = dict(attrs)
        self._href = values.get("href")
        self._parts = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            title = normalize_text(" ".join(self._parts))
            self.links.append((self._href, title))
            self._href = None
            self._parts = []


@dataclass
class FetchResult:
    body: str
    status: int
    elapsed_ms: int


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()


def canonical_url(value: str) -> str:
    parts = urlsplit(value)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k.lower() not in TRACKING_KEYS]
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


def decode_body(raw: bytes, content_type: str) -> str:
    candidates: list[str] = []
    header_match = re.search(r"charset=([\w-]+)", content_type or "", re.I)
    if header_match:
        candidates.append(header_match.group(1))
    head = raw[:4096].decode("ascii", errors="ignore")
    meta_match = re.search(r"charset\s*=\s*[\"']?([\w-]+)", head, re.I)
    if meta_match:
        candidates.append(meta_match.group(1))
    candidates.extend(["utf-8", "gb18030"])
    for encoding in dict.fromkeys(candidates):
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


def fetch(url: str, timeout: float) -> FetchResult:
    started = time.monotonic()
    request = Request(
        url,
        headers={
            "User-Agent": "GuangdongPublicJobsMonitor/1.0 (+GitHub Skill; twice-daily public-page check)",
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.8,*/*;q=0.5",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.5",
        },
    )
    context = ssl.create_default_context()
    with urlopen(request, timeout=timeout, context=context) as response:
        raw = response.read(5_000_000)
        body = decode_body(raw, response.headers.get("Content-Type", ""))
        elapsed = int((time.monotonic() - started) * 1000)
        return FetchResult(body=body, status=response.getcode() or 200, elapsed_ms=elapsed)


def infer_date(context: str) -> str:
    for pattern in DATE_PATTERNS:
        match = pattern.search(context)
        if match:
            try:
                return datetime(int(match.group("y")), int(match.group("m")), int(match.group("d"))).date().isoformat()
            except ValueError:
                continue
    return ""


def infer_job_type(title: str) -> str:
    if re.search(r"编外|雇员|辅助人员|合同制|劳务派遣|购买服务|社区专职", title):
        return "编外"
    if "选调优秀大学毕业生" in title or "选调生" in title:
        return "选调生"
    if re.search(r"参照公务员法|参公", title):
        return "参公"
    if re.search(r"公务员|考录", title):
        return "公务员"
    if re.search(r"事业单位|事业编|编制人员|编制教师", title):
        return "事业编"
    if re.search(r"国企|集团|有限公司", title):
        return "国企"
    return "待核实"


def infer_stage(title: str) -> str:
    ordered = [
        (r"取消|暂停|延期|恢复", "取消暂停/时间变更"),
        (r"更正|补充说明|补充公告", "补充更正"),
        (r"补充录用|补录", "补充录用"),
        (r"拟录用|拟聘用|拟聘人员|公示", "录聘公示"),
        (r"体检|考察", "体检考察"),
        (r"面试", "面试"),
        (r"资格复审|资格审核|资格审查", "资格复审"),
        (r"成绩|合格分数线", "成绩"),
        (r"准考证|笔试安排|笔试公告", "准考证/笔试"),
        (r"报名|报考", "报名"),
    ]
    for pattern, stage in ordered:
        if re.search(pattern, title):
            return stage
    return "首发/其他"


def extract_links(body: str, base_url: str, include: Iterable[str], exclude: Iterable[str], max_links: int) -> list[dict[str, str]]:
    parser = LinkParser()
    parser.feed(body)
    include_terms = tuple(include)
    exclude_terms = tuple(exclude)
    output: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for href, title in parser.links:
        if not title or len(title) < 6:
            continue
        if not any(term in title for term in include_terms):
            continue
        if any(term in title for term in exclude_terms):
            continue
        absolute = urljoin(base_url, href)
        if urlsplit(absolute).scheme not in {"http", "https"}:
            continue
        absolute = canonical_url(absolute)
        if absolute in seen_urls:
            continue
        seen_urls.add(absolute)
        pos = body.find(href)
        context = normalize_text(re.sub(r"<[^>]+>", " ", body[max(0, pos - 260):pos + len(href) + 380])) if pos >= 0 else title
        output.append({"title": title, "url": absolute, "published_date": infer_date(context + " " + title)})
        if len(output) >= max_links:
            break
    return output


def make_notice_id(title: str, url: str) -> str:
    stable = normalize_text(re.sub(r"[（(]?第[一二三四五六七八九十\d]+批[）)]?", "", title))
    return hashlib.sha256(f"{stable}\n{canonical_url(url)}".encode("utf-8")).hexdigest()[:16]


def load_csv(path: Path, key: str) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {row[key]: row for row in csv.DictReader(handle) if row.get(key)}


def write_csv(path: Path, fields: list[str], rows: Iterable[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def render_report(now_text: str, new_rows: list[dict[str, str]], health: list[dict[str, object]], baseline_count: int) -> str:
    successful = sum(1 for row in health if row["status"] == "ok")
    failed = sum(1 for row in health if row["status"] == "failed")
    skipped = sum(1 for row in health if row["status"] == "manual")
    a_rows = [row for row in health if row["authority_level"] == "A" and row["status"] != "manual"]
    a_ok = sum(1 for row in a_rows if row["status"] == "ok")
    lines = [
        "# 广东公考事业编每日监控报告",
        "",
        f"- 核验时间：{now_text}（Asia/Shanghai）",
        f"- 自动检查：成功 {successful}，失败 {failed}，人工入口 {skipped}",
        f"- A 级来源成功率：{a_ok}/{len(a_rows)}" if a_rows else "- A 级来源成功率：无可自动检查来源",
        f"- 本次新增：{len(new_rows)}",
    ]
    if baseline_count:
        lines.append(f"- 首次基线载入：{baseline_count} 条（未作为新增提醒）")
    lines.extend(["", "## 新发现"])
    if not new_rows:
        lines.append("")
        lines.append("本次未发现新的候选公告链接。此结论只表示成功访问来源的页面未出现新链接；失败来源需人工补查。")
    else:
        for row in new_rows[:60]:
            date_text = row["published_date"] or "日期待核验"
            lines.append(f"- [{row['title']}]({row['url']}) — {row['region']} / {row['inferred_job_type']} / {date_text}")
        if len(new_rows) > 60:
            lines.append(f"- 另有 {len(new_rows) - 60} 条，见 `data/notices.csv`。")
    lines.extend(["", "## 失败来源"])
    failures = [row for row in health if row["status"] == "failed"]
    if not failures:
        lines.extend(["", "无。"])
    else:
        for row in failures:
            lines.append(f"- {row['source_name']}：{row['error']}")
    lines.extend(["", "## 人工补查入口"])
    manual_rows = [row for row in health if row["status"] == "manual"]
    if not manual_rows:
        lines.extend(["", "无。"])
    else:
        for row in manual_rows:
            lines.append(f"- [{row['source_name']}]({row['url']})：{row['error']}")
    lines.extend(["", "> 自动发现不等于完成资格核验。报名时间、岗位条件和材料要求必须打开官方原文及附件复核。", ""])
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", default="references/official-sources.json")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--source-id", action="append", help="Only check one or more source IDs")
    parser.add_argument("--baseline", action="store_true", help="Seed state without emitting new alerts")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--delay", type=float, default=0.6)
    parser.add_argument("--max-links", type=int, default=30)
    parser.add_argument("--limit", type=int, help="Limit enabled sources for diagnostics")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_path = Path(args.sources)
    data_dir = Path(args.data_dir)
    runtime_dir = data_dir.parent / ".runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    config = json.loads(source_path.read_text(encoding="utf-8"))
    include = config["default_include_keywords"]
    exclude = config["default_exclude_keywords"]
    selected = [source for source in config["sources"] if source.get("enabled", True)]
    if args.source_id:
        wanted = set(args.source_id)
        selected = [source for source in selected if source["source_id"] in wanted]
    if args.limit:
        selected = selected[:args.limit]

    now = datetime.now(SHANGHAI)
    now_text = now.isoformat(timespec="seconds")
    notices_path = data_dir / "notices.csv"
    existing = load_csv(notices_path, "notice_id")
    for row in existing.values():
        row["current_run_new"] = "否"
    state_path = data_dir / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {"schema_version": 1, "seen": {}}
    state.setdefault("seen", {})
    health: list[dict[str, object]] = []
    new_rows: list[dict[str, str]] = []
    baseline_count = 0

    for index, source in enumerate(selected):
        if not source.get("monitor", True):
            manual_reason = source.get("manual_reason") or source.get("notes") or "按来源登记规则人工核验"
            health.append({
                "checked_at": now_text, "source_id": source["source_id"], "source_name": source["name"],
                "authority_level": source["authority_level"], "region": source["region"], "url": source["url"],
                "status": "manual", "http_status": "", "elapsed_ms": "", "candidate_links": "",
                "error": manual_reason,
            })
            continue
        try:
            result = fetch(source["url"], args.timeout)
            links = extract_links(result.body, source["url"], source.get("include_keywords", include), source.get("exclude_keywords", exclude), args.max_links)
            health.append({
                "checked_at": now_text, "source_id": source["source_id"], "source_name": source["name"],
                "authority_level": source["authority_level"], "region": source["region"], "url": source["url"],
                "status": "ok", "http_status": result.status, "elapsed_ms": result.elapsed_ms,
                "candidate_links": len(links), "error": "",
            })
            for link in links:
                notice_id = make_notice_id(link["title"], link["url"])
                is_unseen = notice_id not in state["seen"]
                first_seen = state["seen"].get(notice_id, {}).get("first_seen", now_text)
                row = {
                    "notice_id": notice_id,
                    "source_id": source["source_id"],
                    "source_name": source["name"],
                    "authority_level": source["authority_level"],
                    "region": source["region"],
                    "source_category": source["source_category"],
                    "title": link["title"],
                    "url": link["url"],
                    "published_date": link["published_date"],
                    "inferred_job_type": infer_job_type(link["title"]),
                    "inferred_stage": infer_stage(link["title"]),
                    "first_seen": first_seen,
                    "last_seen": now_text,
                    "current_run_new": "是" if is_unseen and not args.baseline else "否",
                    "verification_status": existing.get(notice_id, {}).get("verification_status", "待打开原文及附件核验"),
                }
                if notice_id in existing:
                    original = existing[notice_id]
                    original.update(row)
                    row = original
                existing[notice_id] = row
                state["seen"][notice_id] = {"first_seen": first_seen, "last_seen": now_text, "url": link["url"]}
                if is_unseen and args.baseline:
                    baseline_count += 1
                elif is_unseen:
                    new_rows.append(row)
        except (HTTPError, URLError, TimeoutError, ssl.SSLError, ValueError) as exc:
            code = getattr(exc, "code", "")
            health.append({
                "checked_at": now_text, "source_id": source["source_id"], "source_name": source["name"],
                "authority_level": source["authority_level"], "region": source["region"], "url": source["url"],
                "status": "failed", "http_status": code, "elapsed_ms": "", "candidate_links": 0,
                "error": normalize_text(str(exc))[:300],
            })
        if args.delay > 0 and index < len(selected) - 1:
            time.sleep(args.delay)

    ordered_notices = sorted(existing.values(), key=lambda row: (row.get("first_seen", ""), row.get("published_date", ""), row.get("title", "")), reverse=True)
    write_csv(notices_path, NOTICE_FIELDS, ordered_notices)
    write_csv(data_dir / "source_health.csv", HEALTH_FIELDS, health)
    state["last_run"] = now_text
    state["source_registry_verified_on"] = config.get("verified_on", "")
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (data_dir / "daily-report.md").write_text(render_report(now_text, new_rows, health, baseline_count), encoding="utf-8")
    (runtime_dir / "new-count.txt").write_text(f"{len(new_rows)}\n", encoding="utf-8")
    (runtime_dir / "run-date.txt").write_text(now.date().isoformat() + "\n", encoding="utf-8")

    successful = sum(1 for row in health if row["status"] == "ok")
    failed = sum(1 for row in health if row["status"] == "failed")
    print(json.dumps({"checked": len(health), "successful": successful, "failed": failed, "new": len(new_rows), "baseline": baseline_count}, ensure_ascii=False))
    return 2 if selected and successful == 0 else 0


if __name__ == "__main__":
    sys.exit(main())
