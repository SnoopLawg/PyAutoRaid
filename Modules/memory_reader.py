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
UW_SOLO_EVENTS = 0x130   # SoloEventsWrapper
UW_TOURNAMENTS = 0x140   # TournamentsWrapper

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

# HeroType fields (via Hero._type pointer)
HEROTYPE_NAME = 0x18    # SharedLTextKey -> .DefaultValue (+0x18) = champion name
HEROTYPE_FRACTION = 0x38  # HeroFraction enum
HEROTYPE_RARITY = 0x3C  # HeroRarity enum

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

# ArtifactBonus fields
BONUS_STAT_KIND = 0x10  # StatKindId enum
BONUS_VALUE = 0x18      # BonusValue (inline: isAbsolute at +0x10, Fixed _value at +0x18)
BONUS_VALUE_IS_ABS = 0x18  # bool _isAbsolute (relative to ArtifactBonus)
BONUS_VALUE_VAL = 0x20     # Fixed _value (8 bytes, relative to ArtifactBonus)
BONUS_LEVEL = 0x38      # int _level (number of upgrade rolls into this substat)

# ArtifactStorageResolver — static singleton for artifact storage
# Chain: TypeInfo → static_fields → _implementation → _cachedArtifacts → _artifacts dict
ARTIFACT_RESOLVER_TYPEINFO_RVA = 0x4DE5890
ARTRESOLVER_IMPL = 0x00          # _implementation (ExternalArtifactsStorage)
EXTERNAL_CACHED = 0x10           # _cachedArtifacts (CachedArtifacts)
CACHED_ARTIFACTS_DICT = 0x18     # _artifacts (Dictionary<int, Artifact>)

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

# SoloEventsWrapperReadOnly -> GlobalEventsWrapper -> UpdatableGlobalEventsData
SEW_GLOBAL_EVENTS = 0x58    # GlobalEventsWrapper (from SoloEventsWrapperReadOnly)
GEW_DATA = 0x20             # UpdatableGlobalEventsData (from GlobalEventsWrapperReadOnly)
GEDATA_EVENTS = 0x18        # List<GlobalEvent> (from GlobalEventsDataForUser base)
GEDATA_SOLO = 0x20          # ICollection<GlobalEvent> _soloEvents
GEDATA_TOURNAMENTS = 0x28   # ICollection<GlobalEvent> _tournaments

# GlobalEvent fields
GE_ID = 0x10                # int Id
GE_GBOID = 0x14             # int GboId
GE_DATE_COND = 0x28         # GlobalRatingDateCondition
GE_QUEST_DATA = 0x30        # GlobalEventQuestData
GE_IS_FULL = 0x40           # bool IsFull

# GlobalRatingDateCondition (DateTime is 8 bytes, Nullable<DateTime> has bool+padding before)
DATECON_TEASER_START = 0x10  # Nullable<DateTime> TeaserStart
DATECON_START = 0x20         # Nullable<DateTime> Start
DATECON_END = 0x30           # Nullable<DateTime> End
DATECON_PRIZE_DEADLINE = 0x40  # Nullable<DateTime> TakePrizeDeadline

# GlobalEventQuestData -> Quest -> Name
GEQDATA_QUEST = 0x10         # Quest
QUEST_NAME = 0x58            # SharedLTextKey -> .DefaultValue (+0x18)
QUEST_COMPLETIONS = 0x88     # List<QuestCompletion> (progress entries for the quest)


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

# GlobalEventAction (what activities earn event points)
GEA_HERO_LEVELUP = 1
GEA_HERO_RANKUP = 2
GEA_HERO_ASCEND = 3
GEA_HERO_SKILLLEVELUP = 4
GEA_HERO_SUMMON = 5
GEA_HERO_FUSE = 6
GEA_ARTIFACT_COLLECT = 21
GEA_ARTIFACT_UPGRADE = 22
GEA_SHARDS_OPEN = 31
GEA_BATTLE_STORY = 50
GEA_BATTLE_DUNGEON = 51
GEA_BATTLE_ARENA = 52
GEA_BATTLE_DUNGEON_REWARD = 53
GEA_BATTLE_ARENA_3X3 = 54
GEA_BATTLE_DUNGEON_TURN = 55

