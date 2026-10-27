"""List the models this Token Factory key can call and pick out the NVIDIA ones.

  .venv/bin/python scripts/tf_models.py      -> prints NVIDIA model ids, writes docs/token_factory_models.json
"""
import json, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env.local")
from openai import OpenAI
from agent.llm import TOKEN_FACTORY_URL

key = os.getenv("NEBIUS_API_KEY") or sys.exit("No NEBIUS_API_KEY in .env.local")
c = OpenAI(base_url=os.getenv("LLM_BASE_URL") or TOKEN_FACTORY_URL, api_key=key)
ids = sorted(m.id for m in c.models.list().data)
nv = [i for i in ids if "nvidia" in i.lower() or "nemotron" in i.lower()]
(ROOT / "docs/token_factory_models.json").write_text(json.dumps({"all": ids, "nvidia": nv}, indent=1))
print(f"{len(ids)} models; NVIDIA / Nemotron ({len(nv)}):")
for i in nv:
    print("  ", i)
