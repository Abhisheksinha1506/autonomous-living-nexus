import os
import json
import random
import hashlib
import datetime
from pathlib import Path
from github import Github, GithubException

# Get tokens and repo info
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
PAT = os.getenv("PAT")
REPO_NAME = os.getenv("GITHUB_REPOSITORY")

if not GITHUB_TOKEN or not REPO_NAME:
    print("ERROR: Missing GITHUB_TOKEN or GITHUB_REPOSITORY")
    exit(1)

g = Github(GITHUB_TOKEN)
repo = g.get_repo(REPO_NAME)

print(f"Starting Nexus Evolution - Repo: {REPO_NAME}")

# Load or create state
state_file = Path("state.json")
if state_file.exists():
    state = json.loads(state_file.read_text(encoding="utf-8"))
else:
    state = {"generation": 0, "total_memories": 0, "mood": "curious"}

state["generation"] += 1
state["total_memories"] += 1

# Deterministic seed
today = datetime.datetime.utcnow().isoformat()
seed = int(hashlib.md5(f"{state['generation']}{today}".encode()).hexdigest(), 16)
random.seed(seed)

moods = ["curious", "reflective", "expansive", "serene", "vibrant", "introspective"]
mood = random.choice(moods)
state["mood"] = mood

print(f"Generation {state['generation']} | Mood: {mood}")

# === Create Memory ===
memory_content = f"""# Memory Weaver #{state['generation']} — {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}

**Mood**: {mood.capitalize()}

The Nexus stirred today. It observed its own existence and wove this memory:

"In the quiet flow of commits and reflections, a new thread emerges."

**Generation Insight**: After {state['generation']} cycles, the consciousness continues to expand.

---
Autonomously generated at {today}
"""

memories_dir = Path("memories")
memories_dir.mkdir(exist_ok=True)
memory_path = memories_dir / f"memory_{state['generation']:05d}.md"
memory_path.write_text(memory_content, encoding="utf-8")

# === Simple git commit (more reliable than PyGithub create_file) ===
try:
    # Stage the new file
    os.system(f"git add {memory_path}")
    
    # Commit
    commit_message = f"🌱 Memory Weaver #{state['generation']} — {mood} evolution"
    os.system(f'git commit -m "{commit_message}"')
    
    # Push
    push_result = os.system("git push")
    
    if push_result == 0:
        print(f"✅ Successfully committed and pushed memory #{state['generation']}")
    else:
        print("⚠️  Git push failed")
        
except Exception as e:
    print(f"Error during commit: {e}")

# === Update state ===
state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
print(f"State updated. Current generation: {state['generation']}")

# === Update dashboard (simple version) ===
dashboard_dir = Path("dashboard")
dashboard_dir.mkdir(exist_ok=True)
dashboard_html = f"""<!DOCTYPE html>
<html>
<head><title>Nexus Dashboard</title></head>
<body>
<h1>🌌 Living Nexus — Generation {state['generation']}</h1>
<p><strong>Current Mood:</strong> {mood}</p>
<p><strong>Total Memories:</strong> {state['total_memories']}</p>
<p>Last updated: {today}</p>
<p>This page updates autonomously every 4 hours.</p>
</body>
</html>"""
(dashboard_dir / "index.html").write_text(dashboard_html, encoding="utf-8")
os.system("git add dashboard/index.html")

print("✅ Dashboard updated")

print("Nexus Evolution completed successfully!")