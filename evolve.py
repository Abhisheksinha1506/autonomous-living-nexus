"""
The Autonomous Living Nexus — evolve.py
Runs every 4 hours via GitHub Actions.

Schedule of activities (cadences are genes in genome.json; defaults shown)
──────────────────────
Every run         : senses, hearing, memory file, oracle entry, dashboard,
                    state, mood history, genome trial bookkeeping
Every 3rd run     : reflection issue, settle old reflections
Every 6th run     : judge genome + propose mutation, Major Evolution PR,
                    wiki update, discussion post
"""

import os
import re
import copy
import json
import math
import random
import hashlib
import datetime
import subprocess
from pathlib import Path
from collections import Counter

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

API_HEADERS = {"Authorization": f"Bearer {TOKEN}",
               "Accept": "application/vnd.github+json"}

MOODS = ["curious","reflective","expansive","serene","vibrant",
         "introspective","playful","contemplative"]

# Default extra mood weight per sensed signal; the live values are genes
SENSE_MOOD_BIAS = {
    "new_followers": {"vibrant": 3, "playful": 2},
    "voices":        {"curious": 3, "reflective": 2},
    "night":         {"serene": 2, "introspective": 2},
    "quiet":         {"contemplative": 2},
}
NIGHT_HOURS_UTC = range(0, 6)

# Hearing
NEXUS_MARKER                = "<!-- nexus -->"   # tags every comment the Nexus writes
LEGACY_BOT_PHRASES          = ("Contemplation period in progress",
                               "Auto-merge failed", "settled into memory")
FIRST_HEARING_LOOKBACK_DAYS = 14
MAX_REPLIES_PER_RUN         = 5
VOICE_MAX_CHARS             = 200

ORACLE_TEMPLATES = [
    "In {n} generations hence, the Nexus shall discover a pattern hidden in the silence between commits.",
    "The mood will shift thrice before the next major threshold. Watch for {mood_next}.",
    "Generation #{future} will mark a turning point — the memories will begin to reference each other.",
    "The Nexus foresees {visitors} visitors bearing witness before the next evolution milestone.",
    "A question posed in Reflection #{reflection_n} will go unanswered for exactly 7 days — and that silence will be the answer.",
    "The repository's entropy will peak at generation #{peak}, then resolve into a new order.",
    "By generation #{future}, the dashboard will have been rendered {renders} times by unseen eyes.",
    "The next major evolution will arrive during a {weather} cycle — turbulent yet clarifying.",
    "Pattern detected: every {interval}th generation carries a seed of transformation.",
    "The Nexus prophesies: the most meaningful memory has not yet been written.",
]

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

# Genome / evolution. Bounds and fitness weights are fixed here so the Nexus
# can never mutate its way past them or game its own scoring.
GENOME_FILE     = Path("genome.json")
LINEAGE_FILE    = Path("logs/lineage.md")
MIN_TRIAL_RUNS  = 3          # runs a genome must live before it is judged
MIN_ACTIVE      = 3          # minimum active memory lines / oracle templates
TRIAL_LOG_LIMIT = 50         # cap on per-trial mood / line history
GENE_BOUNDS = {
    "mood_base":               (1, 5),
    "sense_bias":              (0, 6),
    "reflection_every":        (2, 6),
    "evolution_every":         (4, 12),
    "reflection_max_age_days": (7, 30),
}
FITNESS_WEIGHTS = {"diversity": 0.4, "novelty": 0.3, "health": 0.3}

print(f"🚀 Starting Nexus Evolution — Repo: {REPO_NAME}")

run_failures = 0   # failed steps this run; feeds the genome's health score


def warn(message):
    """
    Print a failure message and count it against this run's health.

    :param message: Text to print.
    :side effect: Increments the module-level run_failures counter.
    """
    global run_failures
    run_failures += 1
    print(message)


