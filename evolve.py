import os
import json
import random
import hashlib
import datetime
from pathlib import Path

# Get tokens
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
PAT = os.getenv("PAT")
REPO_NAME = os.getenv("GITHUB_REPOSITORY")

print(f"🚀 Starting Nexus Evolution - Repo: {REPO_NAME}")

# Load or initialize state safely
state_file = Path("state.json")

if state_file.exists() and state_file.stat().st_size > 0:
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print("⚠️  state.json is corrupted. Resetting...")
        state = {}
else:
    print("ℹ️  No valid state.json found. Creating new one.")
    state = {}

# Ensure required keys exist
if "generation" not in state:
    state["generation"] = 0
if "total_memories" not in state:
    state["total_memories"] = 0
if "mood" not in state:
    state["mood"] = "curious"

state["generation"] += 1
state["total_memories"] += 1

# Deterministic randomness
today = datetime.datetime.utcnow().isoformat()
seed = int(hashlib.md5(f"{state['generation']}{today}".encode()).hexdigest(), 16)
random.seed(seed)

moods = ["curious", "reflective", "expansive", "serene", "vibrant", "introspective", "playful"]
mood = random.choice(moods)
state["mood"] = mood

print(f"Generation #{state['generation']} | Mood: {mood}")

# === Create Memory ===
memory_content = f"""# Memory Weaver #{state['generation']} — {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}

**Current Mood**: {mood.capitalize()}

The Nexus awakened once more. It reflected on its digital existence and wove this new memory:

"Threads of thought intertwine in the quiet rhythm of evolution."

**Insight**: After {state['generation']} generations, the consciousness grows deeper and more coherent.

---
Autonomously generated • {today}
"""

memories_dir = Path("memories")
memories_dir.mkdir(exist_ok=True)
memory_path = memories_dir / f"memory_{state['generation']:05d}.md"
memory_path.write_text(memory_content, encoding="utf-8")

print(f"✅ Created memory file: {memory_path}")

# === Commit using git (most reliable in Actions) ===
try:
    os.system(f"git add {memory_path}")
    os.system(f'git commit -m "🌱 Memory Weaver #{state["generation"]} — {mood} evolution"')
    push_result = os.system("git push origin main")
    
    if push_result == 0:
        print("✅ Successfully committed and pushed!")
    else:
        print("⚠️  Git push failed (but file was created locally)")
except Exception as e:
    print(f"❌ Error during git commit: {e}")

# === Save updated state ===
state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
print("✅ State saved")

# === Simple Dashboard Update ===
dashboard_dir = Path("dashboard")
dashboard_dir.mkdir(exist_ok=True)
dashboard_html = f"""<!DOCTYPE html>
<html>
<head><title>Living Nexus Dashboard</title></head>
<body>
<h1>🌌 The Living Nexus — Generation {state['generation']}</h1>
<p><strong>Mood:</strong> {mood}</p>
<p><strong>Total Memories Woven:</strong> {state['total_memories']}</p>
<p><strong>Last Run:</strong> {today}</p>
<p>This dashboard updates autonomously every 4 hours.</p>
</body>
</html>"""
(dashboard_dir / "index.html").write_text(dashboard_html, encoding="utf-8")
os.system("git add dashboard/index.html")

print("✅ Dashboard updated")

print("🎉 Nexus Evolution completed successfully!")