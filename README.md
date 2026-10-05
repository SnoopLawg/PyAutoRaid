<div align="center">

<h1>PyAutoRaid</h1>

<h3>See your real Clan Boss fight before you spend a key.</h3>

<p>
Key-free battle simulation, team &amp; gear optimization, and battle history for
<strong>Raid: Shadow Legends</strong> — free, and running entirely on your own PC.
</p>

<p>by <a href="https://youtube.com/@walangkaalam"><b>WalangKaalam</b></a></p>

<p>
<a href="https://youtube.com/@walangkaalam">▶ YouTube</a> &nbsp;·&nbsp;
<a href="https://discord.gg/E8qf7y8sc6">💬 Discord</a> &nbsp;·&nbsp;
<a href="https://reddit.com/user/walangkaalam">👽 Reddit</a>
</p>

<p>
<a href="https://snooplawg.github.io/PyAutoRaid/"><b>🌐 Visit the website — info &amp; downloads →</b></a>
</p>

<b>🚧 In active development.</b> Full details and downloads live on the <a href="https://snooplawg.github.io/PyAutoRaid/"><b>website</b></a>.<br/>
<sub>★ this repo and join the <a href="https://discord.gg/E8qf7y8sc6">Discord</a> to catch the release.</sub>

</div>

---

## Download

| | Platform | File | Notes |
|---|---|---|---|
| 🪟 | **Windows 10 / 11** | `PyAutoRaid-Setup-<ver>.exe` | Run the installer. Nothing else to install. |
| 🍎 | **macOS** (Intel &amp; Apple Silicon) | `PyAutoRaid-<ver>-mac.dmg` | Drag **PyAutoRaid** into **Applications** and open it. |

**[⬇ Get the latest release →](https://github.com/SnoopLawg/PyAutoRaid/releases/latest)** &nbsp;·&nbsp;
[All releases](https://github.com/SnoopLawg/PyAutoRaid/releases) &nbsp;·&nbsp;
[Website, with a tour of every page](https://snooplawg.github.io/PyAutoRaid/#tour)

Either build walks you through setup on first launch — installing the mod into your own
copy of Raid, connecting to it, and copying the game's art across. No terminal, no Python,
no developer tools. Game art is copied from **your** install rather than shipped, which is
why the download is small and why the first launch takes a few minutes.

> **macOS — the first launch.** The app is not yet notarised by Apple, so Gatekeeper blocks
> it the first time. Open **Applications**, double-click **PyAutoRaid**, press **Done** on the
> warning, then go to **System Settings › Privacy & Security**, scroll down, and press
> **Open Anyway** next to "PyAutoRaid was blocked".

> Each platform's download is attached to the release that ships it; if a platform's file is
> not listed on the latest release yet, it is not out yet — the
> [Discord](https://discord.gg/E8qf7y8sc6) gets told first.

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
- **Runs locally.** Your account data (roster, gear, progress) stays on your PC. An optional, pseudonymous **battle-telemetry** feature shares *game* data (teams, speeds, results — never account info) to build aggregate community insights; it's on by default and can be turned off any time with `PYAUTORAID_TELEMETRY=0`. See the [EULA](./EULA.md).
- Because it uses the game's real battle engine, simulated fights match what you see live —
  that's what makes the "before you spend a key" preview trustworthy.

---

## Community &amp; updates

Development, guides, tune sharing, and release news:

- **▶ YouTube** — <https://youtube.com/@walangkaalam>
- **💬 Discord** — <https://discord.gg/E8qf7y8sc6>
- **👽 Reddit** — <https://reddit.com/user/walangkaalam>

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

PyAutoRaid is **100% free** — no paywall, no premium tier. If it saves you keys and you'd
like to support development, it genuinely helps:

- **❤️ Patreon** (monthly) — <https://www.patreon.com/cw/WalangKaalam/membership>
- **☕ One-time** — [Ko-fi](https://ko-fi.com/walangkaalam)

Donations are entirely optional and never gate any feature.

---

## About the source

The tool will be **free to use, but the source is closed** — this repository is the landing
page and (soon) release host, not the source code.

PyAutoRaid is developed and maintained by **[WalangKaalam](https://youtube.com/@walangkaalam)**.
This repository is hosted under the **SnoopLawg** GitHub account.

---

<div align="center">
<sub>PyAutoRaid by WalangKaalam · Not affiliated with Plarium · Raid: Shadow Legends © Plarium · Use at your own risk</sub>
</div>