# GlobalEventStateId
EVENT_CREATED = 1
EVENT_TEASER = 2
EVENT_RUNNING = 3
EVENT_REWARDING = 4
EVENT_FINISHED = 5

# RegionTypeId (dungeons we care about for farming)
REGION_DRAGON = 206       # DragonsLair
REGION_ICE_GOLEM = 207    # IceGolemCave
REGION_FIRE_KNIGHT = 208  # FireGolemCave (Fire Knight)
REGION_SPIDER = 209       # SpiderCave
REGION_MINOTAUR = 210     # MinotaurCave

REGION_NAMES = {
    206: "Dragon", 207: "Ice Golem", 208: "Fire Knight",
    209: "Spider", 210: "Minotaur",
    201: "Void Keep", 202: "Spirit Keep", 203: "Magic Keep",
    204: "Force Keep", 205: "Arcane Keep",
}

# StatKindId
STAT_HP = 1
STAT_ATK = 2
STAT_DEF = 3
STAT_SPD = 4
STAT_RES = 5
STAT_ACC = 6
STAT_CRIT_RATE = 7
STAT_CRIT_DMG = 8

STAT_NAMES = {
    1: "HP", 2: "ATK", 3: "DEF", 4: "SPD",
    5: "RES", 6: "ACC", 7: "C.Rate", 8: "C.Dmg",
}

# ArtifactSetKindId
SET_NAMES = {
    0: "None", 1: "HP", 2: "ATK", 3: "DEF", 4: "Speed",
    5: "C.Rate", 6: "C.Dmg", 7: "ACC", 8: "RES",
    9: "Lifesteal", 10: "Savage", 11: "Sleep", 12: "BlockHeal",
    13: "Frost", 14: "Stamina", 15: "Heal", 16: "BlockDebuff",
    17: "Shield", 18: "Relentless", 19: "IgnoreDef", 20: "DecMaxHP",
    21: "Stun", 22: "Toxic", 23: "Provoke", 24: "Counterattack",
    25: "Retaliation", 26: "AoeDmgDec", 27: "Reflex", 28: "CritHeal",
    29: "Cruel", 30: "Immortal", 31: "Fury", 32: "Perception",
    33: "Resilience", 34: "Swiftparry", 35: "Untouchable",
    36: "Deflection", 37: "Stalwart", 38: "Guardian", 39: "Lethal",
    40: "Bolster", 41: "Frenzy", 42: "Frostbite",
}

# ArtifactKindId
KIND_NAMES = {
    1: "Helmet", 2: "Chest", 3: "Gloves", 4: "Boots",
    5: "Weapon", 6: "Shield", 7: "Ring", 8: "Cloak", 9: "Banner",
}

# "Bottom row" pieces — gloves/chest/boots have variable primary stats
BOTTOM_ROW_KINDS = {2, 3, 4}  # Chest, Gloves, Boots

# Desirable sets for keeping
GOOD_SETS = {4, 9, 10, 29, 31, 19, 32, 34, 35}  # Speed, Lifesteal, Savage, Cruel, Fury, IgnoreDef, Perception, Swiftparry, Untouchable

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

VIEW_DUNGEONS_MAP = 1027
VIEW_DUNGEONS_HUD = 1028
VIEW_DUNGEON_DIALOG = 1029
VIEW_HERO_SELECT_DUNGEON = 1008
VIEW_AUTO_BATTLE_SETTINGS = 2089
VIEW_AUTO_BATTLE_HEROES = 2090
VIEW_MULTI_RUN_INFO = 1130

