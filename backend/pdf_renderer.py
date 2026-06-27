from __future__ import annotations
import os
import re
import urllib.request
from datetime import datetime
from fpdf import FPDF


EMOJI_DIR = os.path.join("/tmp", "twemoji_cache")
os.makedirs(EMOJI_DIR, exist_ok=True)

_NOTO_URL = (
    "https://raw.githubusercontent.com/google/fonts/main/ofl/notosans/"
    "NotoSans%5Bwdth%2Cwght%5D.ttf"
)
_NOTO_BOLD_URL = (
    "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/"
    "NotoSans/NotoSans-Bold.ttf"
)

_FALLBACK_TTFS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/root/agent-src/.venv/lib/python3.10/site-packages/cv2/qt/fonts/DejaVuSans.ttf",
]
_FALLBACK_TTFS_BOLD = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/root/agent-src/.venv/lib/python3.10/site-packages/cv2/qt/fonts/DejaVuSans-Bold.ttf",
]


def _resolve_font(cache_path: str, url: str, fallbacks: list[str]) -> str | None:
    """Trả về đường dẫn 1 file TTF unicode dùng được, hoặc None nếu không có."""
    if os.path.exists(cache_path):
        return cache_path
    try:
        urllib.request.urlretrieve(url, cache_path)
        return cache_path
    except Exception:
        pass
    for fb in fallbacks:
        if os.path.exists(fb):
            return fb
    return None



def is_emoji(ch: str) -> bool:
    code = ord(ch)
    return (
        code >= 0x1F000
        or 0x2600 <= code <= 0x27BF
        or code in (0x2705, 0x2B50, 0x2728, 0x231A, 0x231B)
    )


def get_emoji_png(emoji_str: str) -> str | None:
    # Twemoji bỏ qua variation selector U+FE0F trong tên file
    codepoints = [f"{ord(c):x}" for c in emoji_str if c != "️"]
    codepoint = "-".join(codepoints)
    path = os.path.join(EMOJI_DIR, f"{codepoint}.png")
    if not os.path.exists(path):
        url = (
            "https://raw.githubusercontent.com/jdecked/twemoji/main/"
            f"assets/72x72/{codepoint}.png"
        )
        try:
            urllib.request.urlretrieve(url, path)
        except Exception:
            return None
    return path


def tokenize(text: str):
    """Tách text thành token ('text', s) / ('emoji', s) — giữ nguyên cụm chữ."""
    tokens, buf = [], []
    i = 0
    while i < len(text):
        ch = text[i]
        if is_emoji(ch):
            if buf:
                tokens.append(("text", "".join(buf)))
                buf = []
            emoji_str = ch
            if i + 1 < len(text) and text[i + 1] == "️":
                emoji_str += "️"
                i += 1
            tokens.append(("emoji", emoji_str))
        elif ch == "️":
            pass  # VS-16 đứng lẻ -> bỏ
        else:
            buf.append(ch)
        i += 1
    if buf:
        tokens.append(("text", "".join(buf)))
    return tokens


# =========================================================================
#  DESIGN TOKENS  (đổi màu ở đây là cả report đổi theo)
# =========================================================================
PRIMARY     = (27, 54, 93)     # navy đậm  - tiêu đề, banner
PRIMARY_DK  = (16, 34, 61)
ACCENT      = (42, 157, 143)   # teal      - thanh nhấn, bullet, đường kẻ
ACCENT_SOFT = (224, 240, 238)
INK         = (40, 44, 52)     # chữ thân bài
MUTED       = (110, 118, 129)  # chữ phụ, caption
LIGHT_BG    = (244, 247, 250)  # nền card
CARD_BORDER = (223, 228, 234)
WHITE       = (255, 255, 255)

MARGIN = 18

