#!/usr/bin/env python3
"""Drive the MCP server over stdio, call the READ tools and report what works.
Write tools (publish/send_dm/comment/delete/hide) are NOT executed: irreversible
and public on the real account. They are listed as available capabilities.
"""
import json, subprocess, os, sys, time, select

HERE = os.path.dirname(os.path.abspath(__file__))
proc = subprocess.Popen(
    [os.path.join(HERE, "run.sh")],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    text=True, bufsize=1,
)

_id = 0
def send(method, params=None, notify=False):
    global _id
    msg = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        msg["params"] = params
    if not notify:
        _id += 1
        msg["id"] = _id
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()
    return None if notify else _id

def read_until(want_id, timeout=25):
    end = time.time() + timeout
    while time.time() < end:
        r, _, _ = select.select([proc.stdout], [], [], end - time.time())
        if not r:
            break
        line = proc.stdout.readline()
        if not line:
            break
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("id") == want_id:
            return d
    return None

def call(name, args=None):
    i = send("tools/call", {"name": name, "arguments": args or {}})
    resp = read_until(i)
    if resp is None:
        return False, "NO RESPONSE (timeout)", None
    if "error" in resp:
        return False, resp["error"].get("message", str(resp["error"])), None
    res = resp.get("result", {})
    is_err = res.get("isError", False)
    txt = ""
    for c in res.get("content", []):
        if c.get("type") == "text":
            txt += c.get("text", "")
    # try to parse embedded json
    payload = None
    try:
        payload = json.loads(txt)
    except Exception:
        payload = txt
    return (not is_err), txt, payload

# handshake
send("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "tester", "version": "1"}})
read_until(_id)
send("notifications/initialized", notify=True)

results = []
def rec(name, ok, detail):
    results.append((name, ok, detail))
    mark = "OK " if ok else "FAIL"
    print(f"[{mark}] {name}: {detail[:180]}")

def data_list(payload):
    """Extract the item list from varied shapes: [...], {data:[...]},
    {data:{posts|stories|pages|messages|comments|insights|data:[...]}}."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        d = payload.get("data")
        if isinstance(d, list):
            return d
        if isinstance(d, dict):
            for v in d.values():
                if isinstance(v, list):
                    return v
    return None

def extract_id(payload):
    lst = data_list(payload)
    if lst and isinstance(lst[0], dict) and lst[0].get("id"):
        return lst[0]["id"]
    if isinstance(payload, dict):
        d = payload.get("data")
        if isinstance(d, dict) and d.get("id"):
            return d["id"]
        if payload.get("id"):
            return payload["id"]
    return None

def summarize(payload, keys):
    lst = data_list(payload)
    if lst is not None:
        return f"{len(lst)} items"
    if isinstance(payload, dict):
        flat = ", ".join(f"{k}={payload[k]}" for k in keys if k in payload)
        return flat or ("raw: " + json.dumps(payload)[:160])
    return str(payload)[:160]

def first_id(payload):
    lst = data_list(payload)
    if lst and isinstance(lst[0], dict):
        return lst[0].get("id")
    return None

print("=== READ (executed live) ===")

ok, txt, p = call("validate_access_token")
rec("validate_access_token", ok, txt[:200])

ok, txt, p = call("get_profile_info")
rec("get_profile_info", ok, txt[:200])

ok, txt, p = call("get_account_pages")
rec("get_account_pages", ok, txt[:200])

# media posts -> grab one media_id
ok, txt, p = call("get_media_posts", {"limit": 5})
media_id = extract_id(p)
rec("get_media_posts", ok, f"first id={media_id} | " + summarize(p, []))

if media_id:
    ok, txt, p = call("get_media_insights", {"media_id": media_id})
    rec("get_media_insights", ok, summarize(p, []) if ok else txt[:160])
    ok, txt, p = call("get_comments", {"media_id": media_id, "limit": 5})
    rec("get_comments", ok, summarize(p, []) if ok else txt[:160])
else:
    rec("get_media_insights", False, "no media_id (no posts) -> skipped")
    rec("get_comments", False, "no media_id -> skipped")

ok, txt, p = call("get_account_insights", {"period": "day"})
rec("get_account_insights", ok, summarize(p, []) if ok else txt[:160])

ok, txt, p = call("get_content_publishing_limit")
rec("get_content_publishing_limit", ok, summarize(p, ["quota_usage","config"]) if ok else txt[:160])

ok, txt, p = call("get_stories")
rec("get_stories", ok, summarize(p, []) if ok else txt[:160])

ok, txt, p = call("get_mentions", {"limit": 5})
rec("get_mentions", ok, summarize(p, []) if ok else txt[:160])

# conversations
ok, txt, p = call("get_conversations", {"limit": 5})
conv_id = extract_id(p)
rec("get_conversations", ok, summarize(p, []) if ok else txt[:160])
if conv_id:
    ok, txt, p = call("get_conversation_messages", {"conversation_id": conv_id, "limit": 5})
    rec("get_conversation_messages", ok, summarize(p, []) if ok else txt[:160])
else:
    rec("get_conversation_messages", False, "no conversation -> skipped")

# hashtag search -> id -> media
ok, txt, p = call("search_hashtag", {"hashtag_name": "odontologia"})
hid = extract_id(p)
rec("search_hashtag", ok, f"hashtag_id={hid}" if hid else (summarize(p, []) if ok else txt[:160]))
if hid:
    ok, txt, p = call("get_hashtag_media", {"hashtag_id": hid, "limit": 5})
    rec("get_hashtag_media", ok, summarize(p, []) if ok else txt[:160])
else:
    rec("get_hashtag_media", False, "no hashtag_id -> skipped")

# business discovery of a known public account
ok, txt, p = call("business_discovery", {"target_username": "natgeo"})
rec("business_discovery", ok, (summarize(p,[])+" | "+txt[:120]))

print("\n=== WRITE (NOT executed - irreversible/public) ===")
for w in ["publish_media", "publish_carousel", "publish_reel", "send_dm",
          "post_comment", "reply_to_comment", "delete_comment", "hide_comment"]:
    print(f"[SKIP] {w}: capability present, not executed")

proc.stdin.close()
try:
    proc.wait(timeout=3)
except Exception:
    proc.kill()

okc = sum(1 for _, o, _ in results if o)
print(f"\n=== READ SUMMARY: {okc}/{len(results)} OK ===")
