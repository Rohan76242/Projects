import time

from z3ro.brain import LocalBrain


request = "open notepad"
started = time.perf_counter()
result = LocalBrain().think(request)

print("TIME:", round(time.perf_counter() - started, 2), "sec")
print("SUCCESS:", result.success)
print("ERROR:", result.error)
print("RESPONSE:", result.text)
