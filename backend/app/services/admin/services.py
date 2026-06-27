import os
import json
import logging

from fastapi import HTTPException

import pipeline

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

ADMIN_HTML_PATH = os.getenv("ADMIN_HTML_PATH", "admin.html")
RADAR_JSON_PATH = os.getenv("RADAR_JSON_PATH", "radar.json")


class AdminService:
    def __init__(self):
        self.map_path = pipeline.MAP_JSON_PATH
        self.admin_html_path = ADMIN_HTML_PATH
        self.radar_path = RADAR_JSON_PATH

    def _load_map(self) -> dict:
        with open(self.map_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_map(self, data: dict) -> None:
        with open(self.map_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_radar(self) -> dict:
        """radar.json hiện tại; thiếu file -> khởi tạo từ RADAR_STD mặc định."""
        if os.path.exists(self.radar_path):
            with open(self.radar_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {k: dict(v) for k, v in pipeline.RADAR_STD.items()}

    def _write_radar(self, radar: dict) -> None:
        """Ghi radar.json theo đúng format hiện tại: mỗi stage gọn trên 1 dòng."""
        lines = [
            f"    {json.dumps(k, ensure_ascii=False)}: {json.dumps(v, ensure_ascii=False)}"
            for k, v in radar.items()
        ]
        content = "{\n" + ",\n".join(lines) + "\n}\n"
        with open(self.radar_path, "w", encoding="utf-8") as f:
            f.write(content)

    def _sync_radar(self, stage_objs_by_num: dict, stage_nums: list) -> None:
        """Ghi ngưỡng chuẩn (đã merge default + admin) của các stage vừa lưu vào radar.json."""
        radar = self._load_radar()
        for n in stage_nums:
            radar[f"stage_{n}"] = pipeline.stage_thresholds(stage_objs_by_num[n], n)
        self._write_radar(radar)

    def dimensions(self) -> list[dict]:
        """5 năng lực theo đúng thứ tự dùng trong pipeline."""
        out = []
        for suf in pipeline.ORDER:
            key, label = pipeline.SUFFIX[suf]
            out.append({"key": key, "label": label, "vi": pipeline.DIM_COPY[suf]["vi"]})
        return out

    def admin_html(self) -> str:
        if not os.path.exists(self.admin_html_path):
            raise HTTPException(404, "Không tìm thấy admin.html")
        with open(self.admin_html_path, "r", encoding="utf-8") as f:
            return f.read()

    def get_goals(self) -> dict:
        """Trả về ngưỡng chuẩn hiện tại của 5 stage (đã merge default + goal đã lưu)."""
        data_map = self._load_map()
        stages = []
        for stage_obj in sorted(data_map["stages"], key=lambda s: s["stage"]):
            n = int(stage_obj["stage"])
            stages.append({
                "stage": n,
                "stage_name": stage_obj.get("stage_name", f"Stage {n}"),
                "thresholds": pipeline.stage_thresholds(stage_obj, n),
                "goal": stage_obj.get("goal", "") if isinstance(stage_obj.get("goal"), str) else "",
            })
        return {"dimensions": self.dimensions(), "stages": stages}

    def save_goals(self, payload) -> dict:
        """Lưu ngưỡng chuẩn vào map.json, rồi đồng bộ sang radar.json.

        `payload` là `GoalsUpdate` (controller truyền vào): có `.stages`, mỗi
        phần tử có `.stage`, `.thresholds`, `.goal`.
        """
        valid_keys = {d["key"] for d in self.dimensions()}
        data_map = self._load_map()
        by_num = {int(s["stage"]): s for s in data_map["stages"]}

        updated = []
        for sg in payload.stages:
            stage_obj = by_num.get(sg.stage)
            if stage_obj is None:
                raise HTTPException(400, f"Stage không tồn tại: {sg.stage}")

            thr = {}
            for key, raw in sg.thresholds.items():
                if key not in valid_keys:
                    continue
                val = (raw or "").strip()
                if not val:
                    continue
                try:
                    op, num = pipeline.parse_thr(val)  # validate định dạng "{op}{số}"
                except Exception:
                    raise HTTPException(
                        400, f"Ngưỡng không hợp lệ cho stage {sg.stage}/{key}: '{raw}'"
                    )
                thr[key] = f"{op}{num}"
            stage_obj["thresholds"] = thr
            # Chỉ cập nhật goal khi client thực sự gửi (None = giữ nguyên).
            if sg.goal is not None:
                stage_obj["goal"] = sg.goal.strip()
            updated.append(sg.stage)

        self._save_map(data_map)
        self._sync_radar(by_num, updated)
        return {"saved": True, "updated_stages": sorted(updated)}
