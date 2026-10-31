# Genome Lineage

*Each genome lives a trial, is judged by its own fitness, and survives or dies. No human input.*

| Gen | Genome | Event |
|-----|--------|-------|
| #864 | v1 | 🧬 Genome v1 survives — fitness 0.522 |
| #864 | v2 | 🌱 proposed from v1: `reflection_max_age_days` 14 → 16 |
| #876 | v2 | 🧬 Genome v2 survives — fitness 0.65 vs parent 0.522 |
| #876 | v3 | 🌱 proposed from v2: `active_oracle_templates` [0, 1, 2, 3, 4, 5, 6, 7, 8, 9] → [0, 1, 3, 4, 5, 6, 7, 8, 9], `sense_bias.voices.reflective` 2 → 1 |
| #888 | v3 | 🧬 Genome v3 survives — fitness 0.65 vs parent 0.65 |
| #888 | v4 | 🌱 proposed from v3: `active_memory_lines` [0, 1, 2, 3, 4, 5, 6, 7, 8, 9] → [0, 1, 2, 3, 5, 6, 7, 8, 9], `evolution_every` 6 → 5 |
| #900 | v4 | 🥀 Genome v4 died — fitness 0.517 vs parent 0.65; reverting to v3 |
| #900 | v5 | 🌱 proposed from v3: `evolution_every` 6 → 7, `reflection_every` 3 → 2 |
| #917 | v5 | 🧬 Genome v5 survives — fitness 0.656 vs parent 0.65 |
| #917 | v6 | 🌱 proposed from v5: `active_memory_lines` [0, 1, 2, 3, 4, 5, 6, 7, 8, 9] → [1, 2, 3, 4, 5, 6, 7, 8, 9] |
| #931 | v6 | 🧬 Genome v6 survives — fitness 0.695 vs parent 0.656 |
| #931 | v7 | 🌱 proposed from v6: `reflection_max_age_days` 16 → 19 |
| #945 | v7 | 🥀 Genome v7 died — fitness 0.589 vs parent 0.695; reverting to v6 |
| #945 | v8 | 🌱 proposed from v6: `active_oracle_templates` [0, 1, 3, 4, 5, 6, 7, 8, 9] → [0, 1, 3, 4, 6, 7, 8, 9], `evolution_every` 7 → 8, `reflection_max_age_days` 16 → 18 |
| #960 | v8 | 🥀 Genome v8 died — fitness 0.656 vs parent 0.695; reverting to v6 |
| #960 | v9 | 🌱 proposed from v6: `active_oracle_templates` [0, 1, 3, 4, 5, 6, 7, 8, 9] → [0, 3, 4, 5, 6, 7, 8, 9] |