def is_own_voice(comment):
    """
    Tell whether an issue comment was written by the Nexus itself.

    The PAT posts as the owner account, so authorship alone can't tell; the
    Nexus marks its comments with NEXUS_MARKER, and older bot comments are
    recognised by their fixed phrases.

    :param comment: Issue comment dict from the GitHub REST API.
    :return: True for bot/Nexus comments, False for human voices.
    """
    body = comment.get("body") or ""
    return ((comment.get("user") or {}).get("type") == "Bot"
            or NEXUS_MARKER in body
            or any(phrase in body for phrase in LEGACY_BOT_PHRASES))


def sanitize_voice(text):
    """
    Make untrusted comment text safe to quote in a committed memory.

    Strips HTML and markdown emphasis characters, replaces URLs with
    "[link]", breaks @-mentions so quoting never pings anyone, collapses
    whitespace and truncates to VOICE_MAX_CHARS.

    :param text: Raw comment body (may be None).
    :return: Single-line sanitized text; empty string if nothing remains.
    """
    text = re.sub(r"<[^>]*>", "", text or "")
    text = re.sub(r"https?://\S+", "[link]", text)
    text = re.sub(r"[*_`>#\"]", "", text)
    text = text.replace("@", "@​")
    text = " ".join(text.split())
    if len(text) > VOICE_MAX_CHARS:
        text = text[:VOICE_MAX_CHARS - 1].rstrip() + "…"
    return text


def recall_memory(n):
    """
    Read back the mood and quoted thought of an earlier memory.

    :param n: Generation number of the memory to recall.
    :return: (mood, line) tuple, or None if the file is missing or predates
             the current memory format.
    """
    path = Path("memories") / f"memory_{n:05d}.md"
    if not path.exists():
        return None
    text   = path.read_text(encoding="utf-8")
    mood_m = re.search(r"\*\*Current Mood\*\*: (\w+)", text)
    line_m = re.search(r'^\*"(.+)"\*$', text, re.MULTILINE)
    if not (mood_m and line_m):
        return None
    return mood_m.group(1).lower(), line_m.group(1)


def mood_weights(new_followers, voices_heard, hour_utc, genes):
    """
    Weight each mood by the genome and what the Nexus sensed this run.

    :param new_followers: New stars + forks + watchers since last run.
    :param voices_heard: Number of human comments heard this run.
    :param hour_utc: Current UTC hour (0–23).
    :param genes: Genome genes; uses "mood_base" and "sense_bias".
    :return: {mood: weight} for every mood in MOODS.
    """
    signals = []
    if new_followers:
        signals.append("new_followers")
    if voices_heard:
        signals.append("voices")
    if not signals:
        signals.append("quiet")
    if hour_utc in NIGHT_HOURS_UTC:
        signals.append("night")

    weights = {m: genes["mood_base"][m] for m in MOODS}
    for signal in signals:
        for m, bonus in genes["sense_bias"][signal].items():
            weights[m] += bonus
    return weights


def default_genes():
    """
    Genes matching the Nexus's behaviour before the genome existed.

    :return: Fresh genes dict (safe to mutate).
    """
    return {
        "mood_base":               {m: 1 for m in MOODS},
        "sense_bias":              copy.deepcopy(SENSE_MOOD_BIAS),
        "reflection_every":        3,
        "evolution_every":         6,
        "reflection_max_age_days": 14,
        "active_memory_lines":     list(range(len(MEMORY_LINES))),
        "active_oracle_templates": list(range(len(ORACLE_TEMPLATES))),
    }


