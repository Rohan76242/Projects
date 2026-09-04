import base64, json, urllib.request, time

img = base64.b64encode(open('test_screen_small.png', 'rb').read()).decode()

p = {
    'model': 'qwen3-vl:2b',
    'prompt': 'Describe this screenshot in one short sentence.',
    'images': [img],
    'stream': False,
    'options': {
        'num_predict': 150,
        'num_ctx': 2048
    }
}

d = json.dumps(p).encode()
r = urllib.request.Request(
    'http://127.0.0.1:11434/api/generate',
    data=d,
    headers={'Content-Type': 'application/json'},
    method='POST'
)

t = time.perf_counter()
x = json.loads(urllib.request.urlopen(r, timeout=30).read().decode())
print('TIME:', round(time.perf_counter() - t, 2), 'sec')
print('RESPONSE:', x.get('response'))
print('EVAL_COUNT:', x.get('eval_count'))