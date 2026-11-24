import json
import re
import smtplib
from dataclasses import dataclass, field
from email.message import EmailMessage
from html import escape
from pathlib import Path

from .audit import OUTCOME_LABEL, Context, Finding
from . import zh
from .llm import LLM

DOC_NAMES = {
    "zh-TW": {"invoice": "發票", "po": "採購單", "commitment": "模具訂單承諾書", "approval": "模具承認書",
              "spec": "模具規格書", "custody": "模具保管單", "cost_breakdown": "模具費用明細表"},
    "en": {"invoice": "invoice", "po": "purchase order", "commitment": "tooling order commitment letter",
           "approval": "mold approval sheet", "spec": "mold specification", "custody": "tooling custody agreement",
           "cost_breakdown": "tooling cost breakdown"},
}
ROLE_NAMES = {"zh-TW": {"design": "模具設計", "qa": "品保", "me": "ME"},
              "en": {"design": "Mold Design", "qa": "QA", "me": "ME"}}
SEP = {"zh-TW": "、", "en": ", "}

VENDOR_LINES = {
    "zh-TW": {
        "R01": "缺少以下文件：{missing}，請補齊後一併提供。",
        "R02": "{doc}第 {page} 頁的訂單號寫為 {value}，正確應為 {want}，請更正並重新用印。",
        "R03": "{doc}第 {page} 頁的模具編號寫為 {value}，正確應為 {want}，請更正並重新用印。",
        "R04_invoice": "發票未稅金額 {cur} {invoice} 與訂單金額 {cur} {po} 不一致，請依訂單金額重開發票。",
        "R04_cost": "費用明細表合計 {cur} {cost} 與訂單金額 {cur} {po} 不一致，請更正明細表。",
        "R05": "發票幣別為 {invoice}，訂單幣別為 {po}，請依訂單幣別重開發票。",
        "R07_lack": "模具承認書尚缺 {roles} 簽核，請安排補簽後重新提供。",
        "R07_result": "模具承認書判定結果為「{result}」，尚未承認，暫無法請款。",
        "R11": "文件日期順序有誤（訂單日 {po_date}、承認日 {approval_date}、發票日 {invoice_date}），請確認。",
        "R12": "發票稅率 {rate} 與約定稅率 {master} 不符，請重開發票。",
        "R13": "發票開立方「{seller}」與貴司登記名稱不符，請確認開票主體。",
    },
    "en": {
        "R01": "The following documents are missing: {missing}. Please provide them together.",
        "R02": "The PO number on page {page} of the {doc} reads {value}; it should be {want}. Please correct and re-stamp.",
        "R03": "The mold number on page {page} of the {doc} reads {value}; it should be {want}. Please correct and re-stamp.",
        "R04_invoice": "The invoice amount before tax ({cur} {invoice}) does not match the PO amount ({cur} {po}). Please reissue the invoice.",
        "R04_cost": "The cost breakdown total ({cur} {cost}) does not match the PO amount ({cur} {po}). Please correct it.",
        "R05": "The invoice is in {invoice} but the PO is in {po}. Please reissue the invoice in the PO currency.",
        "R07_lack": "The mold approval sheet is missing the {roles} signature. Please have it signed and resend.",
        "R07_result": "The mold approval result is \"{result}\"; payment cannot proceed until the mold is approved.",
        "R11": "The document dates are out of order (PO {po_date}, approval {approval_date}, invoice {invoice_date}). Please check.",
        "R12": "The invoice tax rate {rate} differs from the agreed rate {master}. Please reissue the invoice.",
        "R13": "The invoice issuer \"{seller}\" does not match your registered company name. Please confirm the issuing entity.",
    },
}

INTERNAL_ACTIONS = {
    "R06": "請策購在模具廠商主檔建立此廠商（代號、窗口、幣別、稅率）後重新執行。",
    "R08": "請確認新的保管人，請廠商更新保管單；資產管理已在副本。",
    "R09": "請先在 SAP 完成收貨（GR），再重新執行本案。",
    "R10": "此 PO 已有付款紀錄，疑似重複請款。請與財務確認後再決定是否退回廠商。",
}

