"""First call to Token Factory: does the chosen Nemotron answer, how fast, does it wrap the answer in <think>,
and does it return clean JSON for the intake prompt? Run before measuring.

  .venv/bin/python scripts/tf_smoke.py                       # LLM_MODEL from .env.local
  .venv/bin/python scripts/tf_smoke.py nvidia/<model id>     # another one
"""
import json, os, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env.local")
if len(sys.argv) > 1:
    os.environ["LLM_MODEL"] = os.environ["LLM_MODEL_INTAKE"] = os.environ["LLM_MODEL_EXPLAIN"] = sys.argv[1]
from agent.llm import token_factory_client, model_for, CallLog
from agent.intake import read_message

log = CallLog()
c, prov = token_factory_client(log)
if c is None:
    sys.exit(f"No client: {prov}")
m = model_for("intake")
t = time.time()
r = c.chat.completions.create(_role="hello", model=m, temperature=0, max_tokens=50,
                              messages=[{"role": "user", "content": "Reply with exactly: hello from Token Factory"}])
print("hello:", repr(r.choices[0].message.content[:120]), f"{int((time.time()-t)*1000)} ms", "model:", r.model)
res = read_message(c, "My wife's email is k.smith@example.org but I paid 24,900 won with liam.patel906@example.com yesterday and nothing came.")
print("intake ok:", res.get("ok"), res.get("error", ""))
if res.get("ok"):
    print(json.dumps(res["grounded"], ensure_ascii=False, indent=1)[:1500])
for x in log:
    print(x)