HEADING_STYLES = {
    1: {"size": 16, "before": 6, "after": 4},
    2: {"size": 14, "before": 5, "after": 3},
    3: {"size": 12.5, "before": 4, "after": 2.5},
    4: {"size": 11.5, "before": 3, "after": 2},
    5: {"size": 11, "before": 2.5, "after": 2},
    6: {"size": 10.5, "before": 2, "after": 2},
}
BODY = {"size": 10.5, "line_height": 5.6, "emoji_size": 4.6}


# =========================================================================
#  PARSE HELPERS  (markdown rút gọn)
# =========================================================================
def parse_heading(line: str):
    m = re.match(r"^(#{1,6})\s+(.+)$", line)
    return (len(m.group(1)), m.group(2).strip()) if m else (0, line)


def parse_bullet(line: str):
    m = re.match(r"^(\s*)[-*+]\s+(.+)$", line)
    if m:
        return True, len(m.group(1)) // 2, m.group(2)
    return False, 0, line


def parse_numbered(line: str):
    m = re.match(r"^(\s*)(\d+)\.\s+(.+)$", line)
    return (True, m.group(2), m.group(3)) if m else (False, "", line)


def parse_roman(line: str):
    m = re.match(r"^\s*([IVXLCDM]+)\.\s+(.+)$", line)
    return (True, m.group(1), m.group(2)) if m else (False, "", line)


def parse_image(line: str):
    m = re.match(r"^\s*!\[(.*?)\]\((.+?)\)\s*$", line)
    return (True, m.group(2).strip()) if m else (False, "")


def strip_inline_bold(text: str) -> str:
    # bỏ ** ** vì fpdf write không hỗ trợ bold inline; giữ chữ
    return re.sub(r"\*\*(.+?)\*\*", r"\1", text)


# Nhãn trường trong kế hoạch nghề nghiệp -> in đậm cho dễ quét mắt.
_FIELD_RE = re.compile(
    r"^\s*(Goal|Key Actions|Expected Output|Success Metrics(?:\s*\([^)]*\))?"
    r"|Reflection & Monitoring|Final Outcome)\s*:?\s*(.*)$"
)


def parse_field_label(line: str):
    m = _FIELD_RE.match(line)
    return (True, m.group(1), m.group(2).strip()) if m else (False, "", line)


def _has_emoji(text: str) -> bool:
    return any(kind == "emoji" for kind, _ in tokenize(text))


# =========================================================================
#  PDF CLASS  (header chạy trang + footer số trang)
# =========================================================================
class ReportPDF(FPDF):
    def __init__(self, report_title="Student Assessment Report",
                 regular_font=None, bold_font=None):
        super().__init__()
        self.report_title = report_title
        self.set_auto_page_break(auto=True, margin=20)
        self.set_margins(MARGIN, MARGIN, MARGIN)
        self.add_font("Noto", fname=regular_font)
        self.add_font("NotoBold", fname=bold_font or regular_font)

    def header(self):
        if self.page_no() == 1:
            return  # trang bìa tự vẽ riêng
        self.set_y(8)
        self.set_font("NotoBold", size=8.5)
        self.set_text_color(*MUTED)
        self.cell(0, 5, self.report_title, align="L")
        self.set_draw_color(*CARD_BORDER)
        self.set_line_width(0.3)
        self.line(MARGIN, 15, self.w - MARGIN, 15)
        self.set_y(20)

    def footer(self):
        self.set_y(-14)
        self.set_draw_color(*CARD_BORDER)
        self.set_line_width(0.3)
        self.line(MARGIN, self.get_y(), self.w - MARGIN, self.get_y())
        self.ln(1.5)
        self.set_font("Noto", size=8)
        self.set_text_color(*MUTED)
        self.cell(0, 5, f"Generated {datetime.now():%d/%m/%Y}", align="L")
        self.cell(0, 5, f"Trang {self.page_no()}", align="R")


