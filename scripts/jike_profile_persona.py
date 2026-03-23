#!/usr/bin/env python3

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple


API_HOST = "https://api.ruguoapp.com"
SCAN_WEB_URL = "https://www.okjike.com/account/scan?uuid={uuid}"
QR_SERVICE = "https://quickchart.io/qr"
SKILL_DIR = Path(__file__).resolve().parent.parent
PROMPT_TEMPLATE_PATH = SKILL_DIR / "references" / "persona-prompt.md"
COMPATIBILITY_PROMPT_TEMPLATE_PATH = SKILL_DIR / "references" / "compatibility-prompt.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch up to 200 recent Jike profile posts and build a corpus plus analysis prompt package."
    )
    parser.add_argument("target", help="Jike profile URL or username/id")
    parser.add_argument("--limit", type=int, default=200, help="Maximum posts to fetch")
    parser.add_argument(
        "--out-dir",
        default=str(Path.cwd() / "jike-profile-output"),
        help="Output directory for JSON, corpus, analysis prompt pack, login QR, and cached session",
    )
    parser.add_argument(
        "--skip-analysis",
        action="store_true",
        help="Fetch posts and write corpus only; skip the prompt-pack file",
    )
    parser.add_argument(
        "--match-brief",
        default="",
        help="User-provided dating preferences or imagined ideal partner; used to build a compatibility prompt pack",
    )
    parser.add_argument(
        "--match-brief-file",
        default="",
        help="Path to a UTF-8 text/markdown file containing the user's dating preferences; appended to --match-brief if both are provided",
    )
    return parser.parse_args()


def resolve_username(target: str) -> str:
    if "/" not in target:
        return target
    parsed = urllib.parse.urlparse(target)
    if parsed.netloc == "web.okjike.com" and parsed.path.startswith("/u/"):
        return urllib.parse.unquote(parsed.path.split("/")[2])
    if parsed.path.startswith("/users/"):
        return urllib.parse.unquote(parsed.path.split("/")[2])
    raise ValueError(f"Unsupported Jike profile input: {target}")


def request_json(
    method: str,
    path: str,
    *,
    params: Optional[Dict] = None,
    payload: Optional[Dict] = None,
    headers: Optional[Dict] = None,
    timeout: int = 30,
) -> Tuple[int, Dict, Dict]:
    url = API_HOST + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = None
    request_headers = {"User-Agent": "Codex Jike Profile Persona"}
    if headers:
        request_headers.update(headers)
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            headers_dict = {str(k).lower(): v for k, v in dict(resp.headers).items()}
            return resp.status, headers_dict, json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        parsed = {}
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"raw": body}
        headers_dict = {str(k).lower(): v for k, v in dict(exc.headers).items()}
        return exc.code, headers_dict, parsed


def session_cache_path(out_dir: Path) -> Path:
    return out_dir / "jike-session.json"


