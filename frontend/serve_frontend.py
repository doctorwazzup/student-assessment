
import csv
import http.server
import io
import json
import os
import time
import urllib.error
import urllib.request
from collections import Counter
from functools import partial

FRONTEND_DIR = os.path.dirname(os.path.abspath(__file__))
ADMIN_HTML = os.path.join(FRONTEND_DIR, "admin.html")
DASHBOARD_HTML = os.path.join(FRONTEND_DIR, "dashboard.html")
PORT = int(os.getenv("FRONTEND_PORT", "8080"))

CSV_URL = os.getenv(
    "CSV_URL",
    "https://docs.google.com/spreadsheets/d/1gLsAcNgKpZrErud2zqv1JGOrmuDDzNzPjJMcYJ4dtwY/export?format=csv&gid=0",
)

BACKEND = os.getenv("API_BACKEND", "http://127.0.0.1:8000")


def _backend_post(path: str, payload: dict, timeout: int = 180) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        BACKEND + path, data=data, method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"backend {path} -> {e.code}: {detail[:300]}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"backend {path} không phản hồi: {e.reason}")

# Cache nhẹ để khỏi tải CSV mỗi lần refresh.
_CACHE = {"ts": 0.0, "data": None}
_CACHE_TTL = 30  # giây


def _fetch_csv_text() -> str:
    req = urllib.request.Request(CSV_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", errors="replace")


def _iso(ddmmyyyy: str) -> str:
    """'08/06/2026' -> '2026-06-08' (để sort/hiển thị); fallback giữ nguyên."""
    try:
        dd, mm, yy = ddmmyyyy.split("/")
        return f"{int(yy):04d}-{int(mm):02d}-{int(dd):02d}"
    except Exception:
        return ddmmyyyy


def compute_stats() -> dict:
  
    text = _fetch_csv_text()
    reader = csv.DictReader(io.StringIO(text))
    subs = {}          # key (Timestamp) -> thông tin 1 lượt nộp
    rows = 0
    for row in reader:
        rows += 1
        ts = (row.get("Timestamp") or "").strip()
        key = ts or f"__row{rows}"   # thiếu timestamp -> coi như lượt riêng
        if key not in subs:
            subs[key] = {
                "stage": (row.get("Stage") or "").strip(),
                "year": (row.get("Year Level") or "").strip(),
                "semester": (row.get("Semester") or "").strip(),
                "date": ts[:10],
            }

    by_stage, by_year, by_sem, by_date = Counter(), Counter(), Counter(), Counter()
    for v in subs.values():
        by_stage[v["stage"]] += 1
        by_year[v["year"] or "—"] += 1
        by_sem[v["semester"] or "—"] += 1
        if v["date"]:
            by_date[v["date"]] += 1

    def _stage_key(k):
        try:
            return int(k)
        except Exception:
            return 999

    def _date_key(d):
        try:
            dd, mm, yy = d.split("/")
            return (int(yy), int(mm), int(dd))
        except Exception:
            return (0, 0, 0)

    stages = sorted([s for s in by_stage if s != ""], key=_stage_key)
    dates = sorted([d for d in by_date if d], key=_date_key)

    return {
        "total": len(subs),
        "responses": rows,
        "stages_count": len(stages),
        "years_count": len([y for y in by_year if y != "—"]),
        "by_stage": [{"label": f"Stage {s}", "count": by_stage[s]} for s in stages],
        "by_year": [{"label": y, "count": by_year[y]} for y in sorted(by_year)],
        "by_semester": [{"label": s, "count": by_sem[s]} for s in sorted(by_sem)],
        "by_date": [{"date": _iso(d), "count": by_date[d]} for d in dates],
    }


def get_stats_cached() -> dict:
    now = time.time()
    if _CACHE["data"] is None or now - _CACHE["ts"] > _CACHE_TTL:
        _CACHE["data"] = compute_stats()
        _CACHE["ts"] = now
    return _CACHE["data"]


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        if path == "/admin":
            return self._send_file(ADMIN_HTML, "text/html; charset=utf-8")
        if path == "/dashboard":
            return self._send_file(DASHBOARD_HTML, "text/html; charset=utf-8")
        if path == "/dashboard/stats":
            return self._send_stats()
        return super().do_GET()

    def do_POST(self):
        path = self.path.split("?", 1)[0].rstrip("/")
        if path == "/api/send-report":
            return self._send_report()
        self.send_error(404, "Not found")

    def _send_report(self):
        """Sinh report từ dữ liệu mới nhất trên sheet rồi gửi email cho sinh viên."""
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            req = json.loads(raw or b"{}")
        except Exception:
            req = {}
        email = (req.get("email") or "").strip()
        if not email:
            return self._send_bytes(
                400, json.dumps({"error": "Thiếu email sinh viên."}).encode("utf-8"),
                "application/json; charset=utf-8")
        try:
            gen = _backend_post("/reports/export-report",
                                {"report_title": "Student Assessment Report"})
            report_id = gen.get("report_id")
            if not report_id:
                raise RuntimeError("Không nhận được report_id từ backend.")
            sent = _backend_post("/mail/send-mail",
                                 {"report_id": report_id, "to_email": email})
            body = json.dumps({"ok": True, "report_id": report_id, "sent": sent})
            self._send_bytes(200, body.encode("utf-8"), "application/json; charset=utf-8")
        except Exception as e:
            body = json.dumps({"error": str(e)})
            self._send_bytes(502, body.encode("utf-8"), "application/json; charset=utf-8")

    def _send_stats(self):
        try:
            payload = json.dumps(get_stats_cached()).encode("utf-8")
            self._send_bytes(200, payload, "application/json; charset=utf-8")
        except Exception as e:
            body = json.dumps({"error": f"Không tải được dữ liệu: {e}"}).encode("utf-8")
            self._send_bytes(502, body, "application/json; charset=utf-8")

    def _send_file(self, filepath, content_type):
        if not os.path.exists(filepath):
            self.send_error(404, "Not found")
            return
        with open(filepath, "rb") as f:
            self._send_bytes(200, f.read(), content_type)

    def _send_bytes(self, status, data, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    handler = partial(Handler, directory=FRONTEND_DIR)
    print(f"Frontend  : http://localhost:{PORT}/")
    print(f"Admin     : http://localhost:{PORT}/admin")
    print(f"Dashboard : http://localhost:{PORT}/dashboard")
    http.server.ThreadingHTTPServer(("0.0.0.0", PORT), handler).serve_forever()
