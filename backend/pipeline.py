
from __future__ import annotations

import json
import os
import re
import tempfile
import uuid
from dataclasses import dataclass, field
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  
from openai import OpenAI  
import pdf_renderer  
from dotenv import load_dotenv

load_dotenv(override=True)


OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

DEFAULT_CSV_URL = os.getenv(
    "DEFAULT_CSV_URL",
    "https://docs.google.com/spreadsheets/d/1gLsAcNgKpZrErud2zqv1JGOrmuDDzNzPjJMcYJ4dtwY/export?format=csv&gid=0",
)
MAP_JSON_PATH = os.getenv("MAP_JSON_PATH", "map.json")

REPORTS_DIR = os.getenv("REPORTS_DIR", "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)


def _client() -> OpenAI:
    if not OPENROUTER_API_KEY:
        raise RuntimeError(
            " Lost OPENROUTER_API_KEY."
        )
    return OpenAI(base_url=OPENROUTER_BASE_URL, api_key=OPENROUTER_API_KEY)


with open('radar.json', 'r', encoding='utf-8') as file:
    RADAR_STD = json.load(file)



SUFFIX = {
    "WB": ("wellbeing_integration", "Wellbeing & Integration"),
    "AC": ("academic_progress", "Academic Progress"),
    "MO": ("motivation_engagement", "Motivation & Efficacy"),
    "CR": ("career_direction", "Career & Direction"),
    "EX": ("extracurricular", "Extracurricular Engagement"),
}
ORDER = ["WB", "AC", "MO", "CR", "EX"]

DIM_COPY = {
    "WB": {"vi": "Sức khỏe tinh thần & hòa nhập",
           "strong": "bạn quản lý cảm xúc và hòa nhập với môi trường học khá tốt",
           "weak": "bạn nên chú ý cân bằng cảm xúc và mở rộng kết nối ở trường",
           "actions": ["Lên lịch ngủ - học - nghỉ cố định trong tuần",
                       "Tham gia một hoạt động kết nối bạn bè (nhóm học, CLB)",
                       "Dành 10 phút/ngày ghi nhật ký cảm xúc"]},
    "AC": {"vi": "Tiến bộ học tập",
           "strong": "bạn duy trì kết quả học tập ổn định và có phương pháp học hiệu quả",
           "weak": "bạn cần củng cố phương pháp học và bám sát tiến độ môn học",
           "actions": ["Lập kế hoạch học theo tuần cho từng môn",
                       "Ôn tập chủ động 30 phút/ngày thay vì dồn vào kỳ thi",
                       "Tìm 1 nhóm học hoặc mentor cho môn khó nhất"]},
    "MO": {"vi": "Động lực & năng lực bản thân",
           "strong": "bạn có động lực rõ ràng và tin vào khả năng của mình",
           "weak": "bạn nên đặt mục tiêu nhỏ, đo được để giữ động lực bền",
           "actions": ["Đặt 1 mục tiêu SMART cho tháng và chia nhỏ theo tuần",
                       "Ghi lại 3 việc làm được mỗi ngày để củng cố tự tin",
                       "Tự thưởng khi hoàn thành cột mốc"]},
    "CR": {"vi": "Định hướng nghề nghiệp",
           "strong": "bạn đã có hình dung khá rõ về hướng đi nghề nghiệp",
           "weak": "bạn cần làm rõ định hướng và thử nghiệm thực tế nhiều hơn",
           "actions": ["Tham gia 1 workshop/talkshow định hướng nghề nghiệp",
                       "Phỏng vấn 1 người đi trước trong ngành quan tâm",
                       "Bắt đầu hồ sơ năng lực (CV/portfolio) phiên bản đầu",
                       "Tìm hiểu 1 vị trí thực tập phù hợp ngành học"]},
    "EX": {"vi": "Tham gia ngoại khóa",
           "strong": "bạn tham gia hoạt động ngoại khóa tích cực và chủ động",
           "weak": "bạn nên tham gia hoạt động ngoại khóa đều đặn hơn",
           "actions": ["Đăng ký 1 CLB/hoạt động phù hợp sở thích",
                       "Tham gia tối thiểu 1 sự kiện/2 tuần",
                       "Nhận 1 vai trò nhỏ (hỗ trợ, tổ chức) trong hoạt động",
                       "Kết nối với 2 bạn mới qua hoạt động"]},
}


def parse_thr(t: str):
    m = re.match(r"\s*(>=|>|<=|<|==)?\s*([\d.]+)", t)
    return (m.group(1) or ">="), float(m.group(2))


def passes(score: float, t: str) -> bool:
    op, v = parse_thr(t)
    return {">=": score >= v, ">": score > v, "<=": score <= v, "<": score < v, "==": score == v}[op]


def stage_thresholds(stage_obj: dict, stage_num: int) -> dict:
    
    base = dict(RADAR_STD[f"stage_{stage_num}"])
    # `thresholds` = ngưỡng số do admin chỉnh (tương thích ngược với key cũ "goal").
    saved = (stage_obj or {}).get("thresholds")
    if not isinstance(saved, dict):
        legacy = (stage_obj or {}).get("goal")
        saved = legacy if isinstance(legacy, dict) else {}
    for k, v in saved.items():
        if k in base and isinstance(v, str) and v.strip():
            base[k] = v.strip()
    return base


def _parse_llm_json(text: str):
    cleaned = text.replace("```json", "").replace("```", "").strip()
    return json.loads(cleaned)



@dataclass
class ReportResult:
    report_id: str
    pdf_path: str
    profile: dict
    scores: list = field(default_factory=list)
    analysis: str = ""
    career: str = ""


def generate_report(
  
    report_title: str = "Student Assessment Report",
    subtitle: str = "Đối chiếu năng lực với ngưỡng chuẩn theo giai đoạn",
    output_dir: str | None = None,
) -> ReportResult:
    # Bỏ qua giá trị rỗng hoặc placeholder "string" mà Swagger UI tự điền
    # -> tự fallback về mặc định trong .env.
    def _clean(v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return None if v == "" or v.lower() == "string" else v

    csv_url = DEFAULT_CSV_URL
    map_json_path =  MAP_JSON_PATH
    output_dir = output_dir or REPORTS_DIR
    os.makedirs(output_dir, exist_ok=True)

    report_id = uuid.uuid4().hex[:12]
    client = _client()

    # --- 1) Đọc dữ liệu, lấy 5 dòng cuối (5 nhóm năng lực của SV mới nhất) ---
    df = pd.read_csv(csv_url)
    df2 = df.reset_index(drop=True).tail(5)

    year_level = df2["Year Level"].iloc[0]
    program_duration = df2["Program Duration"].iloc[0]
    semester = df2["Semester"].iloc[0]

    with open(map_json_path, "r", encoding="utf-8") as f:
        data_map = json.load(f)

    stage_num = int(df2["Stage"].iloc[0])
    stage_obj = next(s for s in data_map["stages"] if s["stage"] == stage_num)
    stage_name = stage_obj["stage_name"]
    stage_short = stage_name.split(" (")[0]

    std = stage_thresholds(stage_obj, stage_num)
    cat_by_suf = {c["category_id"].split("_")[-1]: c for c in stage_obj["categories"]}

    scores = []
    full_questions = []
    for suf in ORDER:
        cat = cat_by_suf[suf]
        key, label = SUFFIX[suf]

        sel = df2[df2["Category ID"] == cat["category_id"]].iloc[0]
        answers = [sel[f"Q{i}"] for i in range(1, 6)]
        for i in range(5):
            question = cat["questions"][i]["question_text"]
            options = cat["questions"][i].get("options", "")
            if len(options) != 0:
                for op in options:
                    if op["value"] == answers[i]:
                        ans = op["text"]
                        full_questions.append(
                            {"label": label, "value": {"question": question, "answer": ans}}
                        )

        thr = std[key]
        scores.append({
            "suf": suf, "label": label, "vi": DIM_COPY[suf]["vi"],
            "threshold": thr, "std_val": parse_thr(thr)[1],
        })


    prompt_score = f"""
You are an expert student assessment evaluator.

Your task is to evaluate a student based on the provided information and return scores (0-10) for 5 dimensions:

1. Wellbeing & Integration
2. Academic Progress
3. Motivation & Efficacy
4. Career & Direction
5. Extracurricular Engagement

## Input
- Year Level: {year_level}
- Program Duration: {program_duration}
- Semester: {semester}
- Student Responses (map_question_answer):
{full_questions}
- Radar: {std}

## Evaluation Rules
- Evaluate each dimension strictly based on evidence in student responses.
- Map scoring using the provided radar standard when applicable.
- If information is missing or unclear, score conservatively.
- Avoid bias, assumptions, or hallucination.
- All 5 dimensions must sum to 100 points total.
- Each dimension is scored from 0 to 100 (NOT 0-10).

## Output Format (STRICT JSON)
Return ONLY valid JSON:
  "Wellbeing & Integration": {{ "score": 0 }},
  "Academic Progress": {{ "score": 0 }},
  "Motivation & Efficacy": {{ "score": 0 }},
  "Career & Direction": {{ "score": 0 }},
  "Extracurricular Engagement": {{ "score": 0 }}

## Scoring Constraint
- Sum of all 5 dimension scores MUST equal 100.
- total_score = sum of all dimensions.
"""
    resp = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt_score}],
        temperature=0.9, top_p=0.95,
    )
    result_json = _parse_llm_json(resp.choices[0].message.content)

    for s in scores:
        s1 = result_json[s["label"]]
        s["score"] = s1["score"] / 10
        s["passed"] = passes(s["score"], s["threshold"])
        # % đạt được so với ngưỡng chuẩn của giai đoạn (thay cho Đạt/Chưa đạt).
        # Ngưỡng tối đa là 100% — vượt chuẩn vẫn tính tròn 100%, không hiển thị 175%.
        std_val = s.get("std_val") or 0
        s["pct"] = min(100, round(s["score"] / std_val * 100)) if std_val else 0

    # --- 5) Vẽ radar ---
    radar_path = os.path.join(tempfile.gettempdir(), f"radar_{report_id}.png")
    labels = [s["label"].replace(" & ", "\n& ") for s in scores]
    stu = [s["score"] for s in scores]
    ref = [s["std_val"] for s in scores]
    ang = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    ang += ang[:1]

    fig, ax = plt.subplots(figsize=(5.2, 5.2), subplot_kw=dict(polar=True))
    ax.set_facecolor("white")
    ax.plot(ang, ref + ref[:1], color="#1B365D", lw=1.6, ls="--", label="Chuẩn")
    ax.plot(ang, stu + stu[:1], color="#2A9D8F", lw=2.2, label="Sinh viên")
    ax.fill(ang, stu + stu[:1], color="#2A9D8F", alpha=0.22)
    ax.set_xticks(ang[:-1]); ax.set_xticklabels(labels, fontsize=8.5)
    ax.set_ylim(0, 4); ax.set_yticks([1, 2, 3, 4])
    ax.tick_params(axis="y", labelsize=7, colors="#6E7681")
    ax.legend(loc="upper right", bbox_to_anchor=(1.15, 1.12), fontsize=8, frameon=False)
    plt.tight_layout()
    fig.savefig(radar_path, dpi=170)
    plt.close(fig)

    prompt_analysis = f"""
You are an expert student assessment evaluator.

Your task is to evaluate a student based ONLY on the information provided.

---

# Input

* Year Level: {year_level}

* Program Duration: {program_duration}

* Semester: {semester}

* Student Responses (map_question_answer):
  {full_questions}

---

# Evaluation Principles

1. Analyze all student responses holistically across the five evaluation dimensions.
2. Base every conclusion strictly on the provided evidence.
3. Do NOT infer, speculate, or introduce assumptions that are not supported by the student's responses.
4. If there is insufficient evidence for any conclusion, explicitly state:
   "Không có đủ bằng chứng để kết luận ..."
5. Write directly to the student using the pronoun "Bạn".
6. Maintain a supportive, constructive, and professional tone, similar to a friendly mentor.

---

# Evaluation Dimensions

Consider the student's responses across these five dimensions:

1. Wellbeing & Integration
2. Academic Progress
3. Motivation & Efficacy
4. Career & Direction
5. Extracurricular Engagement

Do NOT score or rate these dimensions.

Instead, synthesize the available evidence into:

* An overall overview
* Key strengths
* Key areas for improvement

---

# Output Format

Return ONLY valid JSON.


"overview": "...",
"strengths": [
"...",
"..."
],
"weaknesses": [
"...",
"..."
]


Do not include markdown.
Do not include explanations outside the JSON.
Do not include additional fields.

---

# Content Requirements

## overview

Write approximately 100 words.

Summarize:

* The student's overall learning situation and engagement.
* The major patterns observed across the responses.
* How the available evidence reflects the student's current progress.
* Mention any important areas where there is insufficient evidence.

Only include conclusions supported by the provided responses.

---

## strengths

Provide exactly 2 items.

Each item should be approximately 100 words and:

* Describe one specific strength demonstrated by the student.
* Support the conclusion with relevant evidence from the student's responses.
* Explain what the evidence suggests about the student's learning, behavior, or development.
* Write naturally without following a fixed sentence template.
* Avoid generic praise that is not supported by evidence.
* If evidence is insufficient, explicitly state:
  "Không có đủ bằng chứng để kết luận ..."

---

## weaknesses

Provide exactly 2 items.

Each item should be approximately 100 words and:

* Describe one specific area for improvement.
* Support the conclusion with relevant evidence from the student's responses.
* Explain why this represents a challenge or opportunity for growth.
* Provide a constructive and realistic suggestion.
* Write naturally without following a fixed sentence template.
* Avoid unsupported criticism.
* If evidence is insufficient, explicitly state:
  "Không có đủ bằng chứng để kết luận ..."

---

# Writing Rules

* Use ONLY the provided input.
* Every conclusion must be traceable to the student's responses.
* Do NOT hallucinate or add external knowledge.
* Do NOT compare the student with other students.
* Do NOT assign scores, ratings, or probabilities.
* Do NOT mention the evaluation dimensions by name unless they naturally fit the summary.
* Do NOT use repetitive phrases such as:

  * "Dựa trên câu trả lời của bạn..."
  * "Trong phản hồi bạn đã..."
  * "Như đã thể hiện trong câu trả lời..."
* Instead, integrate supporting evidence naturally into the explanation.
* Use clear, supportive, and encouraging language suitable for personalized student feedback.
* The response must be entirely in Vietnamese except for the JSON keys:

  * overview
  * strengths
  * weaknesses
* Return ONLY valid JSON.

"""
    resp = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt_analysis}],
    )
    data = _parse_llm_json(resp.choices[0].message.content)

    analysis = (
        f"1. Tổng quan\n{data['overview']}\n\n"
        f"2. Điểm mạnh\n{data['strengths'][0]}\n\n"
        f"3. Điểm cần cải thiện\n{data['weaknesses'][0]}"
    )

    # --- 7) LLM #3: plan 4 weeks ---
    prompt_career = f"""
You are an expert student assessment evaluator and career advisor.

Your task is to evaluate the student based on the provided information and provide personalized feedback along with a practical 4-week career development plan.

## Evaluation Dimensions

1. Wellbeing & Integration
2. Academic Progress
3. Motivation & Efficacy
4. Career & Direction
5. Extracurricular Engagement

## Input

- Year Level: {year_level}
- Program Duration: {program_duration}
- Semester: {semester}
- Analysis student: {data}


## Instructions

* Identify the student's key strengths and areas for improvement based ONLY on the provided evidence.
* Do NOT make unsupported assumptions or introduce information that is not present.
* If there is insufficient evidence, explicitly state:
  "Không có đủ bằng chứng để cá nhân hóa nội dung này."
* Based on the student's current situation, generate a personalized 4-week career development plan.
* The plan must be tailored to the student's interests, motivation, academic progress, career direction, current challenges, and available evidence whenever possible.
* If personalization is limited due to insufficient evidence, clearly mention that and generate a practical general career development plan instead of making assumptions.

### Planning Requirements

* Design the plan so that each week builds naturally on the previous week.
* Every activity should be realistic, actionable, and achievable within one week.
* Avoid vague advice such as "study harder" or "improve skills". Instead, describe exactly what the student should do.
* Include concrete deliverables and measurable outcomes whenever possible.
* Encourage reflection and continuous improvement throughout the four weeks.
* Recommendations should be specific enough that the student can immediately start following them without additional clarification.

### Detail Requirements

For EACH week:

* Goal:

  * Write 2-3 sentences explaining why this goal is important at this stage.

* Key Actions:

  * Include 4-6 activities.
  * Each activity should contain 2-4 sentences describing:

    * what to do,
    * why it is useful,
    * and how to complete it.

* Expected Output:

  * Include at least 3 concrete deliverables.
  * Describe what the student should have completed by the end of the week.

* Success Metrics (KPI):

  * Include 3-5 measurable indicators.
  * Use quantitative metrics whenever possible (hours, number of applications, completed tasks, portfolio pieces, reflections, etc.).

* Reflection & Monitoring:

  * Include 2-3 reflection questions for the student.
  * Suggest how the student should review progress before moving to the next week.

### Final Outcome

After Week 4, provide a "Final Outcome" section (approximately 150-200 words) summarizing:

* What the student is expected to achieve after completing the plan.
* Which habits or skills should have improved.
* Suggested next steps beyond the four weeks.

### Writing Style

* Return all content in Vietnamese, except the labels:
  Week 1, Week 2, Week 3, Week 4, Goal, Key Actions, Expected Output, Success Metrics, Reflection & Monitoring, Final Outcome.
* Use a friendly, encouraging tone, like giving advice to a friend.
* Keep the language natural and conversational.
* Do not use markdown headings (#, ##, ###).
* Do not use "*" for bullet points. Use "-" instead.
* The entire plan should contain approximately 1,500-2,000 words.

## Output 
# 4-Week Career Development Plan 
## Week 1 Goal: 
[Write the main goal, e.g., Improve time management and establish healthy daily routines]
 Key Actions 
- Activity 1: [e.g., Track daily activities in 30-60 min intervals] 
- Activity 2: [e.g., Identify productivity patterns and time-wasting habits] 
- Activity 3: [e.g., Set fixed study/work schedule and sleep routine]

 Expected Output [e.g., Weekly time log completed] [e.g., 1 reflection report on habits] [e.g., Defined daily schedule] Success Metrics (KPI) [e.g., >= 80% adherence to schedule] [e.g., 7-8 hours sleep daily] 

## Week 2 Goal: [Write the main goal, e.g., Improve time management and establish healthy daily routines] 
Key Actions 
- Activity 1: [e.g., Track daily activities in 30-60 min intervals] 
- Activity 2: [e.g., Identify productivity patterns and time-wasting habits] 
- Activity 3: [e.g., Set fixed study/work schedule and sleep routine]

 Expected Output [e.g., Weekly time log completed] [e.g., 1 reflection report on habits] [e.g., Defined daily schedule] Success Metrics (KPI) [e.g., >= 80% adherence to schedule] [e.g., 7-8 hours sleep daily] 

## Week 3 Goal: [Write the main goal, e.g., Improve time management and establish healthy daily routines]
 Key Actions 
- Activity 1: [e.g., Track daily activities in 30-60 min intervals] 
- Activity 2: [e.g., Identify productivity patterns and time-wasting habits] 
- Activity 3: [e.g., Set fixed study/work schedule and sleep routine]
 Expected Output [e.g., Weekly time log completed] [e.g., 1 reflection report on habits] [e.g., Defined daily schedule] Success Metrics (KPI) [e.g., >= 80% adherence to schedule] [e.g., 7-8 hours sleep daily]

 ## Week 4 Goal: [Write the main goal, e.g., Improve time management and establish healthy daily routines]

 Key Actions - Activity 1: [e.g., Track daily activities in 30-60 min intervals] 
- Activity 2: [e.g., Identify productivity patterns and time-wasting habits] 
- Activity 3: [e.g., Set fixed study/work schedule and sleep routine]

 Expected Output [e.g., Weekly time log completed] [e.g., 1 reflection report on habits] [e.g., Defined daily schedule] Success Metrics (KPI) [e.g., >= 80% adherence to schedule] [e.g., 7-8 hours sleep daily]

The career development plan should be practical, motivating, and aligned with the student's current situation.

If there is insufficient information to personalize the plan, explicitly mention that and provide a general 4-week career development plan instead of making unsupported assumptions.
"""
    resp = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt_career}],
    )
    career = resp.choices[0].message.content

    profile = {
        "name": str(df2["Full Name"].iloc[0]),
        "email": str(df2["Email"].iloc[0]),
        "year_level": str(year_level),
        "program_duration": str(program_duration),
        "semester": str(semester),
        "stage_name": stage_short,
    }

    pdf_path = os.path.join(output_dir, f"student_report_{report_id}.pdf")
    pdf_renderer.build_report(
        pdf_path,
        profile=profile,
        radar_image=radar_path,
        analysis=analysis,
        career_plan=career,
        scores=scores,
        report_title=report_title,
        subtitle=subtitle,
    )


    try:
        os.remove(radar_path)
    except OSError:
        pass

    return ReportResult(
        report_id=report_id,
        pdf_path=pdf_path,
        profile=profile,
        scores=scores,
        analysis=analysis,
        career=career,
    )



