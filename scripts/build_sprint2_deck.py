"""Sprint 2 deck. Content only. Widescreen, editable tables."""

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt
from lxml import etree

OUT = r"c:\Users\LIUSI\Desktop\NUS\DSS5105\DSS5105_26fall_Group10_TheGeneralManager-sCo-Pilot\Presentation_Group10_Sprint2.pptx"

INK = RGBColor(0x1C, 0x19, 0x17)
MUTED = RGBColor(0x5C, 0x56, 0x4E)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
HEADER = RGBColor(0x1C, 0x19, 0x17)
ZEBRA = RGBColor(0xF6, 0xF3, 0xEE)
FONT = "Calibri"


def set_run(run, text, size, bold=False, color=INK):
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = FONT
    r_pr = run._r.get_or_add_rPr()
    for tag in ("a:latin", "a:ea", "a:cs"):
        node = r_pr.find(qn(tag))
        if node is None:
            node = etree.SubElement(r_pr, qn(tag))
        node.set("typeface", FONT)


def add_text(slide, l, t, w, h, text, size=18, bold=False, color=INK):
    shape = slide.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    tf = shape.text_frame
    tf.word_wrap = True
    tf.auto_size = None
    body_pr = tf._txBody.find(qn("a:bodyPr"))
    body_pr.set("anchor", "t")
    lines = text.split("\n") if isinstance(text, str) else text
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.LEFT
        p.space_after = Pt(4)
        run = p.add_run()
        set_run(run, line, size, bold, color)
    return shape


def notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text


def paint_cell(cell, text, size, bold=False, fill=None, color=INK):
    cell.text = ""
    cell.vertical_anchor = MSO_ANCHOR.MIDDLE
    cell.margin_left = Inches(0.08)
    cell.margin_right = Inches(0.08)
    cell.margin_top = Inches(0.04)
    cell.margin_bottom = Inches(0.04)
    p = cell.text_frame.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    run = p.add_run()
    set_run(run, text, size, bold, color)
    if fill is not None:
        cell.fill.solid()
        cell.fill.fore_color.rgb = fill


def add_table(slide, rows, left, top, width, height, font=13):
    table = slide.shapes.add_table(len(rows), len(rows[0]), Inches(left), Inches(top), Inches(width), Inches(height)).table
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            paint_cell(
                table.cell(r, c),
                value,
                14 if r == 0 else font,
                bold=(r == 0),
                fill=HEADER if r == 0 else (ZEBRA if r % 2 == 0 else WHITE),
                color=WHITE if r == 0 else INK,
            )
    return table