# =========================================================================
#  RUN WRITER (text + emoji, word-wrap)
# =========================================================================
def write_runs(pdf, text, font_name, font_size, line_height, emoji_size, color=INK):
    pdf.set_font(font_name, size=font_size)
    pdf.set_text_color(*color)
    for kind, content in tokenize(text):
        if kind == "emoji":
            png = get_emoji_png(content)
            if png is None:
                pdf.write(line_height, " ")
                continue
            x = pdf.get_x()
            if x + emoji_size > pdf.w - pdf.r_margin:
                pdf.ln(line_height)
                x = pdf.get_x()
            y = pdf.get_y()
            pdf.image(png, x=x, y=y + (line_height - emoji_size) / 2,
                      w=emoji_size, h=emoji_size)
            pdf.set_x(x + emoji_size + 1.4)
        else:
            pdf.write(line_height, content)


# =========================================================================
#  CÁC KHỐI TRÌNH BÀY (cover, profile, section)
# =========================================================================
def draw_cover(pdf, title, subtitle, meta_lines):
    """Banner đầu trang bìa: dải navy + sọc teal + tiêu đề."""
    band_h = 56
    pdf.set_fill_color(*PRIMARY)
    pdf.rect(0, 0, pdf.w, band_h, style="F")
    # sọc nhấn dưới banner
    pdf.set_fill_color(*ACCENT)
    pdf.rect(0, band_h, pdf.w, 2.2, style="F")

    pdf.set_xy(MARGIN, 18)
    pdf.set_font("NotoBold", size=24)
    pdf.set_text_color(*WHITE)
    pdf.multi_cell(pdf.w - 2 * MARGIN, 11, title, align="L")

    pdf.set_x(MARGIN)
    pdf.set_font("Noto", size=11)
    pdf.set_text_color(210, 222, 238)
    pdf.cell(0, 7, subtitle, align="L")

    pdf.set_y(band_h + 12)
    pdf.set_x(MARGIN)
    pdf.set_font("Noto", size=9.5)
    pdf.set_text_color(*MUTED)
    meta = "   ".join(meta_lines)
    avail = pdf.w - 2 * MARGIN
    while meta and pdf.get_string_width(meta) > avail:
        meta = meta[:-1]
    pdf.cell(0, 5, meta, align="L")
    pdf.ln(12)


def draw_profile_card(pdf, fields):
    """fields = list[(label, value)] -> card nền nhạt, 2 cột."""
    x0 = MARGIN
    y0 = pdf.get_y() + 2
    w = pdf.w - 2 * MARGIN
    rows = (len(fields) + 1) // 2
    row_h = 11
    pad = 6
    h = pad * 2 + rows * row_h

    pdf.set_fill_color(*LIGHT_BG)
    pdf.set_draw_color(*CARD_BORDER)
    pdf.set_line_width(0.4)
    pdf.rect(x0, y0, w, h, style="DF")
    # thanh nhấn trái
    pdf.set_fill_color(*ACCENT)
    pdf.rect(x0, y0, 2.4, h, style="F")

    col_w = (w - pad * 2) / 2
    for idx, (label, value) in enumerate(fields):
        col = idx % 2
        row = idx // 2
        cx = x0 + pad + col * col_w
        cy = y0 + pad + row * row_h
        pdf.set_xy(cx, cy)
        pdf.set_font("NotoBold", size=8)
        pdf.set_text_color(*MUTED)
        pdf.cell(col_w, 4, label.upper())
        pdf.set_xy(cx, cy + 4.2)
        pdf.set_font("Noto", size=10.5)
        pdf.set_text_color(*INK)
        val = str(value)
        avail = col_w - 2
        while val and pdf.get_string_width(val) > avail:
            val = val[:-1]
        if val != str(value):
            val = val.rstrip() + "…"
        pdf.cell(col_w, 5, val)
    pdf.set_y(y0 + h + 6)


