<div align="center">

<h1>PyAutoRaid</h1>

<h3>See your real Clan Boss fight before you spend a key.</h3>

<p>
Key-free battle simulation, team &amp; gear optimization, and battle history for
<strong>Raid: Shadow Legends</strong> — free, and running entirely on your own PC.
</p>

<b>🚧 In active development — public download coming soon. Watch / ★ this repo to catch the release.</b>

</div>

---

## What it does

PyAutoRaid runs the game's *actual* Clan Boss engine on your own machine, so you can
preview a fight turn-by-turn **without spending a key**. Tune a team, swap gear, check
whether you hold to Turn 50 — then commit the key only when you know it works.

- **🔑 Key-free CB simulation** — the marquee. Play out a full Clan Boss fight (turn
  order, buffs/debuffs, damage, survival) before you burn a real key.
- **🧮 Team &amp; gear optimizer** — search team combos and assign artifacts to hit speed
  tunes and stat targets (ACC floors, CR/CD, speed steps).
- **📜 Battle history** — every run logged turn-by-turn: damage per hero, buff uptime,
  and where a tune broke.
- **🤖 Automation (optional)** — hands-off dailies and farming if you want it. Entirely
  opt-in; the sim and optimizer work fine without it.

---

## How it works

PyAutoRaid installs a small **local mod** into your own copy of Raid, which exposes a
private API on your machine that the tool talks to directly.

- **Mod API only — no screen automation.** It reads game state and issues actions through
  the mod, never by faking mouse clicks or scraping the screen.
- **Everything runs locally.** Your account data stays on your PC; nothing is streamed anywhere.
- Because it uses the game's real battle engine, simulated fights match what you see live —
  that's what makes the "before you spend a key" preview trustworthy.

---

## Status

PyAutoRaid is being prepared for an easy, no-setup public release. Downloads, a community
Discord, and a support link are on the way — **watch / ★ this repo** to be here when it drops.

---

## ⚠️ Disclaimer — use at your own risk

PyAutoRaid is a **fan-made, unofficial tool**. It is **not affiliated with, endorsed by, or
associated with Plarium**. *Raid: Shadow Legends*, its name, artwork, and all related assets
are the property of Plarium.

Modifying or automating a game may violate the game's Terms of Service and could put your
account at risk. **You use this tool entirely at your own risk** — the author accepts no
liability for any consequences, including account action.

Use of PyAutoRaid is governed by the [End User License Agreement](./EULA.md).

---

## Free — donations welcome

PyAutoRaid is **100% free**. No paywall, no premium tier. An optional way to support
development will be added with the public release.

---

## About the source

The tool will be **free to use, but the source is closed** — this repository is the landing
page and (soon) release host, not the source code.

---

<div align="center">
<sub>Not affiliated with Plarium · Raid: Shadow Legends © Plarium · Use at your own risk</sub>
</div>
