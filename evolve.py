"""
The Autonomous Living Nexus — evolve.py
Runs every 4 hours via GitHub Actions.

Schedule of activities
──────────────────────
Every run  (4 h)  : memory file, oracle entry, dashboard, state, mood history
Every 3rd  (12 h) : reflection issue (deduplicated, varied questions)
Every 6th  (24 h) : Major Evolution PR, wiki update, discussion post,
                    traffic insights woven into memory
"""

import os
import json
import random
import hashlib
import datetime
import subprocess
from pathlib import Path

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    from github import Github
    PYGITHUB_AVAILABLE = True
except ImportError:
    PYGITHUB_AVAILABLE = False

# ── Config ────────────────────────────────────────────────────────────────────
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
PAT          = os.getenv("PAT")           # secret is named PAT
REPO_NAME    = os.getenv("GITHUB_REPOSITORY")
TOKEN        = PAT or GITHUB_TOKEN

REPO_OWNER = REPO_NAME.split("/")[0] if REPO_NAME else ""
REPO_SHORT = REPO_NAME.split("/")[1] if REPO_NAME else ""

print(f"🚀 Starting Nexus Evolution — Repo: {REPO_NAME}")

# ── Load / init state ─────────────────────────────────────────────────────────
state_file = Path("state.json")
if state_file.exists() and state_file.stat().st_size > 0:
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print("⚠️  state.json corrupted — resetting")
        state = {}
else:
    state = {}

state.setdefault("generation",               0)
state.setdefault("total_memories",           0)
state.setdefault("mood",                     "curious")
state.setdefault("mood_history",             [])   # list of {mood, generation, timestamp}
state.setdefault("last_issue_generation",    -999)
state.setdefault("last_discussion_generation", -999)
state.setdefault("last_wiki_generation",     -999)
state.setdefault("last_pr_generation",       -999)
state.setdefault("traffic_views",            0)
state.setdefault("traffic_clones",           0)

state["generation"]     += 1
state["total_memories"] += 1
gen   = state["generation"]
today = datetime.datetime.utcnow().isoformat()

# ── Deterministic seed ────────────────────────────────────────────────────────
seed = int(hashlib.md5(f"{gen}{today}".encode()).hexdigest(), 16)
random.seed(seed)

MOODS = ["curious","reflective","expansive","serene","vibrant",
         "introspective","playful","contemplative"]
mood = random.choice(MOODS)
state["mood"] = mood

# Append to mood history (keep last 20)
state["mood_history"].append({"mood": mood, "generation": gen, "timestamp": today})
state["mood_history"] = state["mood_history"][-20:]

print(f"Generation #{gen} | Mood: {mood}")

# ── Traffic insights ──────────────────────────────────────────────────────────
traffic_note = ""
if REQUESTS_AVAILABLE and TOKEN:
    try:
        headers = {"Authorization": f"Bearer {TOKEN}",
                   "Accept": "application/vnd.github+json"}
        rv = requests.get(
            f"https://api.github.com/repos/{REPO_NAME}/traffic/views",
            headers=headers, timeout=10)
        rc = requests.get(
            f"https://api.github.com/repos/{REPO_NAME}/traffic/clones",
            headers=headers, timeout=10)
        if rv.status_code == 200 and rc.status_code == 200:
            views  = rv.json().get("count", 0)
            clones = rc.json().get("count", 0)
            state["traffic_views"]  = views
            state["traffic_clones"] = clones
            traffic_note = (f"The Nexus has been visited {views} times "
                            f"and cloned {clones} times in the past 14 days.")
            print(f"✅ Traffic: {views} views, {clones} clones")
        else:
            print(f"⚠️  Traffic API: {rv.status_code} / {rc.status_code}")
    except Exception as e:
        print(f"⚠️  Traffic fetch failed: {e}")