def draw_score_table(pdf, scores):
    """scores = list[{label, score, threshold, passed}] -> bảng đối chiếu."""
    x0 = MARGIN
    w = pdf.w - 2 * MARGIN
    c_lab, c_sc, c_th, c_res = w * 0.46, w * 0.16, w * 0.16, w * 0.22
    rh = 8.5

    if pdf.get_y() + rh * (len(scores) + 1) > pdf.h - 22:
        pdf.add_page()

    # header
    y = pdf.get_y()
    pdf.set_fill_color(*PRIMARY)
    pdf.rect(x0, y, w, rh, style="F")
    pdf.set_font("NotoBold", size=9)
    pdf.set_text_color(*WHITE)
    pdf.set_xy(x0 + 3, y); pdf.cell(c_lab - 3, rh, "Nhóm năng lực")
    pdf.set_xy(x0 + c_lab, y); pdf.cell(c_sc, rh, "Điểm", align="C")
    pdf.set_xy(x0 + c_lab + c_sc, y); pdf.cell(c_th, rh, "Chuẩn", align="C")
    pdf.set_xy(x0 + c_lab + c_sc + c_th, y); pdf.cell(c_res, rh, "Kết quả", align="C")
    pdf.set_y(y + rh)

    pass_clr = (39, 132, 96)
    for i, s in enumerate(scores):
        y = pdf.get_y()
        if i % 2 == 0:
            pdf.set_fill_color(*LIGHT_BG); pdf.rect(x0, y, w, rh, style="F")
        pdf.set_font("Noto", size=9); pdf.set_text_color(*INK)
        pdf.set_xy(x0 + 3, y); pdf.cell(c_lab - 3, rh, s["label"])
        pdf.set_xy(x0 + c_lab, y)
        pdf.cell(c_sc, rh, f"{s['score']:.2f}", align="C")
        pdf.set_xy(x0 + c_lab + c_sc, y)
        pdf.set_text_color(*MUTED)
        pdf.cell(c_th, rh, s["threshold"], align="C")
        # thanh tiến độ: tô xanh theo đúng % đạt được so với ngưỡng chuẩn
        # (chưa đạt -> chỉ tô một phần ô, không fill đỏ kín ô).
        pct = max(0, min(100, s.get("pct", 0)))
        bw, bh = c_res - 8, 5.4
        bx = x0 + c_lab + c_sc + c_th + (c_res - bw) / 2
        by = y + (rh - bh) / 2
        # nền thanh (track) màu nhạt
        pdf.set_fill_color(*ACCENT_SOFT)
        pdf.rect(bx, by, bw, bh, style="F")
        # phần đã đạt tô xanh theo tỉ lệ
        if pct > 0:
            pdf.set_fill_color(*pass_clr)
            pdf.rect(bx, by, bw * pct / 100, bh, style="F")
        # viền ô + nhãn %
        pdf.set_draw_color(*CARD_BORDER); pdf.set_line_width(0.2)
        pdf.rect(bx, by, bw, bh)
        pdf.set_font("NotoBold", size=7.5); pdf.set_text_color(*PRIMARY)
        pdf.set_xy(bx, by - 0.2); pdf.cell(bw, bh, f"{pct}%", align="C")
        pdf.set_y(y + rh)

    pdf.set_draw_color(*CARD_BORDER); pdf.set_line_width(0.3)
    pdf.rect(x0, y - rh * (len(scores) - 1) - rh, w, rh * (len(scores) + 1))
    pdf.ln(6)


