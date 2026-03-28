"""
Low-level pymem wrapper for reading Raid: Shadow Legends game memory.

Reads game state directly from process memory via IL2CPP pointer chains.
Provides instant battle detection, resource checking, arena opponent
evaluation, hero roster access, and screen/view identification.

All offsets are from Il2CppDumper v6.7.46 output for:
  Raid v11.30.0 | metadata v31 | Unity 6000.0.60

Architecture:
  GameAssembly.dll contains IL2CPP compiled game code.
  Two singletons provide all game state:
    - AppModel (game data: users, heroes, resources, arena, battle)
    - AppViewModel (UI state: routing, current view/screen)
  Both are accessed via SingleInstance<T>._instance static field.

Pointer chain to reach singletons:
  GA_BASE + TypeInfo_RVA -> klass ptr
    -> +0xC8 (generic class info)
    -> +0x08 (specialized klass)
    -> +0xB8 (static_fields)
    -> +0x08 (_instance)

Usage:
    reader = MemoryReader()
    reader.attach()
    print(reader.get_resources())
    print(reader.get_arena_opponents())
    print(reader.get_current_view_name())
    reader.detach()
"""

import logging
import struct
import time

import pymem
import pymem.process

logger = logging.getLogger(__name__)


# =============================================================================
# RVAs and singleton chain
# =============================================================================

# TypeInfo RVAs in GameAssembly.dll (from Il2CppDumper script.json)
APPMODEL_TYPEINFO_RVA = 0x4DC1558
APPVIEWMODEL_TYPEINFO_RVA = 0x4DC2A28

# Pointer chain from TypeInfo to singleton instance
# klass -> generic_class_info -> specialized_klass -> static_fields -> _instance
SINGLETON_CHAIN = [0xC8, 0x08, 0xB8, 0x08]


# =============================================================================
# AppModel field offsets (from dump.cs)
# =============================================================================

# AppModel -> sub-objects
APPMODEL_USER_WRAPPER = 0x1C8       # UserWrapper
APPMODEL_BATTLE_NOTIFIER = 0x108    # BattleStateNotifier

# UserWrapper -> wrappers
UW_ACCOUNT = 0x20    # AccountWrapper
UW_HEROES = 0x28     # HeroesWrapper
UW_ARENA = 0xB0      # ArenaWrapper
UW_BATTLE = 0x158    # BattleWrapper

# AccountWrapperReadOnly -> UserAccount
ACCTWRAP_DATA = 0x20
USERACCT_POWER = 0x18       # double TotalPower
USERACCT_LEVEL = 0x30       # int Level
USERACCT_RESOURCES = 0x60   # Resources object

# Resources -> Dictionary<ResourceTypeId, double>
RESOURCES_RAWVALUES = 0x10

# HeroesWrapperReadOnly -> UserHeroData
HEROESWRAP_DATA = 0x88          # UpdatableHeroData (inherits UserHeroData)
HERODATA_HEROBYID = 0x18        # Dictionary<int, Hero>

# Hero fields
HERO_ID = 0x18          # int
HERO_TYPEID = 0x1C      # int
HERO_GRADE = 0x20       # HeroGrade enum (1-6 stars)
HERO_LEVEL = 0x24       # int (1-60)
HERO_EXP = 0x28         # int
HERO_EMPOWER = 0x30     # int (empowerment level)
HERO_LOCKED = 0x34      # bool
HERO_INSTORAGE = 0x35   # bool

# ArenaWrapperReadOnly -> UserArenaData
ARENAWRAP_DATA = 0x40
ARENA_POINTS = 0x10             # long
ARENA_OPPONENTS = 0x18          # List<ArenaOpponent>

# ArenaOpponent fields
OPP_STATUS = 0x18       # ArenaOpponentStatus enum
OPP_POINTS = 0x20       # long ArenaPoints (opponent's rating)
OPP_TEAM = 0x28         # TeamSetup
OPP_NAME = 0x48         # IL2CPP string

# TeamSetup fields
TEAM_POWER = 0x10       # int CombatPower