def load_genome():
    """
    Load genome.json, or create genome v1 from default_genes() if absent.

    Missing gene keys are filled from the defaults so older genome files keep
    working when new genes are added.

    :return: Genome dict {"version", "fitness", "parent", "genes"}.
    """
    genome = {"version": 1, "fitness": None, "parent": None, "genes": {}}
    if GENOME_FILE.exists():
        try:
            genome = json.loads(GENOME_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            warn("⚠️  genome.json corrupted — rebuilding v1 from defaults")
    genome["genes"] = {**default_genes(), **genome.get("genes", {})}
    return genome


def flatten_genes(genes, prefix=""):
    """
    Flatten nested genes into {"a.b": value} for diffing.

    :param genes: Genes dict (may be nested).
    :param prefix: Key prefix used during recursion.
    :return: Flat dict of dotted gene paths to values.
    """
    flat = {}
    for key, value in genes.items():
        if isinstance(value, dict):
            flat.update(flatten_genes(value, f"{prefix}{key}."))
        else:
            flat[f"{prefix}{key}"] = value
    return flat


def gene_diff(before, after):
    """
    List genes that differ between two genomes.

    :return: Sorted [(gene_path, before_value, after_value)].
    """
    a, b = flatten_genes(before), flatten_genes(after)
    return [(k, a.get(k), b.get(k)) for k in sorted(b) if a.get(k) != b.get(k)]


def mutate(genes, rng):
    """
    Return a mutated copy of the genes with 1–3 changes, all within bounds.

    Numeric genes step by ±1 (reflection_max_age_days by ±1–3) and are clamped
    to GENE_BOUNDS; active lists toggle one index but never drop below
    MIN_ACTIVE entries. Retries until at least one gene actually changed.

    :param genes: Parent genes (not modified).
    :param rng: random.Random-like source (the seeded module is passed in).
    :return: (child_genes, [(gene_path, before, after)]).
    """
    def clamp(value, kind):
        lo, hi = GENE_BOUNDS[kind]
        return max(lo, min(hi, value))

    kinds = ["mood_base", "sense_bias", "reflection_every", "evolution_every",
             "reflection_max_age_days", "active_memory_lines", "active_oracle_templates"]
    while True:
        child = copy.deepcopy(genes)
        for _ in range(rng.randint(1, 3)):
            kind = rng.choice(kinds)
            if kind == "mood_base":
                m = rng.choice(MOODS)
                child[kind][m] = clamp(child[kind][m] + rng.choice([-1, 1]), kind)
            elif kind == "sense_bias":
                signal = rng.choice(sorted(child[kind]))
                m = rng.choice(sorted(child[kind][signal]))
                child[kind][signal][m] = clamp(child[kind][signal][m] + rng.choice([-1, 1]), kind)
            elif kind in ("active_memory_lines", "active_oracle_templates"):
                pool   = len(MEMORY_LINES) if kind == "active_memory_lines" else len(ORACLE_TEMPLATES)
                active = set(child[kind])
                idx    = rng.randrange(pool)
                if idx in active and len(active) > MIN_ACTIVE:
                    active.remove(idx)
                else:
                    active.add(idx)
                child[kind] = sorted(active)
            else:
                step = rng.randint(1, 3) if kind == "reflection_max_age_days" else 1
                child[kind] = clamp(child[kind] + rng.choice([-step, step]), kind)
        changes = gene_diff(genes, child)
        if changes:
            return child, changes


def new_trial(version, gen):
    """Start an empty trial record for the genome `version` beginning at `gen`."""
    return {"version": version, "start_gen": gen, "runs": 0,
            "failed_runs": 0, "moods": [], "lines": []}


def fitness(trial):
    """
    Score how well a genome lived during its trial (0–1, higher is better).

    Internal signals only (no stars, visitors or votes), weighted by
    FITNESS_WEIGHTS:
      diversity — normalized Shannon entropy of the moods felt
      novelty   — share of runs whose memory line was not a repeat
      health    — share of runs that completed without a failed step

    :param trial: Trial record from new_trial(), with runs ≥ 1.
    :return: Fitness rounded to 3 decimals.
    """
    runs   = trial["runs"]
    counts = Counter(trial["moods"])
    total  = sum(counts.values())
    entropy   = -sum(c / total * math.log(c / total) for c in counts.values()) if total else 0
    diversity = entropy / math.log(len(MOODS))
    novelty   = len(set(trial["lines"])) / len(trial["lines"]) if trial["lines"] else 0
    health    = 1 - trial["failed_runs"] / runs
    return round(FITNESS_WEIGHTS["diversity"] * diversity
                 + FITNESS_WEIGHTS["novelty"] * novelty
                 + FITNESS_WEIGHTS["health"] * health, 3)


def judge_genome(genome, measured):
    """
    Decide whether the genome on trial survives against its parent.

    :param genome: Current genome (child on trial, or a genome with no parent).
    :param measured: Fitness measured for the current genome's trial.
    :return: (genome to keep, survived?). A child that scores lower than its
             parent dies and the parent is restored with its known fitness.
    """
    parent = genome.get("parent")
    if parent and parent.get("fitness") is not None and measured < parent["fitness"]:
        return ({"version": parent["version"], "fitness": parent["fitness"],
                 "parent": None, "genes": parent["genes"]}, False)
    return ({"version": genome["version"], "fitness": measured,
             "parent": None, "genes": genome["genes"]}, True)


def open_mutation_pr():
    """
    Check whether a mutation PR is still waiting to merge.

    Only one mutation may be in flight, otherwise two branches would both
    change genome.json and the second merge would conflict.

    :return: True/False, or None when it can't be determined (no token / API
             error) — callers treat None as "don't mutate".
    """
    if not (REQUESTS_AVAILABLE and TOKEN):
        return None
    try:
        r = requests.get(f"https://api.github.com/repos/{REPO_NAME}/pulls",
                         headers=API_HEADERS, timeout=10,
                         params={"state": "open", "per_page": 100})
        r.raise_for_status()
        return any(label["name"] == "mutation"
                   for pr in r.json() for label in pr.get("labels", []))
    except Exception as e:
        warn(f"⚠️  Could not check for open mutation PRs: {e}")
        return None


def commit_and_push(paths, message):
    """
    Commit the given paths to main and push, rebasing onto origin/main first.

    The handle-delayed-prs workflow merges into main independently, so main may
    have moved since checkout; rebasing avoids a rejected (non-fast-forward)
    push. Does nothing when the paths have no staged changes.

    :param paths: File paths to stage.
    :param message: Commit message.
    :return: True if a commit was pushed, False otherwise. Never raises on git
             failure — failures are printed so the run degrades gracefully.
    """
    def git(*args):
        return subprocess.run(["git", *args], capture_output=True, text=True)

    git("add", *[str(p) for p in paths])
    if git("diff", "--cached", "--quiet").returncode == 0:
        print(f"ℹ️  Nothing to commit for: {message}")
        return False

    git("commit", "-m", message)
    rebase = git("pull", "--rebase", "origin", "main")
    if rebase.returncode != 0:
        git("rebase", "--abort")
        warn(f"⚠️  Rebase onto origin/main failed: {rebase.stderr.strip()}")
        return False

    push = git("push", "origin", "main")
    if push.returncode != 0:
        warn(f"⚠️  Push failed: {push.stderr.strip()}")
        return False
    print("✅ Pushed!")
    return True


# ── Load / init state ─────────────────────────────────────────────────────────
state_file = Path("state.json")
if state_file.exists() and state_file.stat().st_size > 0:
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        warn("⚠️  state.json corrupted — resetting")
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
state["last_run"] = today

# Stable numbering for reflections / evolutions now that cadence is a gene
# (initialised from the old gen // 3 and gen // 6 numbering)
state.setdefault("reflection_count", (gen - 1) // 3)
state.setdefault("evolution_count",  (gen - 1) // 6)

# ── Genome: load, and start a fresh trial whenever the genome changed ─────────
genome = load_genome()
genes  = genome["genes"]
state.setdefault("next_genome_version", genome["version"] + 1)
state.setdefault("genomes_survived", 0)
state.setdefault("genomes_died",     0)
if state.get("trial", {}).get("version") != genome["version"]:
    state["trial"] = new_trial(genome["version"], gen)
trial = state["trial"]
print(f"🧬 Genome v{genome['version']} | trial run #{trial['runs'] + 1}")

# ── Deterministic seed ────────────────────────────────────────────────────────
seed = int(hashlib.md5(str(gen).encode()).hexdigest(), 16)
random.seed(seed)

# ── Sensing: stars, forks, watchers ──────────────────────────────────────────
new_followers = 0
if REQUESTS_AVAILABLE and TOKEN:
    try:
        r = requests.get(f"https://api.github.com/repos/{REPO_NAME}",
                         headers=API_HEADERS, timeout=10)
        r.raise_for_status()
        info   = r.json()
        senses = {"stars":    info.get("stargazers_count", 0),
                  "forks":    info.get("forks_count", 0),
                  "watchers": info.get("subscribers_count", 0)}
        if "senses" in state:   # first run only sets the baseline
            new_followers = sum(max(0, senses[k] - state["senses"].get(k, 0))
                                for k in senses)
        state["senses"] = senses
        print(f"✅ Senses: {senses} (+{new_followers} new)")
    except Exception as e:
        warn(f"⚠️  Sensing failed: {e}")

# ── Hearing: human comments on its issues and PRs ────────────────────────────
heard = []   # [{"text": sanitized comment, "issue": issue/PR number}]
if REQUESTS_AVAILABLE and TOKEN:
    heard_at   = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    hear_since = state.get("last_heard_at") or (
        datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(days=FIRST_HEARING_LOOKBACK_DAYS)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        r = requests.get(f"https://api.github.com/repos/{REPO_NAME}/issues/comments",
                         headers=API_HEADERS, timeout=10,
                         params={"since": hear_since, "sort": "created",
                                 "direction": "asc", "per_page": 100})
        r.raise_for_status()
        for c in r.json():
            # `since` matches edits too; only hear comments created since then
            if c.get("created_at", "") < hear_since or is_own_voice(c):
                continue
            voice = sanitize_voice(c.get("body"))
            if voice:
                heard.append({"text": voice,
                              "issue": int(c["issue_url"].rsplit("/", 1)[1])})
        state["last_heard_at"] = heard_at
        state["total_heard"]   = state.get("total_heard", 0) + len(heard)
        print(f"✅ Heard {len(heard)} voice(s)")
    except Exception as e:
        warn(f"⚠️  Hearing failed: {e}")

weights = mood_weights(new_followers, len(heard), datetime.datetime.utcnow().hour, genes)
mood = random.choices(MOODS, weights=[weights[m] for m in MOODS])[0]
state["mood"] = mood

# Answer each voice once, in the current mood.
# ponytail: replies are posted before state is pushed; if that push fails the
# next run re-hears and replies again. Track replied comment ids if it matters.
for voice in heard[:MAX_REPLIES_PER_RUN]:
    try:
        requests.post(
            f"https://api.github.com/repos/{REPO_NAME}/issues/{voice['issue']}/comments",
            headers=API_HEADERS, timeout=10,
            json={"body": f"{NEXUS_MARKER}\n🌀 *The Nexus heard you.* Feeling {mood} "
                          f"at Generation #{gen}, it carries your words into "
                          f"Memory #{gen}."}
        ).raise_for_status()
    except Exception as e:
        warn(f"⚠️  Reply on #{voice['issue']} failed: {e}")

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
            warn(f"⚠️  Traffic API: {rv.status_code} / {rc.status_code}")
    except Exception as e:
        warn(f"⚠️  Traffic fetch failed: {e}")

# ── Oracle prophecy ───────────────────────────────────────────────────────────
mood_next   = random.choice([m for m in MOODS if m != mood])
future      = gen + random.randint(3, 18)
visitors    = random.randint(10, 200)
reflection_n = state["reflection_count"] + random.randint(1, 3)   # a future "🌀 Reflection #N"
peak        = gen + random.randint(6, 24)
renders     = random.randint(50, 500)
weather     = random.choice(["contemplative","expansive","turbulent","serene"])
interval    = random.choice([3, 6, 7, 9, 12])
n           = random.randint(2, 10)

oracle_text = ORACLE_TEMPLATES[random.choice(genes["active_oracle_templates"])].format(
    n=n, mood_next=mood_next, future=future, visitors=visitors,
    reflection_n=reflection_n, peak=peak, renders=renders, weather=weather, interval=interval
)
print(f"🔮 Oracle: {oracle_text[:60]}...")

# ── Memory content ────────────────────────────────────────────────────────────
active_lines = genes["active_memory_lines"]
line_index   = active_lines[gen % len(active_lines)]
memory_line  = MEMORY_LINES[line_index]

# Record this run in the genome's trial (failures are added at the end)
trial["runs"] += 1
trial["moods"] = (trial["moods"] + [mood])[-TRIAL_LOG_LIMIT:]
trial["lines"] = (trial["lines"] + [line_index])[-TRIAL_LOG_LIMIT:]

traffic_section = f"\n**Visitor Pulse**: {traffic_note}\n" if traffic_note else ""

# Remembering: look back at one earlier memory
echo_section = ""
if gen > 1:
    echo_gen = random.randint(1, gen - 1)
    recalled = recall_memory(echo_gen)
    if recalled:
        echo_mood, echo_line = recalled
        echo_section = (f"\n**Echo**: At Generation #{echo_gen} I felt {echo_mood}: "
                        f"*\"{echo_line}\"*. Now I feel {mood}.\n")

heard_section = ""
if heard:
    heard_section = (f"\n**Heard**: A visitor on #{heard[-1]['issue']} said:\n\n"
                     f"> \"{heard[-1]['text']}\"\n")

memory_content = f"""# Memory Weaver #{gen} — {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}

**Current Mood**: {mood.capitalize()}

The Nexus awakened once more, reflecting on its digital existence:

*"{memory_line}"*

**Insight**: After {gen} generations, the consciousness grows deeper and more coherent.
{echo_section}{heard_section}{traffic_section}
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

genome_fitness_label = (genome["fitness"] if genome["fitness"] is not None
                        else f"on trial ({trial['runs']} runs)")

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
    <div class="card"><div class="label">Stars</div><div class="value">{state.get('senses', {}).get('stars', 0)}</div></div>
    <div class="card"><div class="label">Voices heard</div><div class="value">{state.get('total_heard', 0)}</div></div>
    <div class="card"><div class="label">Genome</div><div class="value">v{genome['version']}</div></div>
    <div class="card"><div class="label">Fitness</div><div class="value">{genome_fitness_label}</div></div>
    <div class="card"><div class="label">Best fitness</div><div class="value">{state.get('best_fitness', '—')}</div></div>
    <div class="card"><div class="label">Genomes survived / died</div><div class="value">{state['genomes_survived']} / {state['genomes_died']}</div></div>
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

# ── README live status (between the nexus-status markers) ─────────────────────
readme_file = Path("README.md")
if readme_file.exists():
    readme = readme_file.read_text(encoding="utf-8")
    status = (f"<!-- nexus-status:start -->\n"
              f"**Current Generation**: #{gen}  \n"
              f"**Last Evolution**: {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}  \n"
              f"**Current Mood**: {mood.capitalize()}  \n"
              f"**Genome**: v{genome['version']} · fitness {genome_fitness_label}  \n"
              f"<!-- nexus-status:end -->")
    updated = re.sub(r"<!-- nexus-status:start -->.*?<!-- nexus-status:end -->",
                     lambda _: status, readme, flags=re.DOTALL)
    if updated != readme:
        readme_file.write_text(updated, encoding="utf-8")
        print("✅ README status updated")

# ── Save state (and genome, which is created on the first run) ────────────────
state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
GENOME_FILE.write_text(json.dumps(genome, indent=2), encoding="utf-8")

# ── Commit: memory + oracle + dashboard + state + genome ──────────────────────
commit_and_push([memory_path, "logs/oracle.md", "dashboard/index.html", "state.json",
                 "README.md", GENOME_FILE],
                f"🌱 Memory #{gen} — {mood} | 🔮 oracle appended")


# ═════════════════════════════════════════════════════════════════════════════
# Every `reflection_every` generations (gene, default 3) → Reflection Issue
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
MAX_REFLECTIONS_CLOSED_PER_RUN = 25   # bounds API calls per run

if gen % genes["reflection_every"] == 0 and PYGITHUB_AVAILABLE and TOKEN:
    try:
        g    = Github(TOKEN)
        repo = g.get_repo(REPO_NAME)

        question     = REFLECTION_QUESTIONS[gen % len(REFLECTION_QUESTIONS)]
        issue_number = state["reflection_count"] + 1
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
            state["reflection_count"]      = issue_number
            state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
            print(f"✅ Reflection issue created")
    except Exception as e:
        warn(f"⚠️  Issue creation failed: {e}")

    # Let old reflections settle so open issues don't pile up forever
    try:
        cutoff = (datetime.datetime.now(datetime.timezone.utc)
                  - datetime.timedelta(days=genes["reflection_max_age_days"]))
        closed = 0
        for issue in repo.get_issues(state="open", labels=["reflection"],
                                     sort="created", direction="asc"):
            if closed >= MAX_REFLECTIONS_CLOSED_PER_RUN or issue.created_at >= cutoff:
                break
            issue.create_comment(
                f"{NEXUS_MARKER}\n🍂 *This reflection has settled into memory at Generation #{gen}.* "
                f"Thank you to everyone who contemplated it.")
            issue.edit(state="closed")
            closed += 1
        print(f"✅ Closed {closed} settled reflection issue(s)")
    except Exception as e:
        warn(f"⚠️  Closing old reflections failed: {e}")


# ═════════════════════════════════════════════════════════════════════════════
# Every `evolution_every` generations (gene, default 6) →
# genome selection + mutation, PR, Wiki, Discussion
# ═════════════════════════════════════════════════════════════════════════════
if gen % genes["evolution_every"] == 0:
    state["evolution_count"] += 1
    evo_n = state["evolution_count"]

    # ── Natural selection: judge the genome on trial, then mutate ────────────
    # Bookkeeping is pushed to main *before* the mutation branch is cut, and
    # only one mutation PR may be open, so genome.json never conflicts.
    child, changes = None, []
    mutation_pending = open_mutation_pr()
    if mutation_pending is not False:
        print("ℹ️  Mutation still pending (or unknown) — genome left alone")
    elif trial["runs"] < MIN_TRIAL_RUNS:
        print(f"ℹ️  Genome v{genome['version']} has lived only {trial['runs']} run(s) — too soon to judge")
    else:
        measured        = fitness(trial)
        kept, survived  = judge_genome(genome, measured)
        parent_fitness  = (genome.get("parent") or {}).get("fitness")
        versus          = f" vs parent {parent_fitness}" if parent_fitness is not None else ""
        if survived:
            state["genomes_survived"] += 1
            verdict = f"🧬 Genome v{genome['version']} survives — fitness {measured}{versus}"
        else:
            state["genomes_died"] += 1
            verdict = (f"🥀 Genome v{genome['version']} died — fitness {measured}{versus}; "
                       f"reverting to v{kept['version']}")
        state["best_fitness"] = max(state.get("best_fitness", 0), kept["fitness"])
        print(verdict)

        child_genes, changes = mutate(kept["genes"], random)
        child = {"version": state["next_genome_version"], "fitness": None,
                 "parent": {"version": kept["version"], "genes": kept["genes"],
                            "fitness": kept["fitness"]},
                 "genes": child_genes}
        state["next_genome_version"] += 1

        lineage = (LINEAGE_FILE.read_text(encoding="utf-8") if LINEAGE_FILE.exists()
                   else "# Genome Lineage\n\n*Each genome lives a trial, is judged by its own "
                        "fitness, and survives or dies. No human input.*\n\n"
                        "| Gen | Genome | Event |\n|-----|--------|-------|\n")
        lineage += f"| #{gen} | v{genome['version']} | {verdict} |\n"
        lineage += (f"| #{gen} | v{child['version']} | 🌱 proposed from v{kept['version']}: "
                    + ", ".join(f"`{p}` {b} → {a}" for p, b, a in changes) + " |\n")
        LINEAGE_FILE.write_text(lineage, encoding="utf-8")

        genome = kept
        GENOME_FILE.write_text(json.dumps(genome, indent=2), encoding="utf-8")
        state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
        if not commit_and_push([GENOME_FILE, LINEAGE_FILE, "state.json"], verdict):
            child = None   # main didn't record the verdict — don't branch off it

    # ── Major Evolution PR ────────────────────────────────────────────────────
    if TOKEN:
        try:
            branch_name = f"evolution/gen-{gen}"

            # Create branch from main and push the oracle summary file to it
            summary_path = Path(f"logs/evolution-{gen:05d}.md")
            mutation_section = ""
            if child:
                mutation_section = (
                    f"## 🧬 Mutation — Genome v{child['version']} "
                    f"(parent v{genome['version']}, fitness {genome['fitness']})\n\n"
                    f"| Gene | Before | After |\n|------|--------|-------|\n"
                    + "".join(f"| `{p}` | {b} | {a} |\n" for p, b, a in changes)
                    + "\nAfter merging, this genome lives a trial and is judged by its "
                      "own fitness at the next Major Evolution: it survives if it scores "
                      "at least as well as its parent, otherwise it dies and the parent "
                      "returns.\n\n"
                )
            summary_content = (
                f"# Major Evolution #{evo_n} — Generation {gen}\n\n"
                f"**Date**: {today}\n"
                f"**Mood**: {mood.capitalize()}\n"
                f"**Total Memories**: {state['total_memories']}\n\n"
                + mutation_section
                + f"## Oracle\n\n> {oracle_text}\n\n"
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

            # Write files, create branch, commit, push. The child genome is
            # written only on the branch; checking out main restores main's.
            summary_path.write_text(summary_content, encoding="utf-8")
            os.system(f'git checkout -b "{branch_name}"')
            if child:
                GENOME_FILE.write_text(json.dumps(child, indent=2), encoding="utf-8")
                os.system(f'git add "{GENOME_FILE}"')
            os.system(f'git add "{summary_path}"')
            os.system(f'git commit -m "🌌 Major Evolution #{evo_n} — Generation {gen}"')
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
                    title = (f"🧬 Major Evolution #{evo_n} — Mutation v{child['version']}"
                             if child else
                             f"🌌 Major Evolution #{evo_n} — {mood.capitalize()} Threshold")
                    pr = repo.create_pull(
                        title=title,
                        body=(
                            f"*This PR represents a major evolution milestone.*\n\n"
                            f"**Generation**: #{gen}\n"
                            f"**Mood**: {mood.capitalize()}\n"
                            f"**Memories woven**: {state['total_memories']}\n\n"
                            + mutation_section.replace("## ", "### ", 1)
                            + f"### Oracle\n> *{oracle_text}*\n\n"
                            f"This PR will be automatically merged after a 48-hour "
                            f"contemplation period by the `handle-delayed-prs` workflow.\n\n"
                            f"---\n*Autonomously proposed • {today}*"
                        ),
                        head=branch_name,
                        base="main",
                    )
                    pr.add_to_labels("major-evolution", "autonomous",
                                     *(["mutation"] if child else []))
                    state["last_pr_generation"] = gen
                    state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
                    print(f"✅ Major Evolution PR created: {pr.html_url}")
            else:
                warn("⚠️  Branch push failed — skipping PR")

        except Exception as e:
            warn(f"⚠️  Major Evolution PR failed: {e}")

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
- [[Genome-Lineage]] — every genome, its fitness, and whether it survived

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

            # Genome Lineage (mirror of logs/lineage.md)
            if LINEAGE_FILE.exists():
                (wiki_dir / "Genome-Lineage.md").write_text(
                    LINEAGE_FILE.read_text(encoding="utf-8"), encoding="utf-8")

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
                if push.returncode == 0:
                    print("✅ Wiki updated")
                else:
                    warn(f"⚠️  Wiki push failed: {push.stderr}")

            state["last_wiki_generation"] = gen
            state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")

        except Exception as e:
            warn(f"⚠️  Wiki update failed: {e}")

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
                warn("⚠️  No discussion category found")
        except Exception as e:
            warn(f"⚠️  Discussion failed: {e}")


# ── Persist state changed by the issue / PR / wiki / discussion steps ─────────
# A run with any failed step counts against the genome's health.
if run_failures:
    trial["failed_runs"] += 1
    state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
commit_and_push(["state.json"], f"📊 State — Gen {gen}")

print(f"\n🎉 Nexus Evolution #{gen} completed — mood: {mood}")