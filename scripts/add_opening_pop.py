"""Insert an opening slide: five questions fade and scale in, one after another."""

from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

PATH = r"c:\Users\LIUSI\Desktop\NUS\DSS5105\DSS5105_26fall_Group10_TheGeneralManager-sCo-Pilot\Presentation_Group10_Sprint2.pptx"
P = "http://schemas.openxmlformats.org/presentationml/2006/main"
INK = RGBColor(0x1C, 0x19, 0x17)
BRASS = RGBColor(0x8C, 0x6A, 0x3D)
FONT = "Calibri"

LINES = [
    (0.7, 1.15, "7:00", "Did anything go wrong yesterday?"),
    (6.5, 0.85, "9:40", "How is the TrendCart order doing?"),
    (0.85, 3.05, "11:15", "800 hoodies by the 25th. Can we take it?"),
    (6.3, 3.25, "14:30", "It hasn't moved in a week. Chase it."),
    (3.15, 5.25, "17:00", "Remind me if packing is still behind."),
]


def set_run(run, text, size, bold, color):
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


def add_line(slide, left, top, clock, question):
    shape = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(6.2), Inches(1.25))
    tf = shape.text_frame
    tf.word_wrap = True
    for margin in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(tf, margin, Emu(0))
    p1 = tf.paragraphs[0]
    p1.alignment = PP_ALIGN.LEFT
    r1 = p1.add_run()
    set_run(r1, clock, 18, True, BRASS)
    p2 = tf.add_paragraph()
    p2.alignment = PP_ALIGN.LEFT
    p2.space_before = Pt(2)
    r2 = p2.add_run()
    set_run(r2, question, 26, True, INK)
    return shape.shape_id


def pel(tag, **attrs):
    element = etree.Element("{%s}%s" % (P, tag))
    for key, value in attrs.items():
        element.set(key, str(value))
    return element


def effect(ids, spid, delay):
    """Fade plus a small scale-up. delay is milliseconds after the previous effect ends."""
    outer = pel("par")
    node = pel("cTn", id=ids.next(), fill="hold")
    conds = pel("stCondLst")
    conds.append(pel("cond", delay=delay))
    node.append(conds)
    children = pel("childTnLst")
    inner = pel("par")
    effect_node = pel(
        "cTn",
        id=ids.next(),
        presetID="10",
        presetClass="entr",
        presetSubtype="0",
        fill="hold",
        grpId="0",
        nodeType="afterEffect",
    )
    start = pel("stCondLst")
    start.append(pel("cond", delay="0"))
    effect_node.append(start)
    behaviors = pel("childTnLst")

    show = pel("set")
    show_bhvr = pel("cBhvr")
    show_tn = pel("cTn", id=ids.next(), dur="1", fill="hold")
    show_start = pel("stCondLst")
    show_start.append(pel("cond", delay="0"))
    show_tn.append(show_start)
    show_bhvr.append(show_tn)
    target = pel("tgtEl")
    target.append(pel("spTgt", spid=spid))
    show_bhvr.append(target)
    names = pel("attrNameLst")
    names.append(pel("attrName"))
    names[0].text = "style.visibility"
    show_bhvr.append(names)
    show.append(show_bhvr)
    to = pel("to")
    to.append(pel("strVal", val="visible"))
    show.append(to)
    behaviors.append(show)

    fade = pel("animEffect", transition="in", filter="fade")
    fade_bhvr = pel("cBhvr")
    fade_bhvr.append(pel("cTn", id=ids.next(), dur="350"))
    fade_target = pel("tgtEl")
    fade_target.append(pel("spTgt", spid=spid))
    fade_bhvr.append(fade_target)
    fade.append(fade_bhvr)
    behaviors.append(fade)

    scale = pel("animScale")
    scale_bhvr = pel("cBhvr")
    scale_bhvr.append(pel("cTn", id=ids.next(), dur="350"))
    scale_target = pel("tgtEl")
    scale_target.append(pel("spTgt", spid=spid))
    scale_bhvr.append(scale_target)
    scale.append(scale_bhvr)
    scale.append(pel("from", x="85000", y="85000"))
    scale.append(pel("to", x="100000", y="100000"))
    behaviors.append(scale)

    effect_node.append(behaviors)
    wrap = pel("par")
    wrap.append(effect_node)
    inner.append(wrap)
    children.append(inner)
    node.append(children)
    outer.append(node)
    return outer


class Ids:
    def __init__(self):
        self.n = 10

    def next(self):
        self.n += 1
        return str(self.n)


def timing(spids):
    etree.register_namespace("p", P)
    root = pel("timing")
    tn_list = pel("tnLst")
    root_par = pel("par")
    root_tn = pel("cTn", id="1", dur="indefinite", restart="never", nodeType="tmRoot")
    root_children = pel("childTnLst")
    seq = pel("seq", concurrent="with", nextAc="seek")
    seq_tn = pel("cTn", id="2", dur="indefinite", nodeType="mainSeq")
    seq_children = pel("childTnLst")
    click = pel("par")
    click_tn = pel("cTn", id="3", fill="hold")
    click_conds = pel("stCondLst")
    click_conds.append(pel("cond", delay="0"))
    click_tn.append(click_conds)
    click_children = pel("childTnLst")
    ids = Ids()
    for index, spid in enumerate(spids):
        click_children.append(effect(ids, spid, "200" if index == 0 else "400"))
    click_tn.append(click_children)
    click.append(click_tn)
    seq_children.append(click)
    seq_tn.append(seq_children)
    seq.append(seq_tn)
    for tag, event in (("prevCondLst", "onPrev"), ("nextCondLst", "onNext")):
        cond_list = pel(tag)
        cond = pel("cond", evt=event, delay="0")
        target = pel("tgtEl")
        target.append(pel("sldTgt"))
        cond.append(target)
        cond_list.append(cond)
        seq.append(cond_list)
    root_children.append(seq)
    root_tn.append(root_children)
    root_par.append(root_tn)
    tn_list.append(root_par)
    root.append(tn_list)
    return root


def move_to_front(prs):
    listing = prs.slides._sldIdLst
    items = list(listing)
    last = items[-1]
    listing.remove(last)
    listing.insert(0, last)


def drop_opening(prs):
    first = prs.slides[0]
    text = " ".join(shape.text_frame.text for shape in first.shapes)
    if "Did anything go wrong yesterday?" not in text:
        return
    rel_id = prs.slides._sldIdLst[0].get(
        "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    )
    prs.part.drop_rel(rel_id)
    prs.slides._sldIdLst.remove(prs.slides._sldIdLst[0])


def main():
    prs = Presentation(PATH)
    drop_opening(prs)
    prs.save(PATH)
    prs = Presentation(PATH)
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    spids = [str(add_line(slide, *line)) for line in LINES]
    slide._element.append(timing(spids))
    notes = slide.notes_slide.notes_text_frame
    notes.text = (
        "Opening, about 3.5 seconds. Press F5 once if it waits for a click; "
        "the five questions then fade and scale in on their own. "
        "This page replaces reading the list on the next slide."
    )
    move_to_front(prs)
    prs.save(PATH)
    print("slides", len(prs.slides), "spids", ",".join(spids))


if __name__ == "__main__":
    main()