# BattleStateNotifier
BATTLE_STATE = 0x28     # BattleProcessingState enum


# =============================================================================
# AppViewModel field offsets
# =============================================================================

# AppViewModel -> RoutingManager -> TokensChain -> List -> OpenedNodeMeta
AVM_ROUTING = 0x18          # RoutingManager
ROUTING_ACTIVE_BRANCH = 0x18  # TokensChain (_activeBranch)
CHAIN_LIST = 0x10           # List<OpenedNodeMeta> (_list)
NODE_VIEWKEY = 0x10         # ViewKey enum (int)


# =============================================================================
# Enums
# =============================================================================

# BattleProcessingState
BATTLE_START_CMD = 0
BATTLE_START_SUCCEED = 1
BATTLE_PRE_INIT = 2
BATTLE_LOADING = 3
BATTLE_WAITING = 4
BATTLE_STARTED = 5
BATTLE_FINISHED = 6
BATTLE_UNLOADING = 7
BATTLE_STOPPED = 8

# ArenaOpponentStatus
OPP_NONE = 0        # Available to fight
OPP_DEFEATED = 1    # We lost to them
OPP_WON = 2         # We beat them

# ResourceTypeId (key values in Resources.RawValues dictionary)
RES_ENERGY = 1
RES_SILVER = 2
RES_ARENA_TOKEN = 3
RES_GEM = 4
RES_ARENA_3X3 = 6
RES_LIVE_ARENA = 7
RES_CB_KEY = 300
RES_AUTO_TICKET = 400

RESOURCE_NAMES = {
    RES_ENERGY: "energy",
    RES_SILVER: "silver",
    RES_ARENA_TOKEN: "arena_tokens",
    RES_GEM: "gems",
    RES_CB_KEY: "cb_keys",
    RES_ARENA_3X3: "arena_3x3_tokens",
    RES_LIVE_ARENA: "live_arena_tokens",
    RES_AUTO_TICKET: "auto_tickets",
}

# ViewKey (key screens — full list of 497 in offsets/viewkeys.json)
VIEW_VILLAGE = 1032
VIEW_VILLAGE_HUD = 1033
VIEW_GEM_MINE = 1034
VIEW_SHOP = 1038
VIEW_INBOX = 1042
VIEW_QUESTS = 1049
VIEW_ARENA = 1051
VIEW_BATTLE_HUD = 1015
VIEW_BATTLE_LOADING = 1012
VIEW_BATTLE_FINISH_ARENA = 1014
VIEW_BATTLE_FINISH_STORY = 1013
VIEW_BATTLE_FINISH_DUNGEON = 1063
VIEW_BATTLE_FINISH_CB = 1100
VIEW_HERO_SELECT_ARENA = 1011
VIEW_HERO_SELECT_CB = 1072
VIEW_BATTLE_MODE_SELECT = 1022
VIEW_CB_SCREEN = 1071

VIEW_NAMES = {
    0: "None",
    1011: "HeroSelectArena", 1012: "BattleLoading",
    1013: "BattleFinishStory", 1014: "BattleFinishArena",
    1015: "BattleHUD", 1022: "BattleModeSelect",
    1032: "Village", 1033: "VillageHUD",
    1034: "GemMine", 1038: "Shop",
    1042: "Inbox", 1049: "Quests",
    1051: "Arena", 1063: "BattleFinishDungeon",
    1071: "ClanBoss", 1072: "HeroSelectCB",
    1100: "BattleFinishCB", 1143: "AllianceActivityHUD",
}


# =============================================================================
# IL2CPP memory layout constants
# =============================================================================

# C# Dictionary<TKey, TValue> internal layout
DICT_ENTRIES = 0x18     # Entry[] _entries
DICT_COUNT = 0x20       # int _count

# IL2CPP array header (klass + monitor + bounds + max_length)
ARRAY_HEADER = 0x20

