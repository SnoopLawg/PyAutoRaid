// Simulated PyAutoRaid live data engine. Exposes:
//   window.PARSim.subscribe(fn) -> unsubscribe
//   window.PARSim.setRunning(bool)
//   window.PARSim.state (read-only snapshot)
//   window.PARSim.skipTo(taskId)

(function () {
  const TASKS = [
    { id: 'connect',     label: 'Attach to GameAssembly.dll',    layer: 'memory', duration: 1400 },
    { id: 'window',      label: 'Resize game window → 900×600',  layer: 'screen', duration: 900  },
    { id: 'gem_mine',    label: 'Collect Gem Mine',              layer: 'mod',    duration: 1600, reward: { gems: 60 } },
    { id: 'shop',        label: 'Claim free shop offers',        layer: 'mod',    duration: 2100, reward: { silver: 50000, energy: 60 } },
    { id: 'timed',       label: 'Claim timed rewards (5m–180m)', layer: 'screen', duration: 2400, reward: { silver: 40000, energy: 120, gems: 15 } },
    { id: 'clan',        label: 'Clan check-in + treasure',      layer: 'mod',    duration: 1800, reward: { silver: 25000 } },
    { id: 'quests_reg',  label: 'Claim regular quests',          layer: 'mod',    duration: 2600, reward: { gems: 90, silver: 75000, shards: 1 } },
    { id: 'quests_adv',  label: 'Claim advanced quests',         layer: 'mod',    duration: 2200, reward: { gems: 120, shards: 2 } },
    { id: 'inbox',       label: 'Collect inbox (energy, forge)', layer: 'mod',    duration: 1900, reward: { energy: 300, silver: 20000 } },
    { id: 'arena',       label: 'Classic Arena — 10 battles',    layer: 'battle', duration: 4200, reward: { arena_tokens: -10, gems: 40, silver: 30000 } },
    { id: 'cb',          label: 'Clan Boss (Ultra-Nightmare)',   layer: 'battle', duration: 5200, reward: { cb_keys: -2 } },
    { id: 'dungeon',     label: 'Dragon 20 — Dungeon Divers',    layer: 'battle', duration: 6200, reward: { energy: -80, silver: 180000 } },
  ];

  const HEROES_STARTERS = ['Kael', 'Athel', 'Galek', 'Elhain'];
  const HEROES_LEGENDARY = ['Krisk the Ageless', 'Rotos the Lost Groom', 'Arbiter', 'Siphi the Lost Bride', 'Seer', 'Maneater', 'Duchess Lilitu', 'Sir Nicholas', 'High Khatun', 'Apothecary'];

  const EVENTS = [
    { name: 'Dungeon Divers: Dragon', type: 'solo',       progress: 0.62, reward: 'Void Shard ×2', ends_in: '2d 4h' },
    { name: 'Dragon Tournament',      type: 'tournament', progress: 0.41, reward: 'Ancient Shard ×10', ends_in: '4d 11h' },
    { name: 'Champion Training',      type: 'solo',       progress: 0.28, reward: 'XP Brew ×25', ends_in: '2d 4h' },
    { name: 'Summon Rush',            type: 'tournament', progress: 0.0,  reward: 'Sacred ×1', ends_in: 'starts in 1d 6h', upcoming: true },
  ];

  // Seed
  const state = {
    running: false,
    realMode: false,   // true while the proxy is actually executing; sim pauses
    lastRunAt: null,
    nextRunAt: Date.now() + 2 * 60 * 60 * 1000, // in 2h
    queueIdx: -1,                               // -1 idle
    queueStart: 0,
    queueProgress: 0,                           // 0..1 within current task
    tasks: TASKS.map(t => ({ ...t, status: 'pending', ms: 0, loggedAt: 0, selected: true })),
    resources: {
      energy:       132450,
      silver:      48_200_000,
      gems:         12_480,
      arena_tokens: 3.5,
      cb_keys:      2,
      shards:       { mystery: 14, ancient: 6, void: 1, sacred: 0 },
    },
    account: { level: 95, power: 4_820_000, name: 'SnoopLawg', vault_rank: 12 },
    cb: {
      clan: 'HellforgedVIII',
      keys_used: 0, keys_total: 2,
      damage_today: 0,
      difficulty: 'Ultra-Nightmare',
      affinity: 'Magic',
      boss_hp: 115_000_000,
      team: [
        { name: 'Krisk the Ageless', role: 'Defense lead · Counterattack', rarity: 'Legendary', faction: 'Lizardmen',     hp: 51200, def: 3840, spd: 180, dmg_dealt: 3_180_000, dmg_taken: 1_420_000, counters: 31, turns: 26 },
        { name: 'Seducer',           role: 'Decrease ATK · AoE',          rarity: 'Epic',      faction: 'Undead Hordes',  hp: 22800, def: 2040, spd: 207, dmg_dealt: 2_410_000, dmg_taken:   340_000, counters:  0, turns: 30 },
        { name: 'Frozen Banshee',    role: 'Poisons · HP-burn',           rarity: 'Epic',      faction: 'Dark Elves',     hp: 19400, def: 1760, spd: 213, dmg_dealt: 3_640_000, dmg_taken:   280_000, counters:  0, turns: 31 },
        { name: 'Tormentor',         role: 'Decrease DEF · AoE',          rarity: 'Rare',      faction: 'Demonspawn',     hp: 18900, def: 1680, spd: 199, dmg_dealt: 1_120_000, dmg_taken:   510_000, counters:  0, turns: 29 },
        { name: 'Warmaiden',         role: 'Decrease DEF · single',       rarity: 'Rare',      faction: 'Banner Lords',   hp: 17200, def: 1510, spd: 186, dmg_dealt: 1_050_000, dmg_taken:   580_000, counters:  0, turns: 27 },
      ],
      last_run: {
        duration_s: 204,
        turns_total: 143,
        damage: 11_540_000,
        damage_taken: 3_130_000,
        unkillable_triggers: 6,
        counters_total: 31,
        debuffs_applied: { 'Dec ATK': 18, 'Dec DEF': 22, 'HP Burn': 14, 'Poison': 41, 'Weaken': 9 },
        timeline: [
          { t: 12,  ev: 'Dec ATK applied',  by: 'Seducer' },
          { t: 18,  ev: 'Dec DEF applied',  by: 'Warmaiden' },
          { t: 24,  ev: 'Poison ×4 stacked',by: 'Frozen Banshee' },
          { t: 42,  ev: 'Counterattack ×5',  by: 'Krisk' },
          { t: 78,  ev: 'HP Burn tick 1.2M', by: 'Frozen Banshee' },
          { t: 121, ev: 'Unkillable proc ×2',by: 'Krisk' },
          { t: 168, ev: 'Dec DEF renewed',   by: 'Tormentor' },
          { t: 204, ev: 'Run end — 11.54M',  by: 'result' },
        ],
      },
      potential_teams: [
        {
          name: 'Counter-Poison (active)',
          status: 'active',
          est_damage: 11_540_000,
          confidence: 0.92,
          tags: ['unkillable','poison','dec-def'],
          heroes: ['Krisk the Ageless','Seducer','Frozen Banshee','Tormentor','Warmaiden'],
          note: 'Current daily comp. Reliable 11-12M, no key loss in 42 days.',
        },
        {
          name: 'Full Poison + HP Burn',
          status: 'candidate',
          est_damage: 13_200_000,
          confidence: 0.78,
          tags: ['poison','hp-burn','nuke'],
          heroes: ['High Khatun','Seducer','Frozen Banshee','Bad-el-Kazar','Warmaiden'],
          note: 'Higher ceiling but requires Bad-el heal to avoid wipe on turn 38.',
        },
        {
          name: 'Giant Slayer stack',
          status: 'candidate',
          est_damage: 12_650_000,
          confidence: 0.71,
          tags: ['giant-slayer','hp-burn'],
          heroes: ['Krisk the Ageless','Apothecary','Frozen Banshee','Occult Brawler','Warmaiden'],
          note: 'Needs Occult Brawler to 6★ · projected gain +1.1M.',
        },
        {
          name: 'Budget F2P',
          status: 'backup',
          est_damage: 7_800_000,
          confidence: 0.88,
          tags: ['starter','safe'],
          heroes: ['Kael','Warmaiden','Seducer','Apothecary','Tormentor'],
          note: 'Fallback if Krisk locked (Doom Tower). Safe 7-8M.',
        },
      ],
      sim: {
        baseline: 11_540_000,
        runs: 500,
        variance: 0.08,
        target: 12_500_000,
        histogram: [
          { bucket: '9.5', n:  6 },
          { bucket: '10.0', n: 22 },
          { bucket: '10.5', n: 58 },
          { bucket: '11.0', n: 124 },
          { bucket: '11.5', n: 156 },
          { bucket: '12.0', n: 94 },
          { bucket: '12.5', n: 32 },
          { bucket: '13.0', n:  8 },
        ],
        scenarios: [
          { name: 'Current build',         avg: 11_540_000, min: 10_200_000, max: 12_400_000, keyable: true  },
          { name: '+ Speed Krisk 180→186', avg: 11_920_000, min: 10_800_000, max: 12_800_000, keyable: true  },
          { name: '+ 6★ Frozen Banshee',   avg: 12_380_000, min: 11_100_000, max: 13_100_000, keyable: true  },
          { name: 'Swap Warmaiden → Apoth.',avg: 10_210_000, min:  9_400_000, max: 11_000_000, keyable: true },
          { name: 'Push Nightmare 3x',     avg:  4_900_000, min:  4_200_000, max:  5_400_000, keyable: false },
        ],
      },
      history: [
        { day: 'Mon', dmg: 18_200_000 },
        { day: 'Tue', dmg: 19_700_000 },
        { day: 'Wed', dmg: 17_900_000 },
        { day: 'Thu', dmg: 21_100_000 },
        { day: 'Fri', dmg: 22_400_000 },
        { day: 'Sat', dmg: 23_050_000 },
        { day: 'Today', dmg: 0 },
      ],
    },
    layers: {
      mod:    { up: true,  latency: 9,  label: 'MelonLoader mod',  port: 6790, detail: '/buttons 14 active' },
      memory: { up: true,  latency: 2,  label: 'IL2CPP memory',    port: null, detail: 'pymem attached' },
      screen: { up: true,  latency: 42, label: 'Screen automation',port: null, detail: '900×600 @ (14,56)' },
    },
    vm: { host: 'mothership2', ip: '192.168.0.244', cpu: 31, ram: 2.4, ramMax: 4.0 },
    events: EVENTS,
    arena_opponents: [
      { name: 'xXDragonSlayerXx', power: 3_410_000, tier: 'Silver II', status: 'weak',   pick: true },
      { name: 'RaidGod_99',       power: 4_250_000, tier: 'Gold I',    status: 'fair',   pick: false },
      { name: 'ArbiterAndrew',    power: 5_820_000, tier: 'Gold IV',   status: 'strong', pick: false },
      { name: 'FreeToPlayMike',   power: 3_090_000, tier: 'Silver I',  status: 'weak',   pick: false },
      { name: 'SpiderFarmer',     power: 4_900_000, tier: 'Gold III',  status: 'fair',   pick: false },
    ],
    log: [],
    history: genHistory(),
    heroes: genHeroes(),
  };

  function genHistory() {
    const out = [];
    const now = Date.now();
    for (let i = 13; i >= 0; i--) {
      const d = new Date(now - i * 24 * 3600 * 1000);
      out.push({
        day: d.toISOString().slice(5, 10),
        gems: 120 + Math.round(Math.random() * 220),
        silver_m: 1.2 + Math.random() * 3,
        battles: 18 + Math.round(Math.random() * 6),
        cb_dmg_m: 17 + Math.random() * 7,
      });
    }
    return out;
  }

  function genHeroes() {
    const factions = ['Banner Lords', 'Barbarians', 'High Elves', 'Ogryn Tribe', 'Sacred Order', 'Undead Hordes', 'Knights Revenant'];
    const rarities = ['Common','Uncommon','Rare','Epic','Legendary'];
    const out = [];
    HEROES_LEGENDARY.forEach((n, i) => out.push({
      name: n, faction: factions[i % factions.length], rarity: 'Legendary', stars: 6, level: 60, power: 180_000 + Math.random()*60_000
    }));
    for (let i = 0; i < 22; i++) {
      out.push({
        name: HEROES_STARTERS[i % 4] + ' ' + (['I','II','III','IV','V','VI','VII'][i % 7]),
        faction: factions[i % factions.length],
        rarity: rarities[1 + (i % 3)],
        stars: 3 + (i % 4),
        level: 20 + (i*3) % 40,
        power: 40_000 + Math.random()*80_000,
      });
    }
    return out;
  }

  // Subscribers
  const subs = new Set();
  function notify() { subs.forEach(fn => fn(state)); }

  // Log
  function pushLog(level, text, tag) {
    state.log.unshift({ t: Date.now(), level, text, tag: tag || null });
    if (state.log.length > 200) state.log.pop();
  }

  // Bootstrap log
  pushLog('info', 'PyAutoRaid v2.1-beta ready. Next run 07:00 local.', 'system');
  pushLog('info', 'Attached to GameAssembly.dll (PID 4820). MelonLoader plugin online on :6790.', 'memory');
  pushLog('info', `Account Lv${state.account.level} · Power ${(state.account.power/1e6).toFixed(2)}M`, 'memory');

  // Tick loop
  let last = performance.now();
  function tick(now) {
    const dt = now - last;
    last = now;

    if (state.running && !state.realMode) {
      if (state.queueIdx < 0) {
        // Advance to first selected task
        let first = 0;
        while (first < state.tasks.length && !state.tasks[first].selected) {
          state.tasks[first].status = 'skipped';
          first++;
        }
        if (first >= state.tasks.length) {
          // Nothing selected — end immediately
          state.running = false;
          state.lastRunAt = Date.now();
          pushLog('warn', 'No tasks selected — run ended.', 'system');
          notify();
          requestAnimationFrame(tick);
          return;
        }
        state.queueIdx = first;
        state.queueStart = now;
        state.queueProgress = 0;
        state.tasks[first].status = 'running';
        pushLog('run', `▶ ${state.tasks[first].label}`, state.tasks[first].layer);
      }
      const task = state.tasks[state.queueIdx];
      task.ms = now - state.queueStart;
      state.queueProgress = Math.min(1, task.ms / task.duration);

      // Mid-task sub-events
      if (now - task.loggedAt > 650 + Math.random() * 400 && state.queueProgress < 0.95) {
        task.loggedAt = now;
        emitSubLog(task);
      }

      // Complete task
      if (state.queueProgress >= 1) {
        task.status = 'done';
        applyReward(task);
        pushLog('ok', `✓ ${task.label} · ${rewardText(task)}`, task.layer);
        // Advance to next selected task, marking skipped ones
        let next = state.queueIdx + 1;
        while (next < state.tasks.length && !state.tasks[next].selected) {
          state.tasks[next].status = 'skipped';
          next++;
        }
        state.queueIdx = next;
        if (state.queueIdx >= state.tasks.length) {
          // Finished all
          state.running = false;
          state.lastRunAt = Date.now();
          state.nextRunAt = Date.now() + 6 * 3600 * 1000;
          pushLog('ok', `Run complete. ${tasksDoneCount()} tasks · ${rewardsTotal()}. Next run in 6h.`, 'system');
        } else {
          state.tasks[state.queueIdx].status = 'running';
          state.queueStart = now;
          pushLog('run', `▶ ${state.tasks[state.queueIdx].label}`, state.tasks[state.queueIdx].layer);
        }
      }
    }

    // VM noise
    state.vm.cpu = Math.max(5, Math.min(70, state.vm.cpu + (Math.random() - 0.5) * 4));
    state.vm.ram = Math.max(1.8, Math.min(3.6, state.vm.ram + (Math.random() - 0.5) * 0.05));

    notify();
    requestAnimationFrame(tick);
  }

  function emitSubLog(task) {
    const samples = {
      connect:    [['info','module=memory_reader.attach pid=4820','memory'], ['info','Resolved TypeInfo_RVA=0x4DC1558','memory']],
      window:     [['info','Found "Plarium Play · Raid: Shadow Legends"','screen'], ['info','Moved window → (14,56,900,600)','screen']],
      gem_mine:   [['info','view=VillageView · clicking GemMineButton','mod']],
      shop:       [['info','Claiming 4 free offers…','mod'], ['info','+60 energy +50K silver','mod']],
      timed:      [['info','Sweeping 5m/20m/40m/60m/90m/180m rewards','screen']],
      clan:       [['info','view=ClanView · daily check-in','mod'], ['info','Treasure opened — +25K silver','mod']],
      quests_reg: [['info','Claiming 12/12 daily tasks…','mod'], ['info','Got 1 mystery shard','mod']],
      quests_adv: [['info','Weekly: 6/7 complete','mod']],
      inbox:      [['info','Inbox: 8 messages','mod'], ['info','+300 energy from Raid team','mod']],
      arena:      [['info','Opponents scanned — picked xXDragonSlayerXx (3.41M)','memory'], ['info','Battle 1/10: VICTORY in 22s','battle'], ['info','Battle 5/10: VICTORY (instant)','battle']],
      cb:         [['info','UNM ready — 2 keys available','memory'], ['info','Battle 1/2: 11.4M dmg','battle'], ['info','Battle 2/2: 11.6M dmg','battle']],
      dungeon:    [['info','Event match: Dungeon Divers · Dragon','memory'], ['info','Dragon 20 run 4/20: VICTORY (48s)','battle'], ['info','Energy 132450 → 132370','memory']],
    };
    const arr = samples[task.id] || [['info', task.label + ' step…', task.layer]];
    const pick = arr[Math.floor(Math.random() * arr.length)];
    pushLog(pick[0], pick[1], pick[2]);
  }

  function applyReward(task) {
    if (!task.reward) return;
    for (const k in task.reward) {
      const v = task.reward[k];
      if (k === 'shards') {
        state.resources.shards.mystery += v;
      } else if (k in state.resources) {
        state.resources[k] += v;
      } else if (k === 'cb_keys') {
        state.resources.cb_keys = Math.max(0, state.resources.cb_keys + v);
        state.cb.keys_used += -v;
        state.cb.damage_today += Math.round((11.2 + Math.random()*0.8) * 1e6) * (-v);
        state.cb.history[state.cb.history.length - 1].dmg = state.cb.damage_today;
      }
    }
  }
  function rewardText(task) {
    if (!task.reward) return 'no reward';
    return Object.entries(task.reward).map(([k, v]) => {
      if (k === 'shards') return `+${v} shard`;
      if (k === 'cb_keys') return `used ${-v} key`;
      if (k === 'arena_tokens') return `used ${-v} token`;
      if (k === 'energy' && v < 0) return `-${-v} energy`;
      if (k === 'silver') return `+${(v/1000).toFixed(0)}K silver`;
      return `+${v} ${k}`;
    }).join(' · ');
  }
  function tasksDoneCount() { return state.tasks.filter(t => t.status === 'done').length; }
  function rewardsTotal() { return 'earned 385 gems · 3 shards'; }

  // Kick off
  requestAnimationFrame(tick);

  // Public API
  window.PARSim = {
    state,
    subscribe(fn) {
      subs.add(fn);
      fn(state);
      return () => subs.delete(fn);
    },
    setRunning(run) {
      if (run === state.running) return;
      state.running = run;
      if (run) {
        // Reset queue if all done
        if (state.tasks.every(t => t.status === 'done')) {
          state.tasks.forEach(t => { t.status = 'pending'; t.ms = 0; });
          state.queueIdx = -1;
        }
        pushLog('info', 'Start signal received — beginning daily run.', 'system');
      } else {
        pushLog('warn', 'Paused by user.', 'system');
      }
    },
    reset() {
      state.tasks.forEach(t => { t.status = 'pending'; t.ms = 0; });
      state.queueIdx = -1;
      state.queueProgress = 0;
      state.running = false;
      pushLog('info', 'Queue reset.', 'system');
    },
    toggleSelected(taskId) {
      const t = state.tasks.find(x => x.id === taskId);
      if (t) { t.selected = !t.selected; notify(); }
    },
    setAllSelected(val) {
      state.tasks.forEach(t => { t.selected = !!val; });
      notify();
    },
  };
})();
