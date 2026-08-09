import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "monitor.py"
SPEC = importlib.util.spec_from_file_location("monitor", SCRIPT)
monitor = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = monitor
SPEC.loader.exec_module(monitor)


class MonitorTests(unittest.TestCase):
    def test_extract_and_classify(self):
        page = """
        <ul><li><a href="/notice/1.html">广州市天河区2026年公开招聘事业单位工作人员公告</a>
        <span>2026-07-23</span></li>
        <li><a href="/buy/2.html">招聘考务服务项目比选公告</a></li></ul>
        """
        links = monitor.extract_links(page, "https://example.gov.cn/list/", ["招聘"], ["比选公告"], 10)
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["url"], "https://example.gov.cn/notice/1.html")
        self.assertEqual(links[0]["published_date"], "2026-07-23")
        self.assertEqual(monitor.infer_job_type(links[0]["title"]), "事业编")

    def test_employment_types_do_not_mix(self):
        self.assertEqual(monitor.infer_job_type("公开招聘政府雇员公告"), "编外")
        self.assertEqual(monitor.infer_job_type("广东省考试录用公务员公告"), "公务员")
        self.assertEqual(monitor.infer_job_type("选调优秀大学毕业生公告"), "选调生")
        self.assertEqual(monitor.infer_job_type("某市属国企集团有限公司招聘"), "国企")

    def test_csv_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rows.csv"
            monitor.write_csv(path, ["notice_id", "title"], [{"notice_id": "x", "title": "公告"}])
            rows = monitor.load_csv(path, "notice_id")
            self.assertEqual(rows["x"]["title"], "公告")


if __name__ == "__main__":
    unittest.main()