# Dictionary entry sizes:
#   Entry<int, double>: hashCode(4) + next(4) + key(4) + pad(4) + value(8) = 24
#   Entry<int, object>: hashCode(4) + next(4) + key(4) + pad(4) + value(8) = 24
DICT_ENTRY_SIZE = 24
ENTRY_KEY_OFF = 8
ENTRY_VAL_OFF = 16


# =============================================================================
# MemoryReader
# =============================================================================

class MemoryReader:
    """
    Reads Raid: Shadow Legends game state from process memory.

    Attaches to Raid.exe, resolves AppModel and AppViewModel singletons,
    and provides typed accessors for resources, heroes, arena, battle
    state, and current screen view.
    """

    def __init__(self):
        self.pm = None
        self.ga_base = 0
        self._app_model = 0
        self._uw = 0          # UserWrapper cache
        self._avm = 0         # AppViewModel cache

    @property
    def is_attached(self):
        return self.pm is not None

    # --- Attach / Detach ---

    def attach(self, max_retries=5, retry_delay=10):
        """Attach to Raid.exe and resolve game singletons.
        Retries if the game isn't fully loaded yet (common after VM boot).
        """
        for attempt in range(max_retries):
            try:
                if not self.pm:
                    self.pm = pymem.Pymem("Raid.exe")
                    ga = pymem.process.module_from_name(
                        self.pm.process_handle, "GameAssembly.dll"
                    )
                    self.ga_base = ga.lpBaseOfDll
                    logger.info(f"Attached to Raid.exe (PID {self.pm.process_id})")

                self._resolve_app_model()
                self._resolve_app_view_model()
                logger.info(f"AppModel @ {hex(self._app_model)}")
                return True
            except pymem.exception.ProcessNotFound:
                logger.error("Raid.exe not found")
                return False
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Attach attempt {attempt + 1}/{max_retries} failed: {e}. "
                        f"Retrying in {retry_delay}s..."
                    )
                    time.sleep(retry_delay)
                else:
                    logger.error(f"Attach failed after {max_retries} attempts: {e}")
                    return False

    def detach(self):
        """Close process handle and clear cached pointers."""
        if self.pm:
            try:
                self.pm.close_process()
            except Exception:
                pass
            self.pm = None
            self._app_model = 0
            self._uw = 0
            self._avm = 0

    # --- Low-level pointer helpers ---

    def _ptr(self, addr):
        """Read a 64-bit pointer. Returns 0 if null or invalid."""
        try:
            v = self.pm.read_ulonglong(addr)
            return v if v and v > 0x10000 else 0
        except Exception:
            return 0

    def _chain(self, base, offsets):
        """Follow a chain of pointer dereferences from base."""
        p = base
        for o in offsets:
            p = self._ptr(p + o)
            if not p:
                return 0
        return p

    # --- Singleton resolution ---

    def _resolve_app_model(self):
        """Find AppModel singleton via TypeInfo -> static fields."""
        ti = self._ptr(self.ga_base + APPMODEL_TYPEINFO_RVA)
        if not ti:
            raise RuntimeError("AppModel TypeInfo null")
        self._app_model = self._chain(ti, SINGLETON_CHAIN)
        if not self._app_model:
            raise RuntimeError("AppModel singleton not found")
        self._uw = self._ptr(self._app_model + APPMODEL_USER_WRAPPER)
        if not self._uw:
            raise RuntimeError("UserWrapper null")

    def _resolve_app_view_model(self):
        """Find AppViewModel singleton for view/screen tracking."""
        ti = self._ptr(self.ga_base + APPVIEWMODEL_TYPEINFO_RVA)
        if ti:
            self._avm = self._chain(ti, SINGLETON_CHAIN)

    # --- IL2CPP type readers ---

    def _read_il2cpp_string(self, str_ptr):
        """Read a C# string (UTF-16 with length prefix at +0x10)."""
        if not str_ptr:
            return ""
        try:
            length = self.pm.read_int(str_ptr + 0x10)
            if length <= 0 or length > 200:
                return ""
            raw = self.pm.read_bytes(str_ptr + 0x14, length * 2)
            return raw.decode('utf-16-le', errors='replace')
        except Exception:
            return ""

    def _read_list_ptrs(self, list_ptr, max_items=200):
        """Read a C# List<T> and return element pointers."""
        if not list_ptr:
            return []
        items = self._ptr(list_ptr + 0x10)    # _items array
        size = self.pm.read_int(list_ptr + 0x18)  # _size
        if not items or size <= 0:
            return []
        return [
            p for i in range(min(size, max_items))
            if (p := self._ptr(items + ARRAY_HEADER + i * 8))
        ]

    def _read_dict_int_double(self, dict_ptr):
        """Read Dictionary<int, double> -> {int: float}."""
        if not dict_ptr:
            return {}
        entries = self._ptr(dict_ptr + DICT_ENTRIES)
        count = self.pm.read_int(dict_ptr + DICT_COUNT)
        if not entries or count <= 0:
            return {}
        result = {}
        for i in range(min(count, 500)):
            addr = entries + ARRAY_HEADER + i * DICT_ENTRY_SIZE
            try:
                if self.pm.read_int(addr) < 0:  # deleted entry
                    continue
                key = self.pm.read_int(addr + ENTRY_KEY_OFF)
                val = struct.unpack('d', self.pm.read_bytes(addr + ENTRY_VAL_OFF, 8))[0]
                result[key] = val
            except Exception:
                continue
        return result

    def _read_dict_int_obj(self, dict_ptr, max_items=500):
        """Read Dictionary<int, T> -> [(key, value_ptr)]."""
        if not dict_ptr:
            return []
        entries = self._ptr(dict_ptr + DICT_ENTRIES)
        count = self.pm.read_int(dict_ptr + DICT_COUNT)
        if not entries or count <= 0:
            return []
        items = []
        for i in range(min(count, max_items)):
            addr = entries + ARRAY_HEADER + i * DICT_ENTRY_SIZE
            try:
                if self.pm.read_int(addr) < 0:
                    continue
                key = self.pm.read_int(addr + ENTRY_KEY_OFF)
                val = self._ptr(addr + ENTRY_VAL_OFF)
                if val:
                    items.append((key, val))
            except Exception:
                continue
        return items

    # =========================================================================
    # Resources
    # =========================================================================

    def get_resources(self):
        """Read all resources as a named dict."""
        acct = self._chain(self._uw, [UW_ACCOUNT, ACCTWRAP_DATA])
        res = self._ptr(acct + USERACCT_RESOURCES)
        raw = self._read_dict_int_double(self._ptr(res + RESOURCES_RAWVALUES))
        return {name: raw.get(rid, 0.0) for rid, name in RESOURCE_NAMES.items()}

    def get_account_level(self):
        acct = self._chain(self._uw, [UW_ACCOUNT, ACCTWRAP_DATA])
        return self.pm.read_int(acct + USERACCT_LEVEL)

    def get_total_power(self):
        acct = self._chain(self._uw, [UW_ACCOUNT, ACCTWRAP_DATA])
        return struct.unpack('d', self.pm.read_bytes(acct + USERACCT_POWER, 8))[0]

    def has_arena_tokens(self, minimum=1):
        return self.get_resources().get("arena_tokens", 0) >= minimum

    def has_cb_keys(self, minimum=1):
        return self.get_resources().get("cb_keys", 0) >= minimum

    def has_energy(self, minimum=1):
        return self.get_resources().get("energy", 0) >= minimum

    # =========================================================================
    # Battle State
    # =========================================================================

    def get_battle_state(self):
        """Read BattleProcessingState enum value.
        0=StartCmd, 5=Started, 6=Finished, 8=Stopped."""
        notifier = self._ptr(self._app_model + APPMODEL_BATTLE_NOTIFIER)
        if not notifier:
            return -1
        return self.pm.read_int(notifier + BATTLE_STATE)

    def is_in_battle(self):
        """True if a battle is currently active."""
        vk = self.get_current_view()
        if vk == VIEW_BATTLE_HUD:
            return True
        state = self.get_battle_state()
        return state in (BATTLE_LOADING, BATTLE_WAITING, BATTLE_STARTED)

    def is_battle_finished(self):
        state = self.get_battle_state()
        return state in (BATTLE_FINISHED, BATTLE_UNLOADING, BATTLE_STOPPED)

    def wait_for_battle_end(self, timeout=300, poll_interval=2):
        """Wait for battle to start then finish. Handles both normal
        and instant/quick battles.

        For normal battles: waits for state to go Started -> Finished.
        For instant battles: detects Finished state directly.
        Returns the final BattleProcessingState value, or -1 on timeout.
        """
        start = time.time()

        # Phase 1: Wait for battle to become active (state <= Started)
        # This prevents false positives from stale Stopped state
        logger.info("Waiting for battle to start...")
        while time.time() - start < 60:
            state = self.get_battle_state()
            if state <= BATTLE_STARTED:
                logger.info(f"Battle active (state={state})")
                break
            time.sleep(poll_interval)
        else:
            # Might be an instant fight — check if state went to Finished
            state = self.get_battle_state()
            if state == BATTLE_FINISHED:
                logger.info("Instant fight detected (state=Finished)")
                return state
            logger.warning("Battle never started (60s timeout)")
            return -1

        # Phase 2: Wait for battle to finish (state >= Finished)
        logger.info("Waiting for battle to end...")
        while time.time() - start < timeout:
            state = self.get_battle_state()
            if state >= BATTLE_FINISHED:
                elapsed = time.time() - start
                logger.info(f"Battle ended (state={state}) in {elapsed:.0f}s")
                return state
            time.sleep(poll_interval)

        logger.warning(f"Battle timeout after {timeout}s")
        return -1

    def wait_for_battle_or_view_change(self, from_view, keys_before=None, timeout=120):
        """Wait for battle completion via any signal:
        battle state, ViewKey change, or resource consumption.
        Best for instant/quick fights where state transitions are fast.
        """
        start = time.time()
        while time.time() - start < timeout:
            # Check battle state
            state = self.get_battle_state()
            if state == BATTLE_FINISHED:
                return {"method": "battle_state", "elapsed": time.time() - start}

            # Check ViewKey changed from starting view
            vk = self.get_current_view()
            if vk != from_view and vk > 0:
                return {"method": "view_change", "view": vk, "elapsed": time.time() - start}

            # Check if CB keys decreased (for instant CB fights)
            if keys_before is not None:
                keys_now = int(self.get_resources().get("cb_keys", keys_before))
                if keys_now < keys_before:
                    return {"method": "key_consumed", "elapsed": time.time() - start}

            time.sleep(1)

        return {"method": "timeout", "elapsed": timeout}

    # =========================================================================
    # Heroes
    # =========================================================================

    def get_heroes(self):
        """Read all heroes as a list of dicts."""
        heroes_wrap = self._ptr(self._uw + UW_HEROES)
        hero_data = self._ptr(heroes_wrap + HEROESWRAP_DATA)
        hero_dict = self._ptr(hero_data + HERODATA_HEROBYID)
        entries = self._read_dict_int_obj(hero_dict)
        heroes = []
        for _, ptr in entries:
            try:
                h = {
                    "id": self.pm.read_int(ptr + HERO_ID),
                    "type_id": self.pm.read_int(ptr + HERO_TYPEID),
                    "grade": self.pm.read_int(ptr + HERO_GRADE),
                    "level": self.pm.read_int(ptr + HERO_LEVEL),
                    "empower": self.pm.read_int(ptr + HERO_EMPOWER),
                    "locked": self.pm.read_bytes(ptr + HERO_LOCKED, 1)[0] != 0,
                    "in_storage": self.pm.read_bytes(ptr + HERO_INSTORAGE, 1)[0] != 0,
                }
                if 1 <= h["grade"] <= 6 and 1 <= h["level"] <= 60:
                    heroes.append(h)
            except Exception:
                continue
        return heroes

    # =========================================================================
    # Arena
    # =========================================================================

    def get_arena_opponents(self):
        """Read arena opponents with name, power, points, and status."""
        arena_wrap = self._ptr(self._uw + UW_ARENA)
        arena_data = self._ptr(arena_wrap + ARENAWRAP_DATA)
        if not arena_data:
            return []
        opp_list = self._ptr(arena_data + ARENA_OPPONENTS)
        opp_ptrs = self._read_list_ptrs(opp_list)
        opponents = []
        for ptr in opp_ptrs:
            try:
                status = self.pm.read_int(ptr + OPP_STATUS)
                points = self.pm.read_longlong(ptr + OPP_POINTS)
                name = self._read_il2cpp_string(self._ptr(ptr + OPP_NAME))
                team = self._ptr(ptr + OPP_TEAM)
                power = self.pm.read_int(team + TEAM_POWER) if team else 0
                opponents.append({
                    "name": name,
                    "power": power,
                    "points": points,
                    "status": status,
                    "available": status == OPP_NONE,
                })
            except Exception:
                continue
        return opponents

    def get_weakest_available_opponent(self):
        """Find the weakest undefeated opponent.
        Returns (index, opponent_dict) or (-1, None).
        """
        opps = self.get_arena_opponents()
        available = [(i, o) for i, o in enumerate(opps) if o["available"]]
        if not available:
            return -1, None
        available.sort(key=lambda x: x[1]["power"])
        return available[0]

    def get_arena_points(self):
        arena_wrap = self._ptr(self._uw + UW_ARENA)
        arena_data = self._ptr(arena_wrap + ARENAWRAP_DATA)
        return self.pm.read_longlong(arena_data + ARENA_POINTS) if arena_data else 0

    # =========================================================================
    # View / Screen Detection
    # =========================================================================

    def get_current_view(self):
        """Read the current ViewKey from the navigation routing chain.
        Returns the ViewKey int, or -1 on failure.
        """
        if not self._avm:
            self._resolve_app_view_model()
        if not self._avm:
            return -1
        routing = self._ptr(self._avm + AVM_ROUTING)
        branch = self._ptr(routing + ROUTING_ACTIVE_BRANCH)
        chain_list = self._ptr(branch + CHAIN_LIST)
        if not chain_list:
            return -1
        items = self._ptr(chain_list + 0x10)      # List._items
        size = self.pm.read_int(chain_list + 0x18)  # List._size
        if size <= 0 or not items:
            return -1
        last_node = self._ptr(items + ARRAY_HEADER + (size - 1) * 8)
        if not last_node:
            return -1
        return self.pm.read_int(last_node + NODE_VIEWKEY)

    def get_current_view_name(self):
        vk = self.get_current_view()
        return VIEW_NAMES.get(vk, f"Unknown({vk})")

    def is_at_village(self):
        return self.get_current_view() in (VIEW_VILLAGE, VIEW_VILLAGE_HUD)

    def is_at_battle_results(self):
        return self.get_current_view() in (
            VIEW_BATTLE_FINISH_ARENA, VIEW_BATTLE_FINISH_STORY,
            VIEW_BATTLE_FINISH_DUNGEON, VIEW_BATTLE_FINISH_CB,
        )

    def wait_for_view(self, target_view, timeout=30, poll_interval=0.5):
        """Wait until current view matches target. Returns True if reached."""
        start = time.time()
        while time.time() - start < timeout:
            if self.get_current_view() == target_view:
                return True
            time.sleep(poll_interval)
        return False

    # =========================================================================
    # Snapshot
    # =========================================================================

    def get_snapshot(self):
        """Full account snapshot for logging / before-after comparison."""
        try:
            return {
                "level": self.get_account_level(),
                "power": int(self.get_total_power()),
                "resources": self.get_resources(),
                "hero_count": len(self.get_heroes()),
                "arena_points": self.get_arena_points(),
                "battle_state": self.get_battle_state(),
                "current_view": self.get_current_view_name(),
            }
        except Exception as e:
            logger.error(f"Snapshot failed: {e}")
            return None
