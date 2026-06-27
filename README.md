## Student Assessment
# 1. Core Philosophy
The project is built on the realistic premise that a student's developmental journey is non-linear and dynamic. Throughout their university lifecycle, students continuously experience significant fluctuations in multiple dimensions:

Motivation: Shifts and variations in academic drive and engagement over different high-pressure periods.

Direction: Continuous evolution of interests and career goals as they gain real-world exposure.

Alignment: Changes in how they perceive their own compatibility and suitability with their chosen major.

Well-being: Complex transitions in mental health status, emotional integration, and stress levels before major milestones.

Consequently, this project rejects static, single-point-in-time assessments in favor of a dynamic tracking model that monitors how these key indicators shift over time.

# 2. System Objectives
The system aims to serve as a comprehensive, data-driven companion designed to achieve the following:

Continuous Tracking: Monitor the synchronized progress of both academic development and psychological well-being across distinct journey stages.

Early Warning System: Instantly detect early red flags of disorientation, declining internal motivation, or risk of tracking off-course based on configured baseline metrics.

Personalized Intervention: Provide foundational, actionable insights that enable academic institutions and mentors to deliver timely, tailored support and optimized career guidance to students exactly when they need it most.
Hệ thống khảo sát năng lực sinh viên: sinh viên làm khảo sát ở frontend → backend chấm điểm (LLM), sinh báo cáo PDF (radar + bảng năng lực) và gửi qua email.

## Service

| Component | Folder | Port  | Role |
|---|---|---|---|
| Backend | `backend/` (FastAPI) | `8000` | generate report, send mail |
| Frontend | `frontend/` (HTTP server) | `8080` | UI form survey, dashboard, admin |

## Requirements

- Python **3.13** ( `.python-version`)
- [uv](https://docs.astral.sh/uv/) manage environment 
## 1. Cài đặt

```bash
cd student-assessment
uv sync          
```

## 2. Setup


```
cd backend
cp env.example .env 
```

## 3. Run backend service (port 8000)


```bash
cd student-assessment/backend
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

- API docs: <http://127.0.0.1:8000/docs>

## 4. Run frontend  service (port 8080)

Open new  terminal:

```bash
cd student-assessment/frontend
uv run python serve_frontend.py
```

Access:

- Form survey: <http://127.0.0.1:8080/>
- Dashboard : <http://127.0.0.1:8080/dashboard>
- Admin: <http://127.0.0.1:8080/admin>

