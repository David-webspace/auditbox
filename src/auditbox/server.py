import os
import subprocess
import sys
import threading
from dataclasses import asdict
from pathlib import Path

import httpx
import pymupdf
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, localstore, pipeline, routing
from . import normalize as N
from .db import DB, STATUSES
from .llm import CLAUDE_MODELS, from_settings

WEB = Path(__file__).resolve().parents[2] / "web" / "out"


class Job:
    def __init__(self, pic: str, bases: list[str]):
        self.pic = pic
        self.items = [{"base": b, "status": "等待中", "case_id": None, "outcome": None} for b in bases]
        self.log: list[str] = []
        self.running = True
        self.stop = False
        self.skip = False

    def write(self, msg: str):
        self.log.append(msg)


class RunRequest(BaseModel):
    pic: str
    bases: list[str]


class StatusRequest(BaseModel):
    status: str
    note: str = ""


class OpenRequest(BaseModel):
    target: str


class LLMRequest(BaseModel):
    provider: str
    model: str | None = None
    api_key: str | None = None  # None＝不變更；空字串＝清除


local_db_path = localstore.db_path
HOST_WORKSPACE = os.environ.get("AUDITBOX_HOST_WORKSPACE")  # Docker 模式：主機上的工作區路徑，只用來顯示


def _short(path) -> str:
    """畫面上的路徑把家目錄縮成 ~，截圖時不會露出電腦的帳號名稱。"""
    p, home = str(path), str(Path.home())
    return "~" + p[len(home):] if p == home or p.startswith(home + os.sep) else p


def _key_hint(key: str | None) -> str | None:
    return f"{key[:7]}…{key[-4:]}" if key and len(key) > 12 else ("已設定" if key else None)


def check_claude_key(key: str, model: str):
    """用 models.retrieve 驗證 key 與模型權限，不產生 token 費用。"""
    import anthropic
    try:
        anthropic.Anthropic(api_key=key, max_retries=0, timeout=15).models.retrieve(model)
    except anthropic.AuthenticationError:
        raise HTTPException(400, "API key 無效，請確認是否複製完整")
    except anthropic.PermissionDeniedError:
        raise HTTPException(400, "這組 API key 沒有權限使用此模型")
    except anthropic.NotFoundError:
        raise HTTPException(400, f"這組 API key 無法使用 {model}")
    except anthropic.APIConnectionError:
        raise HTTPException(502, "連不到 Anthropic API，請確認網路或公司防火牆")