def read_cached_session(out_dir: Path) -> Optional[Dict]:
    path = session_cache_path(out_dir)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def write_cached_session(out_dir: Path, tokens: dict) -> None:
    session_cache_path(out_dir).write_text(
        json.dumps(
            {
                "token": tokens["token"],
                "refreshToken": tokens["refreshToken"],
                "cachedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def refresh_tokens(refresh_token: str) -> dict:
    status, headers, body = request_json(
        "POST",
        "/app_auth_tokens.refresh",
        headers={"x-jike-refresh-token": refresh_token},
        payload={},
    )
    if status != 200:
        raise RuntimeError(f"Token refresh failed: HTTP {status} {headers.get('reason', '')}".strip())
    token = body.get("x-jike-access-token")
    refreshed = body.get("x-jike-refresh-token")
    if not token or not refreshed:
        raise RuntimeError("Token refresh response did not include both access and refresh tokens.")
    return {"token": token, "refreshToken": refreshed}


def create_login_session() -> str:
    status, _headers, body = request_json("GET", "/sessions.create")
    if status != 200 or not body.get("uuid"):
        raise RuntimeError(f"Failed to create login session: HTTP {status}")
    return body["uuid"]


def build_login_url(uuid: str) -> str:
    scan_url = SCAN_WEB_URL.format(uuid=uuid)
    encoded = urllib.parse.quote(scan_url, safe="")
    return f"jike://page.jk/web?url={encoded}&displayHeader=false&displayFooter=false"


def write_login_qr(out_dir: Path, uuid: str) -> Tuple[Optional[Path], Path]:
    login_url = build_login_url(uuid)
    url_file = out_dir / "jike-login-url.txt"
    url_file.write_text(login_url + "\n", encoding="utf-8")

    qr_path = out_dir / "jike-login-qr.png"
    qr_query = urllib.parse.urlencode({"text": login_url, "size": "360", "margin": "1"})
    qr_url = f"{QR_SERVICE}?{qr_query}"
    try:
        with urllib.request.urlopen(qr_url, timeout=30) as resp:
            qr_path.write_bytes(resp.read())
        return qr_path, url_file
    except Exception:
        return None, url_file


def wait_for_confirmation(uuid: str) -> dict:
    while True:
        status, headers, body = request_json(
            "GET",
            "/sessions.wait_for_confirmation",
            params={"uuid": uuid},
        )
        if status == 200 and body.get("confirmed"):
            refresh_token = body.get("x-jike-refresh-token")
            token = body.get("token")
            if not refresh_token or not token:
                raise RuntimeError("Confirmation succeeded but tokens were missing.")
            return {"token": token, "refreshToken": refresh_token}

        reason = headers.get("reason", "")
        if status == 400 and reason == "SESSION_IN_WRONG_STATUS":
            time.sleep(1)
            continue
        if status == 404 and reason == "SESSION_EXPIRED":
            raise RuntimeError("Login session expired before confirmation. Generate a fresh QR and rescan.")
        raise RuntimeError(f"Unexpected confirmation response: HTTP {status} {reason}".strip())


def ensure_tokens(out_dir: Path) -> dict:
    cached = read_cached_session(out_dir)
    if cached and cached.get("refreshToken"):
        try:
            tokens = refresh_tokens(cached["refreshToken"])
            write_cached_session(out_dir, tokens)
            return tokens
        except Exception:
            pass

    uuid = create_login_session()
    qr_path, url_file = write_login_qr(out_dir, uuid)
    print("Login required.", file=sys.stderr)
    if qr_path:
        print(f"Scan this QR with the Jike app: {qr_path}", file=sys.stderr)
    else:
        print("QR image generation failed; use the deep link text file instead.", file=sys.stderr)
    print(f"Login deep link: {url_file}", file=sys.stderr)
    print(f"Session UUID: {uuid}", file=sys.stderr)
    print("Waiting for scan confirmation...", file=sys.stderr)
    confirmed = wait_for_confirmation(uuid)
    tokens = refresh_tokens(confirmed["refreshToken"])
    write_cached_session(out_dir, tokens)
    return tokens


def auth_headers(token: str) -> dict:
    return {"x-jike-access-token": token}


def fetch_profile(token: str, username: str) -> Dict:
    status, _headers, body = request_json(
        "GET",
        "/1.0/users/profile",
        params={"username": username},
        headers=auth_headers(token),
    )
    if status != 200 or "user" not in body:
        raise RuntimeError(f"Failed to fetch profile: HTTP {status}")
    return body["user"]


def fetch_updates(token: str, username: str, limit: int) -> List[Dict]:
    updates: List[Dict] = []
    seen = set()
    load_more_key = None

    while len(updates) < limit:
        payload = {"username": username, "limit": min(20, limit - len(updates))}
        if load_more_key:
            payload["loadMoreKey"] = load_more_key
        status, _headers, body = request_json(
            "POST",
            "/1.0/personalUpdate/single",
            payload=payload,
            headers=auth_headers(token),
        )
        if status != 200:
            raise RuntimeError(f"Failed to fetch updates: HTTP {status}")

        page_items = body.get("data") or []
        for item in page_items:
            item_id = item.get("id")
            if not item_id or item_id in seen:
                continue
            seen.add(item_id)
            updates.append(item)
            if len(updates) >= limit:
                break

        load_more_key = body.get("loadMoreKey")
        if not page_items or not load_more_key:
            break

    return updates


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def clip(text: str, length: int = 120) -> str:
    normalized = normalize_whitespace(text)
    if len(normalized) <= length:
        return normalized
    return normalized[:length] + "..."


def extract_post_text(item: Dict) -> str:
    candidates = [
        item.get("content"),
        item.get("text"),
        item.get("message"),
    ]
    for value in candidates:
        text = normalize_whitespace(str(value or ""))
        if text:
            return text
    return ""


def build_observable_stats(updates: List[Dict]) -> Dict[str, object]:
    texts = [extract_post_text(item) for item in updates]
    non_empty = [text for text in texts if text]
    lengths = [len(text) for text in non_empty]

    question_like = sum(1 for text in non_empty if "?" in text or "？" in text)
    exclaim_like = sum(1 for text in non_empty if "!" in text or "！" in text)
    self_reference = sum(1 for text in non_empty if re.search(r"\bI\b|我|自己|本人", text, re.I))
    invitation_like = sum(1 for text in non_empty if re.search(r"欢迎|联系|合作|一起|交流|有兴趣", text, re.I))

    return {
        "nonEmptyCount": len(non_empty),
        "emptyCount": len(updates) - len(non_empty),
        "averageLength": round(sum(lengths) / len(lengths), 1) if lengths else 0,
        "longFormCount": sum(1 for length in lengths if length >= 120),
        "questionLikeCount": question_like,
        "exclaimLikeCount": exclaim_like,
        "selfReferenceCount": self_reference,
        "invitationLikeCount": invitation_like,
    }


def render_corpus_markdown(data: Dict) -> str:
    profile = data["profile"]
    updates = data["updates"]
    stats = build_observable_stats(updates)

    lines = [
        "# 即刻动态语料包",
        "",
        "## 基本信息",
        "",
        f"- 用户名：{data['username']}",
        f"- 显示名：{profile.get('screenName') or data['username']}",
        f"- 个性签名：{normalize_whitespace(str(profile.get('bio') or '')) or '无'}",
        f"- 样本数：{data['actualCount']}",
        f"- 请求上限：{data['requestedLimit']}",
        f"- 抓取时间：{data['fetchedAt']}",
        "",
        "## 可观察统计",
        "",
        f"- 有正文的动态：{stats['nonEmptyCount']}",
        f"- 无正文或仅媒体线索的动态：{stats['emptyCount']}",
        f"- 平均正文长度：{stats['averageLength']} 字符",
        f"- 长文本动态（>=120 字符）：{stats['longFormCount']}",
        f"- 带提问语气的动态：{stats['questionLikeCount']}",
        f"- 带明显感叹语气的动态：{stats['exclaimLikeCount']}",
        f"- 出现自我指涉的动态：{stats['selfReferenceCount']}",
        f"- 出现邀请/合作信号的动态：{stats['invitationLikeCount']}",
        "",
        "## 使用提醒",
        "",
        "- 下面是原始语料，不是结论。",
        "- 如果样本数小于请求上限，说明这个账号当前可抓到的主页动态就这么多，或者更多内容不在主页流里。",
        "- 空文本动态可能是图片、转发或网页端字段不完整，分析时不要过度解读缺失部分。",
        "",
        "## 动态列表",
        "",
    ]

    for index, item in enumerate(updates, start=1):
        text = extract_post_text(item)
        created_at = item.get("createdAt") or "unknown"
        lines.append(f"### {index:03d} | {created_at}")
        lines.append("")
        if text:
            lines.append(text)
        else:
            lines.append("[无可见正文]")

        link_info = normalize_whitespace(str(item.get("linkInfo") or ""))
        if link_info:
            lines.append("")
            lines.append(f"附加线索：{clip(link_info, 180)}")

        lines.append("")

    return "\n".join(lines).strip() + "\n"


def load_template(path: Path) -> str:
    if not path.exists():
        raise RuntimeError(f"Prompt template not found: {path}")
    return path.read_text(encoding="utf-8")


def read_match_brief(args: argparse.Namespace) -> str:
    parts: List[str] = []
    inline = normalize_whitespace(args.match_brief)
    if inline:
        parts.append(inline)

    if args.match_brief_file:
        brief_path = Path(args.match_brief_file).expanduser().resolve()
        parts.append(normalize_whitespace(brief_path.read_text(encoding="utf-8")))

    return "\n\n".join(part for part in parts if part)


def render_analysis_input(data: Dict, corpus_markdown: str) -> str:
    profile = data["profile"]
    template = load_template(PROMPT_TEMPLATE_PATH)
    replacements = {
        "{{screen_name}}": normalize_whitespace(str(profile.get("screenName") or data["username"])),
        "{{username}}": data["username"],
        "{{bio}}": normalize_whitespace(str(profile.get("bio") or "")) or "无",
        "{{sample_count}}": str(data["actualCount"]),
        "{{requested_limit}}": str(data["requestedLimit"]),
        "{{fetched_at}}": data["fetchedAt"],
        "{{corpus}}": corpus_markdown.strip(),
    }

    rendered = template
    for needle, value in replacements.items():
        rendered = rendered.replace(needle, value)
    return rendered.strip() + "\n"


def render_match_analysis_input(data: Dict, corpus_markdown: str, match_brief: str) -> str:
    profile = data["profile"]
    template = load_template(COMPATIBILITY_PROMPT_TEMPLATE_PATH)
    replacements = {
        "{{screen_name}}": normalize_whitespace(str(profile.get("screenName") or data["username"])),
        "{{username}}": data["username"],
        "{{bio}}": normalize_whitespace(str(profile.get("bio") or "")) or "无",
        "{{sample_count}}": str(data["actualCount"]),
        "{{requested_limit}}": str(data["requestedLimit"]),
        "{{fetched_at}}": data["fetchedAt"],
        "{{match_brief}}": match_brief.strip(),
        "{{corpus}}": corpus_markdown.strip(),
    }

    rendered = template
    for needle, value in replacements.items():
        rendered = rendered.replace(needle, value)
    return rendered.strip() + "\n"


def write_outputs(
    out_dir: Path,
    username: str,
    payload: Dict,
    corpus_markdown: str,
    analysis_input: Optional[str],
    match_analysis_input: Optional[str],
) -> Tuple[Path, Path, Optional[Path], Optional[Path]]:
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", username)
    json_path = out_dir / f"{safe_name}.updates.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    corpus_path = out_dir / f"{safe_name}.updates.corpus.md"
    corpus_path.write_text(corpus_markdown, encoding="utf-8")

    analysis_input_path = None
    if analysis_input is not None:
        analysis_input_path = out_dir / f"{safe_name}.analysis-input.md"
        analysis_input_path.write_text(analysis_input, encoding="utf-8")

    match_analysis_input_path = None
    if match_analysis_input is not None:
        match_analysis_input_path = out_dir / f"{safe_name}.match-analysis-input.md"
        match_analysis_input_path.write_text(match_analysis_input, encoding="utf-8")

    return json_path, corpus_path, analysis_input_path, match_analysis_input_path


def main() -> int:
    args = parse_args()
    username = resolve_username(args.target)
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    tokens = ensure_tokens(out_dir)
    profile = fetch_profile(tokens["token"], username)
    updates = fetch_updates(tokens["token"], username, args.limit)

    payload = {
        "fetchedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "username": username,
        "requestedLimit": args.limit,
        "actualCount": len(updates),
        "profile": profile,
        "updates": updates,
    }
    corpus_markdown = render_corpus_markdown(payload)
    match_brief = read_match_brief(args)
    analysis_input = None if args.skip_analysis else render_analysis_input(payload, corpus_markdown)
    match_analysis_input = None
    if not args.skip_analysis and match_brief:
        match_analysis_input = render_match_analysis_input(payload, corpus_markdown, match_brief)
    json_path, corpus_path, analysis_input_path, match_analysis_input_path = write_outputs(
        out_dir,
        username,
        payload,
        corpus_markdown,
        analysis_input,
        match_analysis_input,
    )

    print(
        json.dumps(
            {
                "username": username,
                "screenName": profile.get("screenName"),
                "count": len(updates),
                "jsonPath": str(json_path),
                "corpusPath": str(corpus_path),
                "analysisInputPath": str(analysis_input_path) if analysis_input_path else None,
                "matchAnalysisInputPath": str(match_analysis_input_path) if match_analysis_input_path else None,
                "promptTemplatePath": str(PROMPT_TEMPLATE_PATH),
                "compatibilityPromptTemplatePath": str(COMPATIBILITY_PROMPT_TEMPLATE_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Jike profile fetch failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
