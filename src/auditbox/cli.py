import argparse
import webbrowser
from pathlib import Path

from . import config, localstore, pipeline, reference, routing
from .db import DB
from .llm import from_settings
from .server import create_app, local_db_path


def main():
    ap = argparse.ArgumentParser(prog="auditbox", description="模具請款稽核")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve", help="啟動本機介面")
    s.add_argument("workspace", type=Path)
    s.add_argument("--port", type=int, default=8765)
    s.add_argument("--host", default="127.0.0.1", help="Docker 內用 0.0.0.0；對外只透過 port 對應到主機的 127.0.0.1")
    s.add_argument("--no-browser", action="store_true")
    r = sub.add_parser("run", help="不開介面，直接處理某位承辦的全部檔案")
    r.add_argument("workspace", type=Path)
    r.add_argument("--pic", required=True)
    l = sub.add_parser("lint", help="檢查寄信對照表")
    l.add_argument("workspace", type=Path)
    args = ap.parse_args()

    ws = config.load(args.workspace.resolve())
    if args.cmd == "serve":
        import uvicorn
        url = f"http://localhost:{args.port}"
        if not args.no_browser:
            webbrowser.open(url)
        uvicorn.run(create_app(ws.root), host=args.host, port=args.port, log_level="warning")
    elif args.cmd == "run":
        e = localstore.effective(ws.settings)
        llm = from_settings(ws.settings, e["provider"], e["model"], e["api_key"])
        pipe = pipeline.Pipeline(ws, DB(local_db_path(ws)), pipeline.llm_extractor(ws, llm), llm)
        for item in pipeline.scan_inbox(ws, args.pic):
            if item.problem:
                print(f"略過 {item.base}：{item.problem}")
                continue
            print(f"▶ {item.base}")
            pipe.process(args.pic, item.base)
    else:
        issues = routing.lint(routing.load(ws.config_dir / ws.settings["files"]["mail_routing"]),
                              reference.load(ws), set(ws.rules["rules"]))
        for i in issues:
            print(f"[{i['level']}] 第 {i['row']} 列 {i['rule_id']}：{i['message']}")
        print(f"共 {len(issues)} 項")