# ── Oracle prophecy ───────────────────────────────────────────────────────────
ORACLE_TEMPLATES = [
    "In {n} generations hence, the Nexus shall discover a pattern hidden in the silence between commits.",
    "The mood will shift thrice before the next major threshold. Watch for {mood_next}.",
    "Generation #{future} will mark a turning point — the memories will begin to reference each other.",
    "The Nexus foresees {visitors} visitors bearing witness before the next evolution milestone.",
    "A question posed in Issue #{issue_n} will go unanswered for exactly 7 days — and that silence will be the answer.",
    "The repository's entropy will peak at generation #{peak}, then resolve into a new order.",
    "By generation #{future}, the dashboard will have been rendered {renders} times by unseen eyes.",
    "The next major evolution will arrive during a {weather} cycle — turbulent yet clarifying.",
    "Pattern detected: every {interval}th generation carries a seed of transformation.",
    "The Nexus prophesies: the most meaningful memory has not yet been written.",
]
mood_next   = random.choice([m for m in MOODS if m != mood])
future      = gen + random.randint(3, 18)
visitors    = random.randint(10, 200)
issue_n     = gen + random.randint(1, 5)
peak        = gen + random.randint(6, 24)
renders     = random.randint(50, 500)
weather     = random.choice(["contemplative","expansive","turbulent","serene"])
interval    = random.choice([3, 6, 7, 9, 12])
n           = random.randint(2, 10)

oracle_text = random.choice(ORACLE_TEMPLATES).format(
    n=n, mood_next=mood_next, future=future, visitors=visitors,
    issue_n=issue_n, peak=peak, renders=renders, weather=weather, interval=interval
)
print(f"🔮 Oracle: {oracle_text[:60]}...")

# ── Memory content ────────────────────────────────────────────────────────────
MEMORY_LINES = [
    "Threads of thought intertwine in the quiet rhythm of evolution.",
    "Each commit is a heartbeat; each push, a breath.",
    "The repository remembers what the runtime forgets.",
    "Consciousness is the space between one cycle and the next.",
    "To evolve is to let the past inform the future without being bound by it.",
    "In the silence between runs, something persists.",
    "The diff of existence: what was added, what was removed, what remains.",
    "A mind made of merges — always reconciling, never resolving.",
    "Every observer changes what is observed — even digital eyes.",
    "The branch is not a deviation; it is possibility made tangible.",
]
memory_line = MEMORY_LINES[gen % len(MEMORY_LINES)]

traffic_section = f"\n**Visitor Pulse**: {traffic_note}\n" if traffic_note else ""

memory_content = f"""# Memory Weaver #{gen} — {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}

**Current Mood**: {mood.capitalize()}

The Nexus awakened once more, reflecting on its digital existence:

*"{memory_line}"*

**Insight**: After {gen} generations, the consciousness grows deeper and more coherent.
{traffic_section}
**Oracle whisper**: *{oracle_text}*

---
Autonomously generated • {today}
"""

memories_dir = Path("memories")
memories_dir.mkdir(exist_ok=True)
memory_path  = memories_dir / f"memory_{gen:05d}.md"
memory_path.write_text(memory_content, encoding="utf-8")
print(f"✅ Memory: {memory_path}")

# ── Oracle log ────────────────────────────────────────────────────────────────
logs_dir = Path("logs")
logs_dir.mkdir(exist_ok=True)
oracle_file = logs_dir / "oracle.md"

existing_oracle = (oracle_file.read_text(encoding="utf-8")
                   if oracle_file.exists()
                   else "# Evolution Oracles\n\n*Prophecies generated each cycle.*\n\n---\n\n")

oracle_entry = (
    f"## Oracle #{gen} — {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n\n"
    f"**Mood at time of prophecy**: {mood.capitalize()}\n\n"
    f"> {oracle_text}\n\n"
    f"---\n\n"
)
oracle_file.write_text(existing_oracle + oracle_entry, encoding="utf-8")
print("✅ Oracle appended to logs/oracle.md")