def create_app(root: Path) -> FastAPI:
    ws = config.load(root)
    db = DB(local_db_path(ws))
    state: dict = {"job": None}
    app = FastAPI(title="auditbox")

    def make_llm():
        e = localstore.effective(ws.settings)
        return from_settings(ws.settings, e["provider"], e["model"], e["api_key"])

    def run_job(job: Job):
        try:
            llm = make_llm()
            pipe = pipeline.Pipeline(ws, db, pipeline.llm_extractor(ws, llm, lambda: job.stop or job.skip), llm)
        except Exception as e:
            job.write(f"❌ 讀取設定或參考資料失敗：{e}")
            job.running = False
            return
        for item in job.items:
            if job.stop:
                item["status"] = "已停止"
                continue
            item["status"] = "處理中"
            job.write(f"▶ {item['base']}")
            try:
                r = pipe.process(job.pic, item["base"], job.write)
                item.update(status="完成", case_id=r["case_id"], outcome=r["outcome"])
            except pipeline.Stopped:
                item["status"] = "已停止" if job.stop else "已略過"
                job.write(f"  ⏭ {item['status']}，檔案留在 01_待處理")
                job.skip = False
        job.write("■ 本批處理結束")
        job.running = False

    @app.get("/api/meta")
    def meta():
        e = localstore.effective(ws.settings)
        return {"pics": list(ws.settings["pics"]), "statuses": STATUSES, "llm": f"{e['provider']}:{e['model']}",
                "llm_ready": e["provider"] != "claude" or bool(e["api_key"]),
                "workspace": HOST_WORKSPACE or _short(ws.root), "can_open": not HOST_WORKSPACE,
                "mailpit_url": os.environ.get("MAILPIT_WEB_URL") if ws.settings["mail"]["mode"] == "mailpit" else None,
                "company": ws.settings["company"]["name"]}

    @app.get("/api/llm")
    def llm_get():
        e = localstore.effective(ws.settings)
        return {"provider": e["provider"], "model": e["model"] if e["provider"] == "claude" else
                localstore.load_prefs().get("model") or ws.settings["llm"]["claude"]["model"],
                "models": CLAUDE_MODELS, "key_hint": _key_hint(e["api_key"]), "key_source": e["key_source"],
                "ollama": ws.settings["llm"]["ollama"]}

    @app.put("/api/llm")
    def llm_put(req: LLMRequest):
        if state["job"] and state["job"].running:
            raise HTTPException(409, "批次執行中，請等結束再改模型設定")
        if req.provider not in localstore.PROVIDERS:
            raise HTTPException(400, "不支援的 provider")
        prefs = localstore.load_prefs()
        model = req.model or prefs.get("model") or ws.settings["llm"]["claude"]["model"]
        if model not in CLAUDE_MODELS:
            raise HTTPException(400, "不支援的模型")
        key = prefs.get("api_key")
        if req.api_key is not None:
            key = req.api_key.strip() or None
        if req.provider == "claude":
            key_to_check = key or localstore.api_key({})
            if not key_to_check:
                raise HTTPException(400, "使用 Claude API 需要先輸入 API key")
            check_claude_key(key_to_check, model)
        prefs.update(provider=req.provider, model=model)
        if key:
            prefs["api_key"] = key
        else:
            prefs.pop("api_key", None)
        localstore.save_prefs(prefs)
        return llm_get()

    @app.get("/api/inbox")
    def inbox(pic: str):
        if pic not in ws.settings["pics"]:
            raise HTTPException(404, "沒有這位承辦")
        return [asdict(i) for i in pipeline.scan_inbox(ws, pic)]

    @app.post("/api/jobs")
    def start(req: RunRequest):
        job = state["job"]
        if job and job.running:
            raise HTTPException(409, "已有批次在執行")
        valid = {i.base for i in pipeline.scan_inbox(ws, req.pic) if not i.problem}
        bad = [b for b in req.bases if b not in valid]
        if bad or not req.bases:
            raise HTTPException(400, f"無法處理：{bad or '未勾選檔案'}")
        e = localstore.effective(ws.settings)
        if e["provider"] == "claude" and not e["api_key"]:
            raise HTTPException(400, "尚未設定 Claude API key，請到「模型設定」輸入")
        job = state["job"] = Job(req.pic, req.bases)
        threading.Thread(target=run_job, args=(job,), daemon=True).start()
        return {"ok": True}

    @app.get("/api/jobs/current")
    def current(since: int = 0):
        job = state["job"]
        if not job:
            return {"running": False, "items": [], "log": [], "next": 0}
        return {"running": job.running, "pic": job.pic, "items": job.items, "log": job.log[since:],
                "next": len(job.log)}

    @app.post("/api/jobs/stop")
    def stop():
        if state["job"]:
            state["job"].stop = True
        return {"ok": True}

    @app.post("/api/jobs/skip")
    def skip():
        if state["job"]:
            state["job"].skip = True
        return {"ok": True}

    @app.get("/api/cases")
    def cases(pic: str | None = None, status: str | None = None):
        return db.list(pic, status)

    def get_case(case_id: str) -> dict:
        c = db.get(case_id)
        if not c:
            raise HTTPException(404, "找不到案件")
        return c

    @app.get("/api/cases/{case_id}")
    def case(case_id: str):
        return get_case(case_id)

    @app.patch("/api/cases/{case_id}")
    def update(case_id: str, req: StatusRequest):
        try:
            db.set_status(case_id, req.status, req.note)
        except ValueError as e:
            raise HTTPException(400, str(e))
        return get_case(case_id)

    def case_file(case_id: str, rel: str) -> Path:
        folder = Path(get_case(case_id)["folder"]).resolve()
        p = (folder / rel).resolve()
        if folder not in p.parents or not p.is_file():
            raise HTTPException(404, "找不到檔案")
        return p

    @app.get("/api/cases/{case_id}/page")
    def page(case_id: str, file: str, n: int, q: str | None = None):
        c = get_case(case_id)
        rel = (c["detail"] or {}).get("originals", {}).get(file)
        if not rel:
            raise HTTPException(404, "找不到原始檔")
        doc = pymupdf.open(case_file(case_id, rel))
        if not 1 <= n <= len(doc):
            raise HTTPException(404, "頁碼超出範圍")
        pg = doc[n - 1]
        if q and (needle := N.squash(q)):
            # search_for 在部分中文字型上字元座標會偏移，先用整個 word 的外框比對
            hits = [pymupdf.Rect(w[:4]) for w in pg.get_text("words") if needle in N.squash(w[4])]
            for rect in (hits or pg.search_for(q.strip()))[:5]:
                pg.add_highlight_annot(rect)
        return Response(pg.get_pixmap(dpi=110).tobytes("png"), media_type="image/png")

    @app.get("/api/cases/{case_id}/files/{rel:path}")
    def download(case_id: str, rel: str):
        p = case_file(case_id, rel)
        return FileResponse(p, filename=p.name)

    @app.get("/api/cases/{case_id}/listing")
    def listing(case_id: str):
        folder = Path(get_case(case_id)["folder"])
        return sorted(str(p.relative_to(folder)) for p in folder.rglob("*") if p.is_file() and p.name != "case.json")

    @app.get("/api/health")
    def health():
        checks = []

        def add(name, ok, detail):
            checks.append({"name": name, "ok": ok, "detail": detail})

        e = localstore.effective(ws.settings)
        if e["provider"] == "claude":
            add("Claude API key", bool(e["api_key"]),
                f"{e['model']}（{e['key_source']}）" if e["api_key"] else "尚未設定，請到「模型設定」輸入")
        else:
            o = ws.settings["llm"].get("ollama", {})
            try:
                tags = httpx.get(f"{o['base_url']}/api/tags", timeout=3).json()
                names = [m["name"] for m in tags.get("models", [])]
                add("Ollama 連線", True, o["base_url"])
                add("模型已下載", o["model"] in names, o["model"] if o["model"] in names else f"缺 {o['model']}，請執行 ollama pull {o['model']}")
            except Exception as ex:
                add("Ollama 連線", False, f"{o.get('base_url')} 連不上：{ex.__class__.__name__}")
        if ws.settings["mail"]["mode"] == "mailpit":
            m = ws.settings["mail"]["mailpit"]
            try:
                import socket
                socket.create_connection((m["host"], m["port"]), timeout=2).close()
                add("模擬信箱 Mailpit", True, f"{m['host']}:{m['port']}")
            except OSError:
                add("模擬信箱 Mailpit", False, f"{m['host']}:{m['port']} 連不上，信件只會存成草稿")
        for key in ("vendor_master", "mail_routing", "form_template"):
            p = ws.config_dir / ws.settings["files"][key]
            add(f"設定檔 {p.name}", p.exists(), "存在" if p.exists() else "找不到")
        for key in ("sap_po", "sap_gr", "ap_paid", "employees"):
            try:
                add(f"系統匯出 {ws.settings['files'][key]}", True, ws.export(key).name)
            except FileNotFoundError as e:
                add(f"系統匯出 {ws.settings['files'][key]}", False, str(e))
        try:
            from . import reference
            ref = reference.load(ws)
            lint = routing.lint(routing.load(ws.config_dir / ws.settings["files"]["mail_routing"]), ref,
                                set(ws.rules["rules"]))
            errors = sum(i["level"] == "error" for i in lint)
            add("寄信對照表", errors == 0, f"{errors} 個錯誤、{len(lint) - errors} 個提醒（見對照表健檢）")
        except Exception as e:
            add("參考資料讀取", False, str(e))
        add("本機案件資料庫", True, "Docker volume" if HOST_WORKSPACE else _short(local_db_path(ws)))
        return checks

    @app.get("/api/routing/lint")
    def lint():
        from . import reference
        rules = routing.load(ws.config_dir / ws.settings["files"]["mail_routing"])
        return {"rules": [asdict(r) for r in rules],
                "issues": routing.lint(rules, reference.load(ws), set(ws.rules["rules"]))}

    @app.post("/api/open")
    def open_folder(req: OpenRequest):
        if HOST_WORKSPACE:
            raise HTTPException(400, f"Docker 模式無法直接開資料夾，請到主機的 {HOST_WORKSPACE} 查看")
        if req.target.startswith("case:"):
            target = Path(get_case(req.target[5:])["folder"])
        elif req.target in ("inbox", "forms", "done", "manual", "logs"):
            target = ws.folder(req.target)
        else:
            raise HTTPException(400, "未知的資料夾")
        if sys.platform == "win32":
            os.startfile(target)
        else:
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(target)])
        return {"ok": True}

    if WEB.exists():
        app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
    return app