def draw_section_header(pdf, number, text):
    """Tiêu đề mục lớn I/II/III: số trong ô vuông teal + chữ navy + kẻ dưới."""
    if pdf.get_y() > pdf.h - 50:
        pdf.add_page()
    pdf.ln(4)
    y = pdf.get_y()
    box = 9
    pdf.set_fill_color(*ACCENT)
    pdf.rect(MARGIN, y, box, box, style="F")
    pdf.set_xy(MARGIN, y + 0.5)
    pdf.set_font("NotoBold", size=10)
    pdf.set_text_color(*WHITE)
    pdf.cell(box, box - 1, number, align="C")

    pdf.set_xy(MARGIN + box + 4, y - 0.5)
    pdf.set_font("NotoBold", size=15)
    pdf.set_text_color(*PRIMARY)
    pdf.cell(0, box + 1, text)

    pdf.set_draw_color(*ACCENT)
    pdf.set_line_width(0.6)
    pdf.line(MARGIN, y + box + 2.5, pdf.w - MARGIN, y + box + 2.5)
    pdf.set_y(y + box + 6)


def render_markdown(pdf, content):
    """Render thân nội dung markdown của mỗi mục."""
    for raw in content.split("\n"):
        line = raw.rstrip()
        if not line.strip():
            pdf.ln(2.2)
            continue

        # ảnh -> căn giữa + caption
        is_img, img_path = parse_image(line)
        if is_img:
            if os.path.exists(img_path):
                max_w = pdf.w - 2 * MARGIN
                display_w = min(120, max_w)
                try:
                    info = pdf.image(img_path, w=display_w, x="C")
                    pdf.ln(info.rendered_height + 3)
                except Exception as e:
                    pdf.set_text_color(*MUTED)
                    pdf.write(BODY["line_height"], f"[Image error: {e}]")
                    pdf.ln(BODY["line_height"])
                if pdf.h - pdf.get_y() < 70:
                    pdf.add_page()
            else:
                pdf.set_text_color(*MUTED)
                pdf.write(BODY["line_height"], f"[Image not found: {img_path}]")
                pdf.ln(BODY["line_height"])
            continue

        line = strip_inline_bold(line)

        # heading ###
        level, htext = parse_heading(line)
        if level > 0:
            s = HEADING_STYLES[level]
            pdf.ln(s["before"])
            write_runs(pdf, htext, "NotoBold", s["size"], s["size"] * 0.5,
                       s["size"] * 0.42, color=PRIMARY)
            pdf.ln(s["size"] * 0.5)
            pdf.ln(s["after"])
            continue

        # bullet (hanging indent: dòng wrap thụt theo chữ, không về lề)
        is_b, indent, btext = parse_bullet(line)
        if is_b:
            bx = MARGIN + 2 + indent * 5
            old_lm = pdf.l_margin
            pdf.set_x(bx)
            pdf.set_font("NotoBold", size=BODY["size"])
            pdf.set_text_color(*ACCENT)
            pdf.write(BODY["line_height"], "•  ")
            pdf.set_left_margin(bx + 5)
            write_runs(pdf, btext, "Noto", BODY["size"], BODY["line_height"],
                       BODY["emoji_size"], color=INK)
            pdf.set_left_margin(old_lm)
            pdf.ln(BODY["line_height"])
            continue

        # I. II. -> sub-section in mục (đậm, teal)
        is_r, rnum, rtext = parse_roman(line)
        if is_r:
            pdf.ln(3)
            write_runs(pdf, f"{rnum}. {rtext}", "NotoBold", 13, 7, 6,
                       color=PRIMARY)
            pdf.ln(7); pdf.ln(2)
            continue

        # 1. numbered -> tiêu đề nhỏ đậm
        is_n, num, ntext = parse_numbered(line)
        if is_n:
            pdf.ln(2.5)
            write_runs(pdf, f"{num}.  {ntext}", "NotoBold", 11.5, 6.2, 5.5,
                       color=PRIMARY_DK)
            pdf.ln(6.2); pdf.ln(1.5)
            continue

      
        is_f, flabel, frest = parse_field_label(line)
        if is_f:
            pdf.ln(1.6)
            pdf.set_x(MARGIN)
            pdf.set_font("NotoBold", size=BODY["size"])
            pdf.set_text_color(*PRIMARY_DK)
            pdf.write(BODY["line_height"], f"{flabel}:")
            if frest:
                pdf.write(BODY["line_height"], "  ")
                write_runs(pdf, frest, "Noto", BODY["size"], BODY["line_height"],
                           BODY["emoji_size"], color=INK)
            pdf.ln(BODY["line_height"])
            continue

        # body: căn đều 2 biên cho gọn (chỉ khi không có emoji), ngược lại fallback
        text = line.strip()
        if _has_emoji(text):
            write_runs(pdf, text, "Noto", BODY["size"], BODY["line_height"],
                       BODY["emoji_size"], color=INK)
            pdf.ln(BODY["line_height"])
        else:
            pdf.set_x(MARGIN)
            pdf.set_font("Noto", size=BODY["size"])
            pdf.set_text_color(*INK)
            pdf.multi_cell(pdf.w - 2 * MARGIN, BODY["line_height"], text, align="J")