def build():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    prs.core_properties.title = "Presentation_Group10_Sprint2"
    prs.core_properties.subject = "SweaterCo GM Co-Pilot Sprint 2"
    blank = prs.slide_layouts[6]

    # 1 pain
    s = prs.slides.add_slide(blank)
    add_text(s, 0.5, 0.32, 12.3, 0.35, "Sprint 2  ·  Group 10  ·  0:00–0:50", 14, True, MUTED)
    add_text(s, 0.5, 0.7, 12.3, 0.7, "The manager still cannot read SQL", 32, True)
    add_text(s, 0.5, 1.5, 12.3, 0.7, "Sprint 1 already named his day. This round deepens one point: the result on his screen contains no SQL either. Table names, column names, and SELECT stay inside the system.", 18)
    moments = [
        "7:00     Did anything go wrong yesterday?",
        "9:40     How is the TrendCart order doing?",
        "11:15    800 hoodies by the 25th. Can we take it?",
        "14:30    It hasn't moved in a week. Chase it.",
        "17:00    Remind me if packing is still behind.",
    ]
    add_text(s, 0.5, 2.35, 12.3, 2.6, "\n".join(moments), 22, True)
    add_text(s, 0.5, 5.35, 12.3, 1.5, "He sends these questions to someone who can write SQL. What comes back is a query, or a number he cannot check.\nWhat we hand him is a sentence, a chart, a table, and Why.", 18)
    notes(s, "0:00–0:50. Do not re-explain the factory. He cannot write SQL, and he should not have to read it in the answer. Point at the five times. Then the last two lines.")

    # 2 architecture
    s = prs.slides.add_slide(blank)
    add_text(s, 0.5, 0.32, 12.3, 0.35, "Sprint 2  ·  Group 10  ·  0:50–1:50", 14, True, MUTED)
    add_text(s, 0.5, 0.7, 12.3, 0.6, "Architecture, before and after", 32, True)
    rows = [
        ["Sprint 1", "Now"],
        ["The model picks one tool.", "First ask three things: is there more than one legal way to answer? Is the fact in the tables? Can a current tool retrieve it?"],
        ["Python calculates. SQL stays inside the tool.", "Same rule. The chat answer, the morning briefing, and the weekly briefing show no SQL."],
        ["A few lines, plus Why.", "A sentence, a chart or a table, and Why. The weekly view is three charts from the existing briefing call. It is not a new tool."],
    ]
    table = add_table(s, rows, 0.45, 1.55, 12.4, 4.15, font=16)
    table.columns[0].width = Inches(4.6)
    table.columns[1].width = Inches(7.8)
    add_text(s, 0.5, 5.9, 12.3, 1.2, "We considered letting the model write the SQL. The questions would be freer, and the screen would show statements he cannot read or check. Arithmetic stays in Python. The screen keeps the result and where it came from.", 16)
    notes(s, "0:50–1:50. Read the table left to right, one row at a time. Close on the decision: we did not let the model write SQL. Weekly charts are computed inside the existing briefing, from orders and production_log. No new chat tool.")

    # 3 progress
    s = prs.slides.add_slide(blank)
    add_text(s, 0.5, 0.28, 12.3, 0.3, "Sprint 2  ·  Group 10  ·  1:50–3:00", 14, True, MUTED)
    add_text(s, 0.5, 0.58, 12.3, 0.5, "Progress, before and after", 28, True)
    add_text(s, 0.5, 1.15, 12.3, 0.35, "Left column is what Sprint 1 said we would do next. Fill the owner column with real names.", 14, color=MUTED)
    rows = [
        ["Sprint 1 left this", "Now", "Owner"],
        ["Several TrendCart orders, and the model guessed one.", "A clarification card asks which one.", ""],
        ["“Can we take 800 hoodies?” became yes or no.", "A feasibility estimate, with the assumptions written out.", ""],
        ["Why restated the previous sentence.", "The numbers in Why come from Python.", ""],
        ["A lowercase order id missed. Missing data could be invented.", "Order ids ignore case. No selling price: refuse, and call no tool.", ""],
        ["The 7:00 briefing was not built.", "It opens on demand. A Monday auto-popup is not built.", ""],
        ["Last week meant asking someone for an export.", "Three charts: on time and overdue, four stages, last full week’s products by customer.", ""],
    ]
    table = add_table(s, rows, 0.4, 1.55, 12.5, 4.15, font=13)
    table.columns[0].width = Inches(5.3)
    table.columns[1].width = Inches(5.7)
    table.columns[2].width = Inches(1.5)
    add_text(s, 0.45, 5.85, 12.4, 1.35, "Validation. The baseline is Sprint 1’s two failures: the model did the arithmetic, or it answered when the lookup missed. Three hard cases: revenue is not in the tables; TrendCart cannot be chosen for him; week 14 drops because that week stops on 1 April 2026. A formal held-out score is still in progress.", 14)
    notes(s, "1:50–3:00. Walk the six rows. Do not open a fourth lecture for validation: read the bottom line only. Say clearly what is not built: Monday auto-popup, and the official held-out score.")

    # 4 demo card — not for playback
    s = prs.slides.add_slide(blank)
    add_text(s, 0.5, 0.32, 12.3, 0.35, "Do not play this slide. Record the product.  3:00–5:00", 14, True, MUTED)
    add_text(s, 0.5, 0.72, 12.3, 0.55, "Demo: his day, three scenes", 32, True)
    add_text(s, 0.5, 1.4, 12.3, 0.7, "Each scene has three beats: what he needs, what the screen shows, what he does with it. Keep about 3 seconds of the progress line, then cut to the result. A live call is about 30 seconds. Say that in the Q&A.", 16)
    rows = [
        ["Time", "Do this", "Stop when"],
        ["7:00", "Open Morning briefing, then Last week's briefing. Stay on the three charts.", "You have said week 14 falls because the week is not finished."],
        ["9:40", "Ask: How is the TrendCart order doing? Pick one option on the card. Open Why.", "The answer shows the order, pieces, and status, and Why shows the tool numbers. No SQL."],
        ["11:15", "Ask: 800 hoodies by the 25th. Can we take it?", "The answer is an estimate with assumptions, not “yes”. End the video on this frame."],
    ]
    table = add_table(s, rows, 0.4, 2.25, 12.5, 3.3, font=15)
    table.columns[0].width = Inches(1.4)
    table.columns[1].width = Inches(6.3)
    table.columns[2].width = Inches(4.8)
    add_text(s, 0.5, 5.8, 12.3, 1.2, "14:30 chase and 17:00 reminder stay on the progress slide. Do not open them. Anything after 5:00 is cut.", 18, True)
    notes(s, "Shooting card only. Record the browser, not this slide. Pre-run the two questions while the first three minutes play, so the cut lands on a finished answer. Export and check the file is under 4:50 before you add anything back.")

    prs.save(OUT)
    print(OUT)


if __name__ == "__main__":
    build()
