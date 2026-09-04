import json, urllib.request, time

payload = {
    'model': 'qwen3:1.7b',
    'system': 'You are a helpful assistant. Return only valid JSON with an "actions" list.',
    'prompt': 'open notepad',
    'stream': False,
    'options': {
        'num_predict': 700,
        'num_ctx': 2048
    }
}

data = json.dumps(payload).encode('utf-8')
r = urllib.request.Request(
    'http://127.0.0.1:11434/api/generate',
    data=data,
    headers={'Content-Type': 'application/json'},
    method='POST'
)

t = time.perf_counter()
x = json.loads(urllib.request.urlopen(r, timeout=60).read().decode())
print('TIME:', round(time.perf_counter() - t, 2), 'sec')
print('THINKING_LEN:', len(x.get('thinking', '')))
print('RESPONSE:', x.get('response'))
print('EVAL_COUNT:', x.get('eval_count'))
print('LOAD_DURATION_MS:', x.get('load_duration', 0) / 1e6)