def build_report(
    pdf_path: str,
    profile: dict,
    radar_image: str | None = None,
    analysis: str = "",
    career_plan: str = "",
    scores: list | None = None,
    report_title: str = "Student Assessment Report",
    subtitle: str = "Cá nhân hoá lộ trình phát triển sinh viên",
) -> str:
    """Dựng PDF báo cáo đẹp (cover + profile card + radar + bảng điểm) và ghi
    ra `pdf_path`. Trả về `pdf_path`."""
    regular_font = _resolve_font(
        "/tmp/NotoSans-Regular.ttf", _NOTO_URL, _FALLBACK_TTFS
    )
    bold_font = _resolve_font(
        "/tmp/NotoSans-Bold.ttf", _NOTO_BOLD_URL, _FALLBACK_TTFS_BOLD
    )
    if not regular_font:
        raise RuntimeError(
            "Không tìm thấy font TTF Unicode để dựng PDF (cache, mạng, fallback đều thất bại)."
        )

    os.makedirs(os.path.dirname(os.path.abspath(pdf_path)), exist_ok=True)

    pdf = ReportPDF(report_title=report_title,
                    regular_font=regular_font, bold_font=bold_font)
    pdf.add_page()

    draw_cover(
        pdf,
        title=report_title,
        subtitle=subtitle,
        meta_lines=[f"Ngày xuất bản: {datetime.now():%d/%m/%Y}",
                    f"Giai đoạn: {profile.get('stage_name', '')}"],
    )

    # ---- I. Profile ----
    draw_section_header(pdf, "I", "Thông tin sinh viên")
    draw_profile_card(pdf, [
        ("Họ và tên", profile.get("name", "")),
        ("Email", profile.get("email", "")),
        ("Năm học", profile.get("year_level", "")),
        ("Chương trình đào tạo", profile.get("program_duration", "")),
        ("Học kỳ", profile.get("semester", "")),
        ("Giai đoạn", profile.get("stage_name", "")),
    ])

    # ---- II. Radar Chart ----
    draw_section_header(pdf, "II", "Biểu đồ năng lực (Radar)")
    if radar_image and os.path.exists(radar_image):
        img_w = 92
        # cần đủ chỗ cho ảnh + caption, nếu không thì sang trang mới
        if pdf.h - pdf.get_y() - 20 < img_w + 14:
            pdf.add_page()
        y_img = pdf.get_y()
        pdf.image(radar_image, w=img_w, x="C")
        pdf.set_y(y_img + img_w + 2)           
        pdf.set_font("Noto", size=8.5)
        pdf.set_text_color(*MUTED)
        pdf.cell(0, 5, "Hình 1. Điểm sinh viên so với ngưỡng chuẩn của giai đoạn", align="C")
        pdf.ln(8)
    if scores:
        draw_score_table(pdf, scores)
    render_markdown(pdf, analysis or "")

    # ---- III. Career plan ----
    draw_section_header(pdf, "III", "Kế hoạch phát triển & định hướng")
    render_markdown(pdf, career_plan or "")

    pdf.output(pdf_path)
    return pdf_path