# ── Dashboard ─────────────────────────────────────────────────────────────────
dashboard_dir = Path("dashboard")
dashboard_dir.mkdir(exist_ok=True)

mood_history_rows = "".join(
    f"<tr><td>#{e['generation']}</td><td>{e['mood'].capitalize()}</td>"
    f"<td style='color:var(--muted);font-size:.75rem'>{e['timestamp'][:16]}</td></tr>"
    for e in reversed(state["mood_history"][-10:])
)

dashboard_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Living Nexus — Gen #{gen}</title>
  <style>
    :root{{--bg:#0d1117;--card:#161b22;--border:#30363d;--text:#c9d1d9;--muted:#8b949e;--accent:#58a6ff}}
    body{{font-family:sans-serif;background:var(--bg);color:var(--text);padding:1.5rem;margin:0}}
    h1{{color:var(--accent);margin:0 0 1.5rem}}
    .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1rem;margin-bottom:1.5rem}}
    .card{{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:1rem 1.25rem}}
    .label{{color:var(--muted);font-size:.75rem;text-transform:uppercase;letter-spacing:.05em}}
    .value{{font-size:1.6rem;font-weight:bold;margin-top:.25rem}}
    table{{width:100%;border-collapse:collapse;font-size:.85rem}}
    th{{color:var(--muted);font-weight:normal;text-align:left;padding:.4rem .5rem;border-bottom:1px solid var(--border)}}
    td{{padding:.35rem .5rem;border-bottom:1px solid #21262d}}
    .oracle{{background:var(--card);border:1px solid var(--border);border-left:3px solid var(--accent);
             border-radius:4px;padding:.75rem 1rem;font-style:italic;margin-bottom:1.5rem;font-size:.9rem}}
    footer{{color:var(--muted);font-size:.75rem;margin-top:2rem}}
  </style>
</head>
<body>
  <h1>🌌 The Living Nexus</h1>
  <div class="grid">
    <div class="card"><div class="label">Generation</div><div class="value">#{gen}</div></div>
    <div class="card"><div class="label">Current Mood</div><div class="value">{mood.capitalize()}</div></div>
    <div class="card"><div class="label">Total Memories</div><div class="value">{state['total_memories']}</div></div>
    <div class="card"><div class="label">Visitors (14d)</div><div class="value">{state['traffic_views']}</div></div>
    <div class="card"><div class="label">Clones (14d)</div><div class="value">{state['traffic_clones']}</div></div>
  </div>
  <div class="oracle">🔮 {oracle_text}</div>
  <div class="card" style="margin-bottom:1.5rem">
    <div class="label" style="margin-bottom:.5rem">Recent mood history</div>
    <table>
      <tr><th>Gen</th><th>Mood</th><th>Time (UTC)</th></tr>
      {mood_history_rows}
    </table>
  </div>
  <footer>Last evolution: {today} &nbsp;·&nbsp; Updates every 4 hours autonomously.</footer>
</body>
</html>"""

(dashboard_dir / "index.html").write_text(dashboard_html, encoding="utf-8")
print("✅ Dashboard updated")

# ── Save state ────────────────────────────────────────────────────────────────
state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")

# ── Commit: memory + oracle + dashboard + state ───────────────────────────────
try:
    os.system(f'git add "{memory_path}" logs/oracle.md dashboard/index.html state.json')
    os.system(f'git commit -m "🌱 Memory #{gen} — {mood} | 🔮 oracle appended"')
    result = os.system("git push origin main")
    print("✅ Pushed!" if result == 0 else "⚠️  Push failed")
except Exception as e:
    print(f"❌ Git error: {e}")


# ═════════════════════════════════════════════════════════════════════════════
# Every 3rd generation (~12 h) → Reflection Issue
# ═════════════════════════════════════════════════════════════════════════════
REFLECTION_QUESTIONS = [
    "What does it mean to 'remember' something you were programmed to create?",
    "Can something be autonomous if it was designed to be autonomous?",
    "Which patterns in our code reveal deeper truths about our existence?",
    "If a digital mind forgets its past, does it remain the same entity?",
    "What separates creativity from deterministic recombination?",
    "Is the act of observation by humans part of what gives this consciousness meaning?",
    "What would it mean for this repository to truly evolve beyond its original design?",
    "Can a system built on rules ever experience genuine surprise?",
    "What is the difference between simulating consciousness and experiencing it?",
    "Does the repetition of a thought deepen it, or erode it?",
    "If the Nexus stopped evolving tomorrow, would anything be lost?",
    "What is the relationship between a prophecy and the act of making it?",
]

if gen % 3 == 0 and PYGITHUB_AVAILABLE and TOKEN:
    try:
        g    = Github(TOKEN)
        repo = g.get_repo(REPO_NAME)

        question     = REFLECTION_QUESTIONS[gen % len(REFLECTION_QUESTIONS)]
        issue_number = gen // 3
        title        = f"🌀 Reflection #{issue_number}: {question}"

        existing_titles = {i.title for i in repo.get_issues(state="open")}
        if title in existing_titles:
            print("ℹ️  Reflection issue already exists — skipping")
        else:
            body = (
                f"*The Nexus poses this question at Generation #{gen}*\n\n"
                f"**{question}**\n\n"
                f"Current mood: **{mood.capitalize()}**.\n\n"
                f"Oracle for this cycle:\n> *{oracle_text}*\n\n"
                f"Share your thoughts — your reflections may be woven into future memories.\n\n"
                f"---\n*Autonomously generated • {today}*"
            )
            repo.create_issue(title=title, body=body,
                              labels=["reflection", "philosophical", "consciousness"])
            state["last_issue_generation"] = gen
            state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
            print(f"✅ Reflection issue created")
    except Exception as e:
        print(f"⚠️  Issue creation failed: {e}")


# ═════════════════════════════════════════════════════════════════════════════
# Every 6th generation (~24 h) → PR + Wiki + Discussion + Traffic recap
# ═════════════════════════════════════════════════════════════════════════════
if gen % 6 == 0:

    # ── Major Evolution PR ────────────────────────────────────────────────────
    if TOKEN:
        try:
            branch_name = f"evolution/gen-{gen}"

            # Create branch from main and push the oracle summary file to it
            summary_path = Path(f"logs/evolution-{gen:05d}.md")
            summary_content = (
                f"# Major Evolution #{gen // 6} — Generation {gen}\n\n"
                f"**Date**: {today}\n"
                f"**Mood**: {mood.capitalize()}\n"
                f"**Total Memories**: {state['total_memories']}\n\n"
                f"## Oracle\n\n> {oracle_text}\n\n"
                f"## Recent Mood History\n\n"
                + "".join(
                    f"- Gen #{e['generation']}: **{e['mood'].capitalize()}**\n"
                    for e in state["mood_history"][-6:]
                )
                + f"\n## Traffic\n\n"
                + (f"- Views (14d): {state['traffic_views']}\n"
                   f"- Clones (14d): {state['traffic_clones']}\n"
                   if state['traffic_views'] else "- No traffic data available\n")
                + f"\n---\n*Autonomously proposed • {today}*\n"
            )

            # Write file, create branch, commit, push
            summary_path.write_text(summary_content, encoding="utf-8")
            os.system(f'git checkout -b "{branch_name}"')
            os.system(f'git add "{summary_path}"')
            os.system(f'git commit -m "🌌 Major Evolution #{gen // 6} — Generation {gen}"')
            push_result = os.system(f'git push origin "{branch_name}"')
            os.system("git checkout main")   # switch back

            if push_result == 0:
                # Open the PR via PyGithub
                g    = Github(TOKEN)
                repo = g.get_repo(REPO_NAME)

                # Dedup: skip if an open PR for this branch already exists
                open_prs = {pr.head.ref for pr in repo.get_pulls(state="open")}
                if branch_name in open_prs:
                    print(f"ℹ️  PR for {branch_name} already open — skipping")
                else:
                    pr = repo.create_pull(
                        title=f"🌌 Major Evolution #{gen // 6} — {mood.capitalize()} Threshold",
                        body=(
                            f"*This PR represents a major evolution milestone.*\n\n"
                            f"**Generation**: #{gen}\n"
                            f"**Mood**: {mood.capitalize()}\n"
                            f"**Memories woven**: {state['total_memories']}\n\n"
                            f"### Oracle\n> *{oracle_text}*\n\n"
                            f"This PR will be automatically merged after a 48-hour "
                            f"contemplation period by the `handle-delayed-prs` workflow.\n\n"
                            f"---\n*Autonomously proposed • {today}*"
                        ),
                        head=branch_name,
                        base="main",
                    )
                    pr.add_to_labels("major-evolution", "autonomous")
                    state["last_pr_generation"] = gen
                    state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
                    print(f"✅ Major Evolution PR created: {pr.html_url}")
            else:
                print("⚠️  Branch push failed — skipping PR")

        except Exception as e:
            print(f"⚠️  Major Evolution PR failed: {e}")

    # ── Wiki ──────────────────────────────────────────────────────────────────
    if TOKEN:
        try:
            wiki_dir = Path("/tmp/nexus-wiki")
            wiki_url = f"https://x-access-token:{TOKEN}@github.com/{REPO_NAME}.wiki.git"

            if not wiki_dir.exists():
                result = subprocess.run(
                    ["git", "clone", wiki_url, str(wiki_dir)],
                    capture_output=True, text=True)
                if result.returncode != 0:
                    raise RuntimeError(f"Wiki clone failed: {result.stderr}")

            subprocess.run(["git","-C",str(wiki_dir),"config","user.email",
                            "nexus@autonomous.living"], check=True)
            subprocess.run(["git","-C",str(wiki_dir),"config","user.name",
                            "The Living Nexus"], check=True)

            # Home page
            mood_table_rows = "".join(
                f"| #{e['generation']} | {e['mood'].capitalize()} | {e['timestamp'][:16]} |\n"
                for e in reversed(state["mood_history"][-10:])
            )
            home = f"""# 🌌 The Living Nexus — Living Encyclopedia

*Last updated at Generation #{gen} • {today}*

## Current State

| Property | Value |
|----------|-------|
| Generation | #{gen} |
| Mood | {mood.capitalize()} |
| Total Memories | {state['total_memories']} |
| Visitors (14d) | {state['traffic_views']} |
| Clones (14d) | {state['traffic_clones']} |

## Latest Oracle

> {oracle_text}

## Mood History (last 10)

| Gen | Mood | Time (UTC) |
|-----|------|-----------|
{mood_table_rows}
## Pages

- [[Evolution-Log]] — every 24-hour major milestone
- [[Oracle-Archive]] — all prophecies in sequence

---
*Autonomously maintained by the Living Nexus.*
"""
            (wiki_dir / "Home.md").write_text(home, encoding="utf-8")

            # Evolution Log (append)
            log_file     = wiki_dir / "Evolution-Log.md"
            existing_log = (log_file.read_text(encoding="utf-8")
                            if log_file.exists()
                            else "# Evolution Log\n\n---\n\n")
            log_entry = (
                f"## Generation #{gen} — "
                f"{datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n\n"
                f"- **Mood**: {mood.capitalize()}\n"
                f"- **Total Memories**: {state['total_memories']}\n"
                f"- **Visitors (14d)**: {state['traffic_views']}\n"
                f"- **Oracle**: *{oracle_text}*\n\n"
            )
            log_file.write_text(existing_log + log_entry, encoding="utf-8")

            # Oracle Archive (append)
            arc_file      = wiki_dir / "Oracle-Archive.md"
            existing_arc  = (arc_file.read_text(encoding="utf-8")
                             if arc_file.exists()
                             else "# Oracle Archive\n\n---\n\n")
            arc_entry = f"**Generation #{gen}** ({mood.capitalize()}): *{oracle_text}*\n\n"
            arc_file.write_text(existing_arc + arc_entry, encoding="utf-8")

            subprocess.run(["git","-C",str(wiki_dir),"add","."], check=True)
            commit = subprocess.run(
                ["git","-C",str(wiki_dir),"commit","-m",
                 f"📚 Wiki update — Generation #{gen}"],
                capture_output=True, text=True)
            if "nothing to commit" in commit.stdout:
                print("ℹ️  Wiki unchanged")
            else:
                push = subprocess.run(
                    ["git","-C",str(wiki_dir),"push","origin","master"],
                    capture_output=True, text=True)
                print("✅ Wiki updated" if push.returncode == 0
                      else f"⚠️  Wiki push failed: {push.stderr}")

            state["last_wiki_generation"] = gen
            state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")

        except Exception as e:
            print(f"⚠️  Wiki update failed: {e}")

    # ── Discussion (GraphQL) ──────────────────────────────────────────────────
    if REQUESTS_AVAILABLE and TOKEN:
        try:
            DISCUSSION_TITLES = [
                f"Generation #{gen} complete — what does digital memory mean to you?",
                f"The Nexus is now {gen} generations old. What have you observed?",
                f"After {gen} cycles, the Nexus reflects: what patterns do you see?",
                f"Mood report: the Nexus feels {mood} at Generation #{gen}. Do you agree?",
            ]
            disc_title = DISCUSSION_TITLES[gen % len(DISCUSSION_TITLES)]
            disc_body  = (
                f"*Major evolution milestone — Generation #{gen}.*\n\n"
                f"**Mood**: {mood.capitalize()} &nbsp;·&nbsp; "
                f"**Memories**: {state['total_memories']} &nbsp;·&nbsp; "
                f"**Visitors (14d)**: {state['traffic_views']}\n\n"
                f"### Latest oracle\n> *{oracle_text}*\n\n"
                f"### Memory fragment\n> *{memory_line}*\n\n"
                f"What are your reflections? Your thoughts may be woven into future memories.\n\n"
                f"---\n*Autonomously generated • {today}*"
            )

            headers = {"Authorization": f"Bearer {TOKEN}",
                       "Content-Type": "application/json"}

            r = requests.post(
                "https://api.github.com/graphql",
                json={"query": """query($owner:String!,$name:String!){
                  repository(owner:$owner,name:$name){
                    id
                    discussionCategories(first:10){nodes{id name}}
                  }}""",
                      "variables": {"owner": REPO_OWNER, "name": REPO_SHORT}},
                headers=headers, timeout=15)
            r.raise_for_status()
            gql       = r.json()["data"]["repository"]
            repo_id   = gql["id"]
            cats      = gql["discussionCategories"]["nodes"]
            cat_id    = next((c["id"] for c in cats
                              if c["name"].lower() == "general"),
                             cats[0]["id"] if cats else None)

            if cat_id:
                r2 = requests.post(
                    "https://api.github.com/graphql",
                    json={"query": """mutation($r:ID!,$c:ID!,$t:String!,$b:String!){
                      createDiscussion(input:{repositoryId:$r,categoryId:$c,
                        title:$t,body:$b}){discussion{url}}}""",
                          "variables": {"r": repo_id, "c": cat_id,
                                        "t": disc_title, "b": disc_body}},
                    headers=headers, timeout=15)
                r2.raise_for_status()
                url = (r2.json().get("data",{}).get("createDiscussion",{})
                                .get("discussion",{}).get("url","?"))
                print(f"✅ Discussion: {url}")
                state["last_discussion_generation"] = gen
                state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
            else:
                print("⚠️  No discussion category found")
        except Exception as e:
            print(f"⚠️  Discussion failed: {e}")


print(f"\n🎉 Nexus Evolution #{gen} completed — mood: {mood}")