INTRO_FALLBACK = {
    "need_vendor_docs": {
        "zh-TW": "{contact} 您好，貴司就採購訂單 {po}（模具 {mold}）提交的請款文件經本公司審核，尚有以下事項需要更正，請處理後重新提供，謝謝。",
        "en": "Dear {contact}, we have reviewed the payment documents for PO {po} (mold {mold}). The items below need to be corrected before we can proceed. Please resend the corrected documents. Thank you.",
    },
    "ready_to_sign": {"zh-TW": "{pic} 您好，{vendor} PO {po} 的請款文件已完成稽核，各項檢核皆通過，驗收單已預填在附件。"},
    "internal_action": {"zh-TW": "{pic} 您好，{vendor} PO {po} 的請款文件有需要內部處理的項目，處理完成前先不要送簽。"},
    "master_data": {"zh-TW": "策購同仁好，承辦 {pic} 收到 {vendor} 的模具請款（PO {po}），但此廠商不在模具廠商主檔，請協助建檔。"},
}


@dataclass
class Draft:
    subject: str
    html: str
    text: str
    to: list[str]
    cc: list[str]
    lang: str
    intro_source: str
    attachments: list[Path] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _money(v) -> str:
    return f"{v:,.2f}" if isinstance(v, (int, float)) else str(v)


def vendor_lines(findings: list[Finding], lang: str) -> list[str]:
    L, docs, roles = VENDOR_LINES[lang], DOC_NAMES[lang], ROLE_NAMES[lang]
    out = []
    for f in findings:
        if f.status != "fail" or f.owner != "vendor":
            continue
        d = f.data
        if f.rule == "R01":
            out.append(L["R01"].format(missing=SEP[lang].join(docs[m] for m in d["missing"])))
        elif f.rule in ("R02", "R03"):
            out += [L[f.rule].format(doc=docs.get(e["doc_key"], e["doc"]), page=e["page"], value=e["value"],
                                     want=d["want"]) for e in d["diffs"]]
        elif f.rule == "R04":
            kw = {"cur": d["currency"], "invoice": _money(d["invoice"]), "po": _money(d["po"]),
                  "cost": _money(d["cost"])}
            if d["invoice_bad"]:
                out.append(L["R04_invoice"].format(**kw))
            if d["cost_bad"]:
                out.append(L["R04_cost"].format(**kw))
        elif f.rule == "R07":
            if d["lack"]:
                out.append(L["R07_lack"].format(roles=SEP[lang].join(roles[r] for r in d["lack"])))
            if d["result"] != "approved":
                out.append(L["R07_result"].format(result=d["result"]))
        elif f.rule == "R12":
            out.append(L["R12"].format(rate=f"{d['rate']:.0%}", master=f"{d['master']:.0%}"))
        else:
            out.append(L[f.rule].format(**d))
    return out




GENDERED = re.compile(r"先生|小姐|女士|\b(Mr|Mrs|Ms|Miss)\b\.?", re.I)


def _numbers(s: str) -> set[str]:
    return {n.replace(",", "") for n in re.findall(r"\d[\d,.\-]*\d|\d", s)}


def llm_intro(llm: LLM, facts: dict, lang: str, fallback: str) -> tuple[str, str]:
    lang_name = {"zh-TW": "繁體中文（台灣用字，不可出現簡體字）", "en": "English"}[lang]
    prompt = (f"你在幫採購寫一封信的開頭段落。整段必須使用：{lang_name}。\n"
              f"這封信的收件人是：{facts.get('收件人')}。用對收件人的稱呼與語氣。\n"
              "稱呼一律用全名加「您好」（英文用 Dear 加全名），不要用先生、小姐、女士、Mr.、Ms. 這類依性別的稱謂；"
              "也不要自稱「我是某某部門」。細節清單就寫在這封信的下方，不是附件，不要說「附件」或 attached。\n"
              "依下列事實寫 2–3 句，直接說明狀況與希望對方做什麼。\n"
              "限制：只能轉述事實中寫到的內容，不可改寫成相反意思；不要條列細節（細節另有清單）；"
              "不要加入事實以外的數字、日期或承諾；不要寫署名。\n"
              f"事實：{json.dumps(facts, ensure_ascii=False)}")
    try:
        text = llm.json(prompt, {"type": "object", "properties": {"intro": {"type": "string"}},
                                 "required": ["intro"], "additionalProperties": False})["intro"].strip()
    except Exception as e:
        return fallback, f"範本（LLM 失敗：{e.__class__.__name__}）"
    allowed = _numbers(json.dumps(facts, ensure_ascii=False))
    extra = _numbers(text) - allowed
    if extra:
        return fallback, f"範本（LLM 段落含事實以外的數字 {sorted(extra)}）"
    if GENDERED.search(text):
        return fallback, "範本（LLM 段落用了依性別的稱謂）"
    if not text or len(text) > 400:
        return fallback, "範本（LLM 段落長度不合格）"
    return text, "LLM"


def _table(rows: list[tuple[str, str]]) -> str:
    cells = "".join(
        f"<tr><th style='background:#1F3A5F;color:#fff;text-align:left;padding:6px 10px;width:150px;"
        f"border:1px solid #c8ccd2'>{escape(k)}</th><td style='padding:6px 10px;border:1px solid #c8ccd2'>"
        f"{escape(str(v))}</td></tr>" for k, v in rows)
    return f"<table style='border-collapse:collapse;font-size:13px;margin:8px 0 16px'>{cells}</table>"


def _banner(text: str, color: str) -> str:
    return (f"<div style='background:{color};color:#fff;padding:8px 12px;font-weight:bold;font-size:14px;"
            f"margin:8px 0'>{escape(text)}</div>")


def _wrap(lang: str, company: str, *parts: str) -> str:
    foot = {"en": "This email was drafted by auditbox for {company}. Please contact your buyer with any questions.",
            "zh-TW": "本信由 auditbox 自動擬稿，寄出前請承辦確認內容。"}[lang].format(company=company)
    return ("<div style='font-family:Microsoft JhengHei,PingFang TC,Arial,sans-serif;font-size:14px;"
            "color:#222;line-height:1.6'>" + "".join(parts) +
            f"<p style='color:#888;font-size:12px;margin-top:24px'>{escape(foot)}</p></div>")


