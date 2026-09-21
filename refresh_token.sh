#!/usr/bin/env bash
# Refresh the Meta long-lived access token (extends +60 days) and update .env.
# Usage: ./refresh_token.sh   (runs from any cwd)
# Does not print the token. Backs up .env to .env.bak before touching it.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f .env ]; then echo "ERROR: .env not found in $(pwd)" >&2; exit 1; fi
set -a; . ./.env; set +a

: "${FACEBOOK_APP_ID:?FACEBOOK_APP_ID missing in .env}"
: "${FACEBOOK_APP_SECRET:?FACEBOOK_APP_SECRET missing in .env}"
: "${INSTAGRAM_ACCESS_TOKEN:?INSTAGRAM_ACCESS_TOKEN missing in .env}"
API="${INSTAGRAM_API_VERSION:-v19.0}"

echo "Exchanging current token for a new long-lived one..."
resp="$(curl -s "https://graph.facebook.com/${API}/oauth/access_token" \
  --get \
  --data-urlencode "grant_type=fb_exchange_token" \
  --data-urlencode "client_id=${FACEBOOK_APP_ID}" \
  --data-urlencode "client_secret=${FACEBOOK_APP_SECRET}" \
  --data-urlencode "fb_exchange_token=${INSTAGRAM_ACCESS_TOKEN}")"

new_token="$(printf '%s' "$resp" | python3 -c "import sys,json
d=json.load(sys.stdin)
if 'access_token' not in d:
    sys.exit('Meta ERROR: '+json.dumps(d.get('error',d)))
print(d['access_token'])")"

# backup and safe replacement (| delimiter avoids collision with / in the token)
cp .env .env.bak
python3 - "$new_token" <<'PY'
import sys,re,io
tok=sys.argv[1]
p='.env'
lines=open(p,encoding='utf-8').read().splitlines()
out=[]; done=False
for l in lines:
    if l.startswith('INSTAGRAM_ACCESS_TOKEN='):
        out.append('INSTAGRAM_ACCESS_TOKEN='+tok); done=True
    else:
        out.append(l)
if not done: out.append('INSTAGRAM_ACCESS_TOKEN='+tok)
open(p,'w',encoding='utf-8').write('\n'.join(out)+'\n')
PY

# validate and show the new expiration (without printing the token)
info="$(curl -s "https://graph.facebook.com/${API}/debug_token?input_token=${new_token}&access_token=${new_token}")"
printf '%s' "$info" | python3 -c "import sys,json,datetime
d=json.load(sys.stdin).get('data',{})
ea=d.get('expires_at',0)
if ea==0: print('OK. New token valid. Expires: NEVER')
else:
    dt=datetime.datetime.fromtimestamp(ea,datetime.timezone.utc)
    print('OK. New token valid. Expires at', dt.isoformat())
print('Backup of previous .env: .env.bak')
print('Restart Claude Code (or /mcp) so the server picks up the new token.')"
