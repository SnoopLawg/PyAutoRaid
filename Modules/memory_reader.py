"""
Low-level pymem wrapper for reading Raid: Shadow Legends game memory.

Reads game state directly from process memory via IL2CPP pointer chains.
Provides instant battle detection, resource checking, arena opponent
evaluation, hero roster access, and screen/view identification.

Offset resolution (priority order):
  1. MelonLoader mod API (/offsets) — auto-detects singleton pointers
     and field offsets at runtime. Immune to game version updates.
  2. Hardcoded RVAs + offsets — fallback for when mod is unavailable.
     These are from Il2CppDumper output and need manual update per version.

Architecture:
  GameAssembly.dll contains IL2CPP compiled game code.
  Two singletons provide all game state:
    - AppModel (game data: users, heroes, resources, arena, battle)
    - AppViewModel (UI state: routing, current view/screen)
  Both are accessed via SingleInstance<T>._instance static field.

Pointer chain to reach singletons (fallback only):
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

import json
import logging
import struct
import time
import urllib.request

import pymem
import pymem.process

logger = logging.getLogger(__name__)


# =============================================================================
# RVAs and singleton chain
# =============================================================================

# TypeInfo RVAs in GameAssembly.dll (from Il2CppDumper script.json)
APPMODEL_TYPEINFO_RVA = 0x4DEE858      # Il2CppDumper script.json 2026-04-19 (Unity 6000.0.60f1)
APPVIEWMODEL_TYPEINFO_RVA = 0x4DEFD28

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
HERO_TYPE_PTR = 0x10    # HeroType* (for name/faction/rarity lookup)
HERO_ID = 0x18          # int
HERO_TYPEID = 0x1C      # int
HERO_GRADE = 0x20       # HeroGrade enum (1-6 stars)
HERO_LEVEL = 0x24       # int (1-60)
HERO_EXP = 0x28         # int
HERO_EMPOWER = 0x30     # int (empowerment level)
HERO_LOCKED = 0x34      # bool
HERO_INSTORAGE = 0x35   # bool

# Hero extended fields
HERO_SKILLS = 0x60      # List<Skill>
HERO_MASTERY = 0x68     # HeroMasteryData
HERO_DBLASCEND = 0x70   # HeroDoubleAscendData
HERO_POWER = 0x78       # Nullable<double> Power

# Skill fields
SKILL_TYPEID = 0x1C     # int TypeId
SKILL_LEVEL = 0x20      # int Level

# HeroMasteryData fields
MASTERY_LIST = 0x20     # List<int> Masteries

# HeroDoubleAscendData fields
DBLASCEND_GRADE = 0x10      # DoubleAscendGrade enum
DBLASCEND_BLESSINGID = 0x14 # Nullable<BlessingTypeId>

# HeroType fields (via Hero._type pointer)
HEROTYPE_NAME = 0x18    # SharedLTextKey -> .DefaultValue (+0x18) = champion name
HEROTYPE_FRACTION = 0x3C  # HeroFraction enum (verified live)
HEROTYPE_RARITY = 0x40   # HeroRarity enum (verified live)
HEROTYPE_LEADERSKILLS = 0x48  # List<LeaderSkill>
HEROTYPE_FORMS = 0x88   # HeroForm[] (verified via live probing)

# LeaderSkill fields
LS_STATKIND = 0x10      # StatKindId
LS_ISABSOLUTE = 0x14    # bool
LS_AMOUNT = 0x18        # Fixed
LS_AREA = 0x20          # Nullable<AreaTypeId>

# HeroForm fields (from HeroType.Forms array)
HEROFORM_ELEMENT = 0x10     # Element enum
HEROFORM_ROLE = 0x14        # HeroRole enum
HEROFORM_BASESTATS = 0x18   # BattleStats (inline object ptr)

# BattleStats field offsets (all Fixed type = long with 32 fractional bits)
BS_HEALTH = 0x10
BS_ATTACK = 0x18
BS_DEFENCE = 0x20
BS_SPEED = 0x28
BS_RESISTANCE = 0x30
BS_ACCURACY = 0x38
BS_CRITCHANCE = 0x40
BS_CRITDAMAGE = 0x48
BS_CRITHEAL = 0x50
BS_IGNOREDEF = 0x58

# ArtifactBonus fields
ARTBONUS_KINDID = 0x10      # StatKindId enum
ARTBONUS_VALUE = 0x18       # BonusValue ptr
ARTBONUS_POWERUP = 0x20     # Fixed _powerUpValue
ARTBONUS_LEVEL = 0x38       # int _level

# BonusValue fields
BONUSVAL_ISABSOLUTE = 0x10  # bool (true=flat, false=%)
BONUSVAL_VALUE = 0x18       # Fixed

# EquipmentWrapper -> UserArtifactData
EQUIPWRAP_ARTDATA = 0x60    # UserArtifactData
ARTDATA_ARTIFACTS = 0x28    # List<Artifact> (all artifacts)
ARTDATA_BYHERO = 0x30       # Dictionary<int, HeroArtifactData>
HEROARTDATA_BYKIND = 0x10   # Dictionary<ArtifactKindId, int>

# Capitol (Great Hall)
UW_CAPITOL = 0xC8           # CapitolWrapper
CAPITOLWRAP_VILLAGEDATA = 0x18  # UpdatableVillageData (inherits UserVillageData)
VILLAGEDATA_BONUSES = 0x30  # Dictionary<Element, Dictionary<StatKindId, int>>

# Artifact fields
ART_ID = 0x10           # int
ART_SELL_PRICE = 0x28   # int
ART_LEVEL = 0x30        # int (0-16)
ART_KIND = 0x40         # ArtifactKindId enum (weapon/helmet/shield/etc)
ART_RANK = 0x44         # ArtifactRankId enum (1-6 stars)
ART_RARITY = 0x48       # ItemRarity enum (common-legendary)
ART_PRIMARY = 0x50      # ArtifactBonus ptr (primary stat)
ART_SECONDARIES = 0x58  # List<ArtifactBonus> (substats)
ART_SET = 0x68          # ArtifactSetKindId enum

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

# Fixed-point conversion: Fixed uses 32 fractional bits, so value = raw_long / 2^32
FIXED_SCALE = 4294967296.0  # 2^32

# StatKindId enum
STAT_HEALTH = 1
STAT_ATTACK = 2
STAT_DEFENCE = 3
STAT_SPEED = 4
STAT_RESISTANCE = 5
STAT_ACCURACY = 6
STAT_CRITCHANCE = 7
STAT_CRITDAMAGE = 8
STAT_CRITHEAL = 9
STAT_IGNOREDEF = 10

STAT_NAMES = {
    STAT_HEALTH: "HP", STAT_ATTACK: "ATK", STAT_DEFENCE: "DEF",
    STAT_SPEED: "SPD", STAT_RESISTANCE: "RES", STAT_ACCURACY: "ACC",
    STAT_CRITCHANCE: "CR%", STAT_CRITDAMAGE: "CD%",
    STAT_CRITHEAL: "C.HEAL", STAT_IGNOREDEF: "IGN.DEF",
}

# Element (affinity) enum
ELEMENT_MAGIC = 0    # Blue / Magic
ELEMENT_FORCE = 1    # Red / Force
ELEMENT_SPIRIT = 2   # Green / Spirit
ELEMENT_VOID = 3     # Purple / Void

ELEMENT_NAMES = {0: "Magic", 1: "Force", 2: "Spirit", 3: "Void"}

# HeroRole enum
ROLE_NAMES = {0: "Attack", 1: "Defense", 2: "HP", 3: "Support"}

# ArtifactSetKindId enum (key sets for CB)
SET_NAMES = {
    0: "None", 1: "HP", 2: "ATK", 3: "DEF", 4: "Speed", 5: "CritRate",
    6: "CritDmg", 7: "ACC", 8: "RES", 9: "Lifesteal",
    10: "Savage", 11: "Sleep", 12: "BlockHeal", 13: "Freeze",
    14: "Stamina", 15: "Heal", 16: "BlockDebuff", 17: "Shield",
    18: "Relentless", 19: "IgnoreDEF", 20: "DecMaxHP", 21: "Stun",
    22: "Toxic", 23: "Provoke", 24: "Counterattack", 25: "CounterCrit",
    26: "AoEDmgReduce", 27: "CooldownReduce", 28: "CritHeal",
    29: "SavageFury", 30: "Regeneration", 31: "ShieldATK", 32: "ShieldCR",
    33: "ShieldHP", 34: "ShieldSPD", 35: "Unkillable",
    36: "ReflexBlock", 37: "StalwartHP", 38: "AccSPD", 39: "LethCrit",
    40: "ResBlockDebuff", 41: "AtkCR", 42: "FreezeResist", 43: "CritLifesteal",
    44: "StoneguardHP", 45: "ResDEF", 46: "CritIgnoreDEF", 47: "SwiftParry",
    48: "StoneskinHPResDef", 49: "CritDmgSPD", 50: "SPDIgnoreDef",
    51: "GuardianHP2", 52: "DefAoEReduce", 53: "SPDCooldown",
    54: "CritDmgHPScale", 55: "StaminaSPDAcc", 56: "CritDmgIgnoreDefCD",
}

RARITY_NAMES = {1: "Common", 2: "Uncommon", 3: "Rare", 4: "Epic", 5: "Legendary", 6: "Mythical"}
FACTION_NAMES = {
    0: "Unknown", 1: "BannerLords", 2: "HighElves", 3: "SacredOrder",
    4: "CovenOfMagi", 5: "OgrynTribes", 6: "LizardMen", 7: "Skinwalkers",
    8: "Orcs", 9: "Demonspawn", 10: "UndeadHordes", 11: "DarkElves",
    12: "KnightsRevenant", 13: "Barbarians", 14: "SylvanWatchers",
    15: "Samurai", 16: "Dwarves", 17: "Olympians",
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

    def _fetch_mod_offsets(self):
        """Try to get singleton pointers from the MelonLoader mod API.
        Returns True if singletons were resolved via mod, False otherwise.
        """
        try:
            resp = urllib.request.urlopen("http://localhost:6790/offsets", timeout=5)
            data = json.loads(resp.read().decode())
            types = data.get("types", {})

            am = types.get("AppModel", {}).get("instance")
            avm = types.get("AppViewModel", {}).get("instance")

            if am and avm:
                self._app_model = int(am, 16)
                self._avm = int(avm, 16)
                # Cache UserWrapper pointer
                self._uw = self._ptr(self._app_model + APPMODEL_USER_WRAPPER)
                logger.info(
                    f"Mod API resolved singletons: "
                    f"AppModel={am}, AppViewModel={avm}"
                )
                return True
            logger.debug("Mod API responded but singletons not available")
        except Exception as e:
            logger.debug(f"Mod API offsets unavailable: {e}")
        return False

    def attach(self, max_retries=5, retry_delay=10):
        """Attach to Raid.exe and resolve game singletons.
        Tries mod API first for version-independent offset resolution,
        falls back to hardcoded TypeInfo RVAs if mod is unavailable.
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

                # Try mod API first (auto-detects offsets for any game version)
                if self._fetch_mod_offsets():
                    logger.info(f"AppModel @ {hex(self._app_model)} (via mod API)")
                    return True

                # Fallback: hardcoded RVA chain (version-specific)
                logger.warning("Falling back to hardcoded RVAs (may be stale)")
                self._resolve_app_model()
                self._resolve_app_view_model()
                logger.info(f"AppModel @ {hex(self._app_model)} (via RVA chain)")
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

    def _read_fixed(self, addr):
        """Read a Fixed value (64-bit fixed-point with 32 fractional bits)."""
        try:
            raw = struct.unpack('<q', self.pm.read_bytes(addr, 8))[0]
            return raw / FIXED_SCALE
        except Exception:
            return 0.0

    def _read_battle_stats(self, bs_ptr):
        """Read a BattleStats object into a dict. All fields are Fixed type.
        Note: CR/CD/C.HEAL/IGN.DEF are stored as whole percentages (e.g. 15.0 = 15%).
        """
        if not bs_ptr:
            return {}
        return {
            "HP": self._read_fixed(bs_ptr + BS_HEALTH),
            "ATK": self._read_fixed(bs_ptr + BS_ATTACK),
            "DEF": self._read_fixed(bs_ptr + BS_DEFENCE),
            "SPD": self._read_fixed(bs_ptr + BS_SPEED),
            "RES": self._read_fixed(bs_ptr + BS_RESISTANCE),
            "ACC": self._read_fixed(bs_ptr + BS_ACCURACY),
            "CR%": self._read_fixed(bs_ptr + BS_CRITCHANCE),
            "CD%": self._read_fixed(bs_ptr + BS_CRITDAMAGE),
            "C.HEAL": self._read_fixed(bs_ptr + BS_CRITHEAL),
            "IGN.DEF": self._read_fixed(bs_ptr + BS_IGNOREDEF),
        }
        # CR/CD values: 15.0 means 15%, 63.0 means 63% — they are whole numbers

    def _read_list_ints(self, list_ptr, max_items=200):
        """Read a C# List<int> and return int values."""
        if not list_ptr:
            return []
        items_arr = self._ptr(list_ptr + 0x10)  # _items array
        size = self.pm.read_int(list_ptr + 0x18)  # _size
        if not items_arr or size <= 0:
            return []
        result = []
        for i in range(min(size, max_items)):
            try:
                val = self.pm.read_int(items_arr + ARRAY_HEADER + i * 4)
                result.append(val)
            except Exception:
                continue
        return result

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

    def _read_hero_name(self, hero_ptr):
        """Read champion name from Hero._type -> HeroType.Name.DefaultValue."""
        hero_type = self._ptr(hero_ptr + HERO_TYPE_PTR)
        if not hero_type:
            return ""
        name_key = self._ptr(hero_type + HEROTYPE_NAME)  # SharedLTextKey
        if not name_key:
            return ""
        name_str = self._ptr(name_key + 0x18)  # .DefaultValue
        return self._read_il2cpp_string(name_str)

    def _read_hero_type_info(self, hero_ptr):
        """Read faction and rarity from Hero._type -> HeroType."""
        hero_type = self._ptr(hero_ptr + HERO_TYPE_PTR)
        if not hero_type:
            return "", ""
        frac = self.pm.read_int(hero_type + HEROTYPE_FRACTION)
        rar = self.pm.read_int(hero_type + HEROTYPE_RARITY)
        return FACTION_NAMES.get(frac, f"?{frac}"), RARITY_NAMES.get(rar, f"?{rar}")

    def get_heroes(self, with_names=True):
        """Read all heroes. Set with_names=False for faster reads."""
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
                if not (1 <= h["grade"] <= 6 and 1 <= h["level"] <= 60):
                    continue
                if with_names:
                    h["name"] = self._read_hero_name(ptr)
                    h["faction"], h["rarity"] = self._read_hero_type_info(ptr)
                heroes.append(h)
            except Exception:
                continue
        return heroes

    def _read_hero_base_stats(self, hero_ptr):
        """Read base stats from Hero._type -> HeroType.Forms[0].BaseStats."""
        hero_type = self._ptr(hero_ptr + HERO_TYPE_PTR)
        if not hero_type:
            return {}
        forms_arr = self._ptr(hero_type + HEROTYPE_FORMS)
        if not forms_arr:
            return {}
        # Forms is a C# array — read first element (default form)
        form_ptr = self._ptr(forms_arr + ARRAY_HEADER)
        if not form_ptr:
            return {}
        # BaseStats is an object pointer inside HeroForm
        bs_ptr = self._ptr(form_ptr + HEROFORM_BASESTATS)
        stats = self._read_battle_stats(bs_ptr)
        # Also read element and role from the form
        try:
            stats["element"] = self.pm.read_int(form_ptr + HEROFORM_ELEMENT)
            stats["element_name"] = ELEMENT_NAMES.get(stats["element"], "?")
            stats["role"] = self.pm.read_int(form_ptr + HEROFORM_ROLE)
            stats["role_name"] = ROLE_NAMES.get(stats["role"], "?")
        except Exception:
            pass
        return stats

    def _read_hero_skills(self, hero_ptr):
        """Read skill levels from Hero.Skills -> List<Skill>."""
        skill_list = self._ptr(hero_ptr + HERO_SKILLS)
        skill_ptrs = self._read_list_ptrs(skill_list, max_items=20)
        skills = []
        for ptr in skill_ptrs:
            try:
                skills.append({
                    "type_id": self.pm.read_int(ptr + SKILL_TYPEID),
                    "level": self.pm.read_int(ptr + SKILL_LEVEL),
                })
            except Exception:
                continue
        return skills

    def _read_hero_masteries(self, hero_ptr):
        """Read mastery IDs from Hero.MasteryData.Masteries -> List<int>."""
        mastery_data = self._ptr(hero_ptr + HERO_MASTERY)
        if not mastery_data:
            return []
        return self._read_list_ints(self._ptr(mastery_data + MASTERY_LIST))

    def _read_hero_blessing(self, hero_ptr):
        """Read blessing from Hero.DoubleAscendData."""
        da = self._ptr(hero_ptr + HERO_DBLASCEND)
        if not da:
            return None
        try:
            # Nullable<BlessingTypeId> — check hasValue first
            has_value = self.pm.read_bytes(da + DBLASCEND_BLESSINGID + 4, 1)[0]
            if has_value:
                return self.pm.read_int(da + DBLASCEND_BLESSINGID)
            return None
        except Exception:
            return None

    def _read_hero_leader_skill(self, hero_ptr):
        """Read leader skills from HeroType.LeaderSkills."""
        hero_type = self._ptr(hero_ptr + HERO_TYPE_PTR)
        if not hero_type:
            return []
        ls_list = self._ptr(hero_type + HEROTYPE_LEADERSKILLS)
        ls_ptrs = self._read_list_ptrs(ls_list, max_items=5)
        skills = []
        for ptr in ls_ptrs:
            try:
                ls = {
                    "stat": STAT_NAMES.get(
                        self.pm.read_int(ptr + LS_STATKIND), "?"
                    ),
                    "stat_id": self.pm.read_int(ptr + LS_STATKIND),
                    "is_absolute": self.pm.read_bytes(ptr + LS_ISABSOLUTE, 1)[0] != 0,
                    "amount": self._read_fixed(ptr + LS_AMOUNT),
                }
                # Read area (Nullable<AreaTypeId>)
                try:
                    area_val = self.pm.read_int(ptr + LS_AREA)
                    has_area = self.pm.read_bytes(ptr + LS_AREA + 4, 1)[0]
                    ls["area"] = area_val if has_area else None
                except Exception:
                    ls["area"] = None
                skills.append(ls)
            except Exception:
                continue
        return skills

    def get_heroes_full(self):
        """Read all heroes with full details: stats, skills, masteries, blessing."""
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
                if not (1 <= h["grade"] <= 6 and 1 <= h["level"] <= 60):
                    continue
                h["name"] = self._read_hero_name(ptr)
                h["faction"], h["rarity"] = self._read_hero_type_info(ptr)
                h["base_stats"] = self._read_hero_base_stats(ptr)
                h["skills"] = self._read_hero_skills(ptr)
                h["masteries"] = self._read_hero_masteries(ptr)
                h["blessing_id"] = self._read_hero_blessing(ptr)
                h["leader_skills"] = self._read_hero_leader_skill(ptr)
                heroes.append(h)
            except Exception:
                continue
        return heroes

    # =========================================================================
    # Artifacts (detailed)
    # =========================================================================

    def _read_artifact_bonus(self, bonus_ptr):
        """Read an ArtifactBonus (primary stat or substat)."""
        if not bonus_ptr:
            return None
        try:
            kind_id = self.pm.read_int(bonus_ptr + ARTBONUS_KINDID)
            level = self.pm.read_int(bonus_ptr + ARTBONUS_LEVEL)
            # Read BonusValue (contains isAbsolute flag and value)
            bv_ptr = self._ptr(bonus_ptr + ARTBONUS_VALUE)
            if bv_ptr:
                is_absolute = self.pm.read_bytes(bv_ptr + BONUSVAL_ISABSOLUTE, 1)[0] != 0
                value = self._read_fixed(bv_ptr + BONUSVAL_VALUE)
            else:
                is_absolute = True
                value = 0.0
            return {
                "stat": STAT_NAMES.get(kind_id, f"?{kind_id}"),
                "stat_id": kind_id,
                "value": value,
                "is_flat": is_absolute,
                "level": level,
            }
        except Exception:
            return None

    def _read_artifact_full(self, art_ptr):
        """Read full artifact details including primary and substats."""
        if not art_ptr:
            return None
        try:
            art = {
                "id": self.pm.read_int(art_ptr + ART_ID),
                "level": self.pm.read_int(art_ptr + ART_LEVEL),
                "kind": self.pm.read_int(art_ptr + ART_KIND),
                "rank": self.pm.read_int(art_ptr + ART_RANK),
                "rarity": self.pm.read_int(art_ptr + ART_RARITY),
                "rarity_name": RARITY_NAMES.get(
                    self.pm.read_int(art_ptr + ART_RARITY), "?"
                ),
                "set_id": self.pm.read_int(art_ptr + ART_SET),
                "set_name": SET_NAMES.get(
                    self.pm.read_int(art_ptr + ART_SET), "?"
                ),
            }
            if not (0 <= art["level"] <= 16 and 1 <= art["rank"] <= 6):
                return None

            # Primary bonus
            primary_ptr = self._ptr(art_ptr + ART_PRIMARY)
            art["primary"] = self._read_artifact_bonus(primary_ptr)

            # Secondary bonuses (substats)
            subs_list = self._ptr(art_ptr + ART_SECONDARIES)
            sub_ptrs = self._read_list_ptrs(subs_list, max_items=4)
            art["substats"] = []
            for sp in sub_ptrs:
                bonus = self._read_artifact_bonus(sp)
                if bonus:
                    art["substats"].append(bonus)

            return art
        except Exception:
            return None

    def _build_artifact_id_lookup(self):
        """Build a dict of artifact_id -> artifact_ptr from the equipment wrapper.
        Uses the probing approach from get_artifacts since the master list
        (UserArtifactData.Artifacts) can be empty in some game states.
        """
        equip_wrap = self._ptr(self._uw + 0x30)
        if not equip_wrap:
            return {}
        # Probe for the artifact dictionary (same approach as get_artifacts)
        for data_off in [0x60, 0x88, 0x90, 0x80, 0x78]:
            art_data = self._ptr(equip_wrap + data_off)
            if not art_data:
                continue
            for dict_off in [0x18, 0x10, 0x20]:
                art_dict = self._ptr(art_data + dict_off)
                if not art_dict:
                    continue
                try:
                    count = self.pm.read_int(art_dict + DICT_COUNT)
                    if count < 10 or count > 5000:
                        continue
                    entries = self._read_dict_int_obj(art_dict, max_items=min(count, 2000))
                    if not entries:
                        continue
                    # Validate first entry looks like an artifact
                    _, test_ptr = entries[0]
                    test_level = self.pm.read_int(test_ptr + ART_LEVEL)
                    test_rank = self.pm.read_int(test_ptr + ART_RANK)
                    if not (0 <= test_level <= 16 and 1 <= test_rank <= 6):
                        continue
                    # Build ID lookup
                    lookup = {}
                    for _, ptr in entries:
                        try:
                            aid = self.pm.read_int(ptr + ART_ID)
                            lookup[aid] = ptr
                        except Exception:
                            continue
                    logger.info(f"Built artifact lookup: {len(lookup)} artifacts")
                    return lookup
                except Exception:
                    continue
        return {}

    def get_hero_artifacts(self, hero_id, art_lookup=None):
        """Get all artifacts equipped on a specific hero.
        Returns dict of {slot_kind: artifact_dict}.
        Pass art_lookup from _build_artifact_id_lookup() to avoid rebuilding.
        """
        equip_wrap = self._ptr(self._uw + 0x30)
        if not equip_wrap:
            return {}
        art_data = self._ptr(equip_wrap + EQUIPWRAP_ARTDATA)
        if not art_data:
            return {}

        # Get hero's artifact slot mapping
        by_hero = self._ptr(art_data + ARTDATA_BYHERO)
        hero_entries = self._read_dict_int_obj(by_hero)

        hero_art_data = None
        for key, ptr in hero_entries:
            if key == hero_id:
                hero_art_data = ptr
                break
        if not hero_art_data:
            return {}

        # Read ArtifactIdByKind: Dictionary<ArtifactKindId, int>
        by_kind = self._ptr(hero_art_data + HEROARTDATA_BYKIND)
        if not by_kind:
            return {}

        entries_arr = self._ptr(by_kind + DICT_ENTRIES)
        count = self.pm.read_int(by_kind + DICT_COUNT)
        if not entries_arr or count <= 0:
            return {}

        ENTRY_SIZE_INT_INT = 16
        slot_to_art_id = {}
        for i in range(min(count, 20)):
            addr = entries_arr + ARRAY_HEADER + i * ENTRY_SIZE_INT_INT
            try:
                if self.pm.read_int(addr) < 0:
                    continue
                kind = self.pm.read_int(addr + 8)
                art_id = self.pm.read_int(addr + 12)
                slot_to_art_id[kind] = art_id
            except Exception:
                continue

        if not slot_to_art_id:
            return {}

        # Build or use cached artifact lookup
        if art_lookup is None:
            art_lookup = self._build_artifact_id_lookup()

        ARTIFACT_KINDS = {
            1: "Weapon", 2: "Helmet", 3: "Shield",
            4: "Gauntlets", 5: "Chestplate", 6: "Boots",
            7: "Ring", 8: "Amulet", 9: "Banner",
        }

        result = {}
        for kind, art_id in slot_to_art_id.items():
            art_ptr = art_lookup.get(art_id)
            if art_ptr:
                art = self._read_artifact_full(art_ptr)
                if art:
                    art["slot"] = ARTIFACT_KINDS.get(kind, f"Slot{kind}")
                    result[kind] = art
        return result

    # =========================================================================
    # Artifacts (legacy simple reader)
    # =========================================================================

    def get_artifacts(self):
        """Read all artifacts with set, rank, rarity, level, and sell price."""
        equip_wrap = self._ptr(self._uw + 0x30)  # UW_ARTIFACTS
        if not equip_wrap:
            return []
        # EquipmentWrapperReadOnly stores artifact data similarly to heroes
        # Search for the artifact dictionary in the wrapper
        for data_off in [0x88, 0x90, 0x80, 0x78]:
            art_data = self._ptr(equip_wrap + data_off)
            if not art_data:
                continue
            # Look for ArtifactById dictionary at common offsets
            for dict_off in [0x18, 0x10, 0x20]:
                art_dict = self._ptr(art_data + dict_off)
                if not art_dict:
                    continue
                try:
                    count = self.pm.read_int(art_dict + DICT_COUNT)
                    if count < 10 or count > 5000:
                        continue
                    entries = self._read_dict_int_obj(art_dict, max_items=min(count, 2000))
                    if not entries:
                        continue
                    # Validate first entry looks like an artifact
                    _, test_ptr = entries[0]
                    test_level = self.pm.read_int(test_ptr + ART_LEVEL)
                    test_rank = self.pm.read_int(test_ptr + ART_RANK)
                    if not (0 <= test_level <= 16 and 1 <= test_rank <= 6):
                        continue
                    # Found it — read all artifacts
                    artifacts = []
                    for _, ptr in entries:
                        try:
                            a = {
                                "id": self.pm.read_int(ptr + ART_ID),
                                "level": self.pm.read_int(ptr + ART_LEVEL),
                                "rank": self.pm.read_int(ptr + ART_RANK),
                                "rarity": self.pm.read_int(ptr + ART_RARITY),
                                "set": self.pm.read_int(ptr + ART_SET),
                                "kind": self.pm.read_int(ptr + ART_KIND),
                                "sell_price": self.pm.read_int(ptr + ART_SELL_PRICE),
                            }
                            if 0 <= a["level"] <= 16 and 1 <= a["rank"] <= 6:
                                a["rarity_name"] = RARITY_NAMES.get(a["rarity"], "?")
                                artifacts.append(a)
                        except Exception:
                            continue
                    logger.info(f"Read {len(artifacts)} artifacts (from offset 0x{data_off:X}/0x{dict_off:X})")
                    return artifacts
                except Exception:
                    continue
        logger.warning("Could not find artifact dictionary")
        return []

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

    def get_active_events(self):
        """Return active solo events and tournaments.
        TODO: Read from game memory once event data offsets are mapped.
        """
        return {"solo_events": [], "tournaments": []}

    def get_running_events(self):
        """Return currently running events for dungeon/farming optimization.
        TODO: Read from game memory once event data offsets are mapped.
        """
        return {"solo_events": [], "tournaments": []}

    def should_farm_dungeons(self):
        """Check if dungeon farming is worthwhile (enough energy, relevant events).
        TODO: Implement energy threshold and event-based logic.
        """
        try:
            res = self.get_resources()
            return res.get("energy", 0) >= 1000
        except Exception:
            return False

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