def compose(*, outcome: str, findings: list[Finding], ctx: Context, case: dict, route, form_vals: dict | None,
            company: str, llm: LLM | None, llm_mode: str = "internal", company_en: str | None = None) -> Draft:
    v = ctx.vendor
    po, mold = ctx.po_no, (ctx.sap_po or {}).get("模具編號", "")
    vendor_name = v.short if v else (ctx.sap_po or {}).get("供應商名稱", "")
    pic = case["pic"]
    # 對外信只分英文與繁體；主檔標「簡中」的廠商也寄繁體
    lang = "en" if outcome == "need_vendor_docs" and v and v.lang == "en" else "zh-TW"
    if lang == "en" and company_en:
        company = company_en
    fails = [f for f in findings if f.status == "fail"]
    fmt = {"contact": v.contact if v else "", "po": po, "mold": mold, "pic": pic["姓名"], "vendor": vendor_name}
    if outcome == "need_vendor_docs":
        lines = vendor_lines(findings, lang)
        facts = {"收件人": v.contact, "收件廠商": v.name_local if lang != "en" else v.name_en, "採購訂單": po,
                 "模具編號": mold,
                 "需更正事項數": len(lines), "寄件公司": company}
        subject = {"zh-TW": f"【補件通知】PO {po} / {mold} 請款文件需更正 - {company}",
                   "en": f"[Action Required] PO {po} / {mold} - payment documents need correction"}[lang]
    else:
        lines = [f"{f.rule} {f.name}：{f.message}" for f in fails]
        facts = {"收件人": "策購部同事" if outcome == "master_data" else f"公司內部承辦 {pic['姓名']}",
                 "廠商": vendor_name, "PO": po, "模具編號": mold, "稽核結果": OUTCOME_LABEL[outcome],
                 "發現的問題": [f.message for f in fails] or ["無，全部通過"]}
        mark = {"ready_to_sign": "✅ 可送簽", "internal_action": "⚠ 內部處理", "master_data": "⚠ 主檔維護"}[outcome]
        subject = f"[模具請款AI] {vendor_name} PO {po} {mark}"
    fallback = INTRO_FALLBACK[outcome][lang].format(**fmt)
    use_llm = llm and (llm_mode == "all" or (llm_mode == "internal" and outcome in ("internal_action", "master_data")))
    intro, source = llm_intro(llm, facts, lang, fallback) if use_llm else (fallback, "範本")

    file_row = [("檔案", f"{case['files']['invoice']}、{case['files']['attachment']}")]
    if outcome == "need_vendor_docs":
        head = {"zh-TW": "需更正事項", "en": "Items to correct"}[lang]
        info = {"zh-TW": [("採購訂單", po), ("模具編號", mold)],
                "en": [("PO No.", po), ("Mold No.", mold)]}[lang]
        html = _wrap(lang, company, f"<p>{escape(intro)}</p>", _table(info), f"<p><b>{head}</b></p><ol>" +
                     "".join(f"<li>{escape(l)}</li>" for l in lines) + "</ol>")
    elif outcome == "ready_to_sign":
        passed = sum(f.status == "pass" for f in findings)
        summary = (f"文件齊全，{passed} 項檢核全部通過" if passed == len(findings)
                   else f"文件齊全，{passed} 項檢核通過、{len(findings) - passed} 項不適用")
        html = _wrap(lang, company, f"<p>{escape(intro)}</p>", _banner("✅ 可送簽　沒有需處理的項目", "#2E7D32"),
                     _table(file_row + [("廠商", v.name_local), ("PO 號", po), ("摘要", summary)]),
                     "<p><b>驗收單內容（已填入附件）</b></p>",
                     _table([(k, form_vals[k]) for k in ("廠商名稱", "廠商代號", "PO 號", "GR 號", "收貨日期",
                                                        "驗收日期", "品名", "未稅總價", "存放地點", "保管人工號")]),
                     f"<p><b>下一步：</b>請確認附件驗收單，沒問題後以傳簽單送簽。合併 PDF：{escape(str(case.get('merged_pdf', '')))}</p>")
    else:
        actions = [INTERNAL_ACTIONS[f.rule] for f in fails if f.rule in INTERNAL_ACTIONS]
        html = _wrap(lang, company, f"<p>{escape(intro)}</p>", _banner(f"⚠ {OUTCOME_LABEL[outcome]}", "#B26A00"),
                     _table(file_row + [("廠商", vendor_name), ("PO 號", po), ("模具編號", mold)]),
                     "<p><b>稽核發現</b></p><ul>" + "".join(f"<li>{escape(l)}</li>" for l in lines) + "</ul>",
                     "<p><b>需要的處理</b></p><ul>" + "".join(f"<li>{escape(a)}</li>" for a in actions) + "</ul>")
    subject, html = zh.t(subject), zh.t(html)
    text = re.sub(r"<[^>]+>", "\n", html)
    text = re.sub(r"\n\s*\n+", "\n", text).strip()
    atts = [Path(case["form_xlsx"])] if outcome == "ready_to_sign" and case.get("form_xlsx") else []
    return Draft(subject, html, text, route.to, route.cc, lang, source, atts, list(route.warnings))


def to_eml(d: Draft, sender: str, out: Path) -> Path:
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = d.subject, sender, ", ".join(d.to)
    if d.cc:
        msg["Cc"] = ", ".join(d.cc)
    msg["X-Unsent"] = "1"
    msg.set_content(d.text)
    msg.add_alternative(d.html, subtype="html")
    for a in d.attachments:
        msg.add_attachment(a.read_bytes(), maintype="application",
                           subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename=a.name)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(bytes(msg))
    return out


def send_mailpit(eml: Path, host: str, port: int):
    from email import message_from_bytes, policy
    msg = message_from_bytes(eml.read_bytes(), policy=policy.default)
    with smtplib.SMTP(host, port, timeout=10) as s:
        s.send_message(msg)