VIEW_NAMES = {
    0: "None",
    1008: "HeroSelectDungeon", 1011: "HeroSelectArena",
    1012: "BattleLoading", 1013: "BattleFinishStory",
    1014: "BattleFinishArena", 1015: "BattleHUD",
    1022: "BattleModeSelect", 1025: "RegionDialog",
    1027: "DungeonsMap", 1028: "DungeonsHUD",
    1029: "DungeonDialog",
    1032: "Village", 1033: "VillageHUD",
    1034: "GemMine", 1038: "Shop",
    1042: "Inbox", 1049: "Quests",
    1051: "Arena", 1063: "BattleFinishDungeon",
    1071: "ClanBoss", 1072: "HeroSelectCB",
    1100: "BattleFinishCB", 1130: "MultiRunInfo",
    1143: "AllianceActivityHUD",
    2089: "AutoBattleSettings", 2090: "AutoBattleHeroes",
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

    # =========================================================================
    # Artifacts
    # =========================================================================

    def _resolve_artifact_dict(self):
        """Resolve the artifact dictionary via ArtifactStorageResolver static singleton.
        Chain: TypeInfo → static_fields → _implementation → _cachedArtifacts → _artifacts
        """
        ti = self._ptr(self.ga_base + ARTIFACT_RESOLVER_TYPEINFO_RVA)
        if not ti:
            return None
        sf = self._ptr(ti + 0xB8)  # static_fields
        if not sf:
            return None
        impl = self._ptr(sf + ARTRESOLVER_IMPL)
        if not impl:
            return None
        cached = self._ptr(impl + EXTERNAL_CACHED)
        if not cached:
            return None
        return self._ptr(cached + CACHED_ARTIFACTS_DICT)

    def _read_artifact_bonus(self, bonus_ptr):
        """Read an ArtifactBonus (primary or substat).
        Returns {"stat": int, "stat_name": str, "is_flat": bool, "value": float, "rolls": int}.
        """
        if not bonus_ptr:
            return None
        stat_kind = self.pm.read_int(bonus_ptr + BONUS_STAT_KIND)
        is_abs = self.pm.read_bytes(bonus_ptr + BONUS_VALUE_IS_ABS, 1)[0] != 0
        # Fixed value is 8 bytes at offset 0x20 from bonus ptr
        raw = struct.unpack('<q', self.pm.read_bytes(bonus_ptr + BONUS_VALUE_VAL, 8))[0]
        # Fixed-point: divide by appropriate scale. Common scales are 100 or 10000.
        # For percentage stats, raw is already the percentage * some factor.
        # Flat stats (is_abs=True): value is the flat amount
        # Percentage stats (is_abs=False): value is percentage (e.g. 5 = 5%)
        level = self.pm.read_int(bonus_ptr + BONUS_LEVEL)
        return {
            "stat": stat_kind,
            "stat_name": STAT_NAMES.get(stat_kind, f"?{stat_kind}"),
            "is_flat": is_abs,
            "value": raw,
            "rolls": level,
        }

    def get_artifacts(self, with_substats=False):
        """Read all artifacts from the ArtifactStorageResolver cache.
        Set with_substats=True to include primary and secondary stat details.
        """
        art_dict = self._resolve_artifact_dict()
        if not art_dict:
            logger.warning("Could not resolve artifact storage")
            return []

        count = self.pm.read_int(art_dict + DICT_COUNT)
        if count <= 0:
            return []

        entries = self._read_dict_int_obj(art_dict, max_items=min(count, 5000))
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
                if not (0 <= a["level"] <= 16 and 1 <= a["rank"] <= 6):
                    continue
                a["rarity_name"] = RARITY_NAMES.get(a["rarity"], "?")
                a["set_name"] = SET_NAMES.get(a["set"], f"?{a['set']}")
                a["kind_name"] = KIND_NAMES.get(a["kind"], f"?{a['kind']}")

                if with_substats:
                    # Primary bonus
                    pri = self._ptr(ptr + ART_PRIMARY)
                    a["primary"] = self._read_artifact_bonus(pri)

                    # Secondary bonuses (substats)
                    secs = self._ptr(ptr + ART_SECONDARIES)
                    a["substats"] = []
                    if secs:
                        sec_ptrs = self._read_list_ptrs(secs, max_items=4)
                        for sp in sec_ptrs:
                            bonus = self._read_artifact_bonus(sp)
                            if bonus:
                                a["substats"].append(bonus)

                artifacts.append(a)
            except Exception:
                continue

        logger.info(f"Read {len(artifacts)} artifacts")
        return artifacts

    def score_artifact(self, art):
        """Score an artifact 0-100 for quality.
        Higher = better, should keep. Lower = sell candidate.

        Scoring:
          - Base: rank(1-6) * 8 + rarity(1-6) * 5  (max 78)
          - Speed substat bonus: +15 per speed sub
          - Good set bonus: +5
          - Flat stat penalty on bottom row: -20
          - Level bonus: +level (0-16)
        """
        score = art["rank"] * 8 + art["rarity"] * 5 + art["level"]

        # Good set bonus
        if art["set"] in GOOD_SETS:
            score += 5

        # Substat analysis (requires with_substats=True)
        if "substats" in art:
            for sub in art["substats"]:
                if sub["stat"] == STAT_SPD:
                    score += 15  # Speed is king
                if sub["is_flat"] and art["kind"] in BOTTOM_ROW_KINDS:
                    score -= 10  # Flat stats on bottom row = bad

        return min(100, max(0, score))

    def get_sellable_artifacts(self, threshold=40):
        """Get artifacts scoring below threshold — candidates for selling.
        Excludes leveled artifacts (level > 0) and locked heroes' gear.
        """
        arts = self.get_artifacts(with_substats=True)
        sellable = []
        for a in arts:
            if a["level"] > 0:
                continue  # Don't sell leveled gear
            score = self.score_artifact(a)
            a["score"] = score
            if score < threshold:
                sellable.append(a)
        sellable.sort(key=lambda x: x["score"])
        return sellable

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
    # Events & Tournaments
    # =========================================================================

    def _read_datetime(self, addr):
        """Read a C# DateTime (8 bytes, ticks since 0001-01-01).
        Returns a Python datetime or None."""
        try:
            from datetime import datetime, timedelta, timezone
            ticks = self.pm.read_ulonglong(addr)
            if ticks == 0:
                return None
            # C# ticks: 100-nanosecond intervals since 0001-01-01
            # Python: seconds since 1970-01-01
            epoch_ticks = 621355968000000000  # ticks from 0001-01-01 to 1970-01-01
            seconds = (ticks - epoch_ticks) / 10_000_000
            return datetime.fromtimestamp(seconds, tz=timezone.utc)
        except Exception:
            return None

    def _read_nullable_datetime(self, addr):
        """Read a Nullable<DateTime>. Layout: bool hasValue (1 byte),
        padding to 8-byte boundary, then DateTime value (8 bytes).
        The Nullable<DateTime> at the given offset is already the struct start."""
        try:
            # Nullable<DateTime> in IL2CPP: stored as 16 bytes total
            # Offset +0x00: DateTime value (8 bytes)
            # Offset +0x08: bool hasValue (in some layouts)
            # But C# Nullable<T> in memory: hasValue first, then value
            # For reference types the layout may differ — try reading the DateTime directly
            # and validate the year is reasonable
            dt = self._read_datetime(addr)
            if dt and 2020 < dt.year < 2030:
                return dt
            # Try offset +8
            dt = self._read_datetime(addr + 8)
            if dt and 2020 < dt.year < 2030:
                return dt
            return None
        except Exception:
            return None

    def _read_event_name(self, event_ptr):
        """Read event name from GlobalEvent -> QuestData -> Quest -> Name."""
        quest_data = self._ptr(event_ptr + GE_QUEST_DATA)
        if not quest_data:
            return ""
        quest = self._ptr(quest_data + GEQDATA_QUEST)
        if not quest:
            return ""
        name_key = self._ptr(quest + QUEST_NAME)  # SharedLTextKey
        if not name_key:
            return ""
        name_str = self._ptr(name_key + 0x18)  # .DefaultValue
        return self._read_il2cpp_string(name_str)

    def _get_global_events_data(self):
        """Navigate to UpdatableGlobalEventsData from UserWrapper.
        Chain: UW -> SoloEventsWrapper -> _globalEvents -> _data
        """
        solo_wrap = self._ptr(self._uw + UW_SOLO_EVENTS)
        if not solo_wrap:
            return None
        global_events = self._ptr(solo_wrap + SEW_GLOBAL_EVENTS)
        if not global_events:
            return None
        return self._ptr(global_events + GEW_DATA)

    def _read_event_list(self, collection_ptr):
        """Read events from an ICollection<GlobalEvent> (typically a List)."""
        if not collection_ptr:
            return []
        # ICollection backed by List — read as list
        ptrs = self._read_list_ptrs(collection_ptr)
        events = []
        for ptr in ptrs:
            try:
                event_id = self.pm.read_int(ptr + GE_ID)
                if event_id <= 0 or event_id > 100000:
                    continue

                # Read date condition
                date_cond = self._ptr(ptr + GE_DATE_COND)
                start_time = None
                end_time = None
                if date_cond:
                    start_time = self._read_nullable_datetime(date_cond + DATECON_START)
                    end_time = self._read_nullable_datetime(date_cond + DATECON_END)

                name = self._read_event_name(ptr)

                events.append({
                    "id": event_id,
                    "name": name,
                    "start": start_time,
                    "end": end_time,
                    "is_full": self.pm.read_bytes(ptr + GE_IS_FULL, 1)[0] != 0,
                })
            except Exception:
                continue
        return events

    def get_active_events(self):
        """Read all active solo events and tournaments.
        Returns {"solo_events": [...], "tournaments": [...]}.
        Each event has: id, name, start, end, is_full, active (bool).
        """
        from datetime import datetime, timezone

        ge_data = self._get_global_events_data()
        if not ge_data:
            logger.warning("Could not read global events data")
            return {"solo_events": [], "tournaments": []}

        now = datetime.now(timezone.utc)

        def annotate(events):
            for e in events:
                s, end = e.get("start"), e.get("end")
                e["active"] = (s is not None and end is not None
                               and s <= now <= end)
                if s:
                    e["start"] = s.isoformat()
                if end:
                    e["end"] = end.isoformat()
                    e["hours_left"] = max(0, (end - now).total_seconds() / 3600)
            return events

        solo_ptr = self._ptr(ge_data + GEDATA_SOLO)
        tourn_ptr = self._ptr(ge_data + GEDATA_TOURNAMENTS)

        solo = annotate(self._read_event_list(solo_ptr))
        tournaments = annotate(self._read_event_list(tourn_ptr))

        # Fallback: try the base class Events list (0x18) which has all events
        if not solo and not tournaments:
            all_ptr = self._ptr(ge_data + GEDATA_EVENTS)
            all_events = annotate(self._read_event_list(all_ptr))
            if all_events:
                logger.info(f"Read {len(all_events)} events from base Events list")
                return {"solo_events": all_events, "tournaments": []}

        logger.info(f"Events: {len(solo)} solo, {len(tournaments)} tournaments")
        return {"solo_events": solo, "tournaments": tournaments}

    def get_running_events(self):
        """Get only currently active (running) events."""
        data = self.get_active_events()
        running_solo = [e for e in data["solo_events"] if e.get("active")]
        running_tourn = [e for e in data["tournaments"] if e.get("active")]
        return {"solo_events": running_solo, "tournaments": running_tourn}

    def should_farm_dungeons(self):
        """Check if any active event rewards dungeon battles.
        Returns True if a 'Dungeon Divers' style event or dungeon tournament
        is currently running, meaning dungeon farming would double-dip.
        """
        running = self.get_running_events()
        dungeon_keywords = ["dungeon", "dragon", "spider", "fire knight",
                            "ice golem", "keeps", "divers"]
        for event in running["solo_events"] + running["tournaments"]:
            name = event.get("name", "").lower()
            if any(kw in name for kw in dungeon_keywords):
                return True
        return False

    def should_farm_arena(self):
        """Check if any active event rewards arena battles."""
        running = self.get_running_events()
        arena_keywords = ["arena", "gladiator"]
        for event in running["solo_events"] + running["tournaments"]:
            name = event.get("name", "").lower()
            if any(kw in name for kw in arena_keywords):
                return True
        return False

    def should_upgrade_artifacts(self):
        """Check if any active event rewards artifact upgrades."""
        running = self.get_running_events()
        artifact_keywords = ["artifact", "enhancement", "forge", "gear"]
        for event in running["solo_events"] + running["tournaments"]:
            name = event.get("name", "").lower()
            if any(kw in name for kw in artifact_keywords):
                return True
        return False

    def should_summon_champions(self):
        """Check if any active event rewards summoning."""
        running = self.get_running_events()
        summon_keywords = ["summon", "invocation", "champion chase"]
        for event in running["solo_events"] + running["tournaments"]:
            name = event.get("name", "").lower()
            if any(kw in name for kw in summon_keywords):
                return True
        return False

    def should_level_champions(self):
        """Check if any active event rewards champion training."""
        running = self.get_running_events()
        training_keywords = ["training", "champion chase", "level up"]
        for event in running["solo_events"] + running["tournaments"]:
            name = event.get("name", "").lower()
            if any(kw in name for kw in training_keywords):
                return True
        return False

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
