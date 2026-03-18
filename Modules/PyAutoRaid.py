import pyautogui
import logging
import os
import sys
import time
import configparser
import datetime
import threading
import tkinter
from tkinter import ttk
from ttkthemes import ThemedTk
import pyscreeze

from base import (
    BaseDaily, locate_and_click, locate_and_click_loop,
    wait_for_image, asset, MAX_RETRIES,
)

pyscreeze.USE_IMAGE_NOT_FOUND_EXCEPTION = False

logging.basicConfig(
    filename='PyAutoRaid.log',
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filemode='w',
    level=logging.DEBUG,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Named pixel coordinates (1920x1080, game window 900x600 centered)
# ---------------------------------------------------------------------------
GEM_MINE_POS = (583, 595)
TIMED_REWARDS_Y = 500
TIMED_REWARDS_X_RANGE = range(669, 1269, 100)
TIMED_REWARDS_END_X = 1269
CB_SCROLL_POS = (1080, 724)
CB_SCROLL_DELTA = -200
ARENA_SCROLL_POS = (969, 788)
ARENA_SCROLL_DELTA = -380
ARENA_REGIONS = [
    # (region_x, region_y, region_w, region_h, click_x, click_y)
    (1215, 423, 167, 58, 1304, 457),
    (1215, 508, 167, 58, 1304, 540),
    (1215, 596, 167, 58, 1303, 625),
    (1215, 681, 167, 58, 1304, 711),
    (1208, 762, 190, 68, 1304, 800),
]


# ---------------------------------------------------------------------------
# Command pattern base
# ---------------------------------------------------------------------------
class Command:
    def execute(self):
        pass


# ---------------------------------------------------------------------------
# Individual commands
# ---------------------------------------------------------------------------
class DailyGemMineCommand(Command):
    def __init__(self, app):
        self.app = app

    def execute(self):
        try:
            logger.info("Starting Daily Gem Mine task.")
            pyautogui.click(*GEM_MINE_POS)
            time.sleep(2)
            pyautogui.hotkey("esc")
            time.sleep(2)
            self.app.steps["Gem_mine"] = "True"
            self.app.delete_popup()
            logger.info("Completed Daily Gem Mine task.")
        except Exception as e:
            logger.error(f"Error in DailyGemMineCommand: {e}")
            self.app.back_to_bastion()
            self.app.delete_popup()


class DailyMarketPurchaseCommand(Command):
    def __init__(self, app):
        self.app = app
        self.AS_bought = 0
        self.MS_bought = 0

    def execute(self):
        try:
            logger.info("Starting Daily Market Purchase task.")
            market_image = asset(self.app.asset_path, "theMarket.png")
            ancient_shard_image = asset(self.app.asset_path, "ancientShard.png")
            mystery_shard_image = asset(self.app.asset_path, "mysteryShard.png")
            default_claim_image = asset(self.app.asset_path, "defaultClaim.png")

            locate_and_click_loop(market_image, sleep_after=2)

            # Buy ancient shards
            retries = 0
            while retries < MAX_RETRIES:
                loc = pyautogui.locateOnScreen(ancient_shard_image, confidence=0.8)
                if not loc:
                    break
                x, y = pyautogui.center(loc)
                pyautogui.click(x, y)
                time.sleep(2)
                if locate_and_click(default_claim_image, sleep_after=3):
                    self.AS_bought += 1
                    logger.info(f"Bought ancient shard #{self.AS_bought}")
                retries += 1

            # Buy mystery shards
            retries = 0
            while retries < MAX_RETRIES:
                loc = pyautogui.locateOnScreen(mystery_shard_image, confidence=0.8)
                if not loc:
                    break
                x, y = pyautogui.center(loc)
                pyautogui.click(x, y)
                time.sleep(2)
                if locate_and_click(default_claim_image, sleep_after=3):
                    self.MS_bought += 1
                    logger.info(f"Bought mystery shard #{self.MS_bought}")
                retries += 1

            self.app.steps["AS_bought"] = self.AS_bought
            self.app.steps["MS_bought"] = self.MS_bought
            self.app.back_to_bastion()
            self.app.delete_popup()
            logger.info("Completed Daily Market Purchase task.")
        except Exception as e:
            logger.error(f"Error in DailyMarketPurchaseCommand: {e}")
            self.app.back_to_bastion()
            self.app.delete_popup()


class DailyShopCommand(Command):
    def __init__(self, app):
        self.app = app

    def execute(self):
        try:
            logger.info("Starting Daily Shop task.")
            shop_image = asset(self.app.asset_path, "shop.png")
            offers_image = asset(self.app.asset_path, "offers.png")
            free_gift_image = asset(self.app.asset_path, "claimFreeGift.png")

            locate_and_click_loop(shop_image, sleep_after=2)
            time.sleep(2)

            # Click through offers
            if locate_and_click(offers_image, confidence=0.9, sleep_after=3):
                for i in range(724, 1400, 50):
                    pyautogui.click(i, 333)
                    locate_and_click(free_gift_image, sleep_after=1)
                time.sleep(1.5)

            self.app.steps["Shop"] = "Accessed"
            self.app.back_to_bastion()
            self.app.delete_popup()
            logger.info("Completed Daily Shop task.")
        except Exception as e:
            logger.error(f"Error in DailyShopCommand: {e}")
            self.app.back_to_bastion()
            self.app.delete_popup()


class DailyGuardianRingCommand(Command):
    def __init__(self, app):
        self.app = app

    def execute(self):
        try:
            logger.info("Starting Daily Guardian Ring task.")
            guardian_ring_image = asset(self.app.asset_path, "guardianRing.png")
            gr_upgrade_image = asset(self.app.asset_path, "GRupgrade.png")

            if locate_and_click(guardian_ring_image, sleep_after=4):
                upgrades = locate_and_click_loop(gr_upgrade_image, sleep_after=2)
                self.app.steps["GR_upgrades"] = upgrades
                logger.info(f"Performed {upgrades} Guardian Ring upgrade(s).")
                self.app.back_to_bastion()
                self.app.delete_popup()
                logger.info("Completed Daily Guardian Ring task.")
            else:
                logger.warning("Guardian Ring button not found on screen.")
        except Exception as e:
            logger.error(f"Error in DailyGuardianRingCommand: {e}")
            self.app.back_to_bastion()
            self.app.delete_popup()


class DailyTimedRewardsCommand(Command):
    def __init__(self, app):
        self.app = app

    def execute(self):
        try:
            logger.info("Starting Daily Timed Rewards task.")
            time_rewards_image = asset(self.app.asset_path, "timeRewards.png")
            red_dot_image = asset(self.app.asset_path, "redNotificationDot.png")

            if locate_and_click(time_rewards_image, sleep_after=2):
                locate_and_click_loop(red_dot_image, sleep_after=1)

                for i in TIMED_REWARDS_X_RANGE:
                    time.sleep(0.2)
                    pyautogui.click(i, TIMED_REWARDS_Y)
                time.sleep(1)
                pyautogui.click(TIMED_REWARDS_END_X, TIMED_REWARDS_Y)
                pyautogui.click(TIMED_REWARDS_END_X, TIMED_REWARDS_Y)

                self.app.steps["Timed_rewards"] = "Collected"
                self.app.back_to_bastion()
                self.app.delete_popup()
                logger.info("Completed Daily Timed Rewards task.")
            else:
                logger.warning("Timed Rewards button not found on screen.")

            self.app.steps["7_campaign_battles"] = "Not Collected"
        except Exception as e:
            logger.error(f"Error in DailyTimedRewardsCommand: {e}")
            self.app.back_to_bastion()
            self.app.delete_popup()


class DailyClanCommand(Command):
    def __init__(self, app):
        self.app = app

    def execute(self):
        try:
            logger.info("Starting Daily Clan task.")
            clan_btn_image = asset(self.app.asset_path, "clanBTN.png")
            clan_members_image = asset(self.app.asset_path, "clanMembers.png")
            clan_check_in_image = asset(self.app.asset_path, "clanCheckIn.png")
            clan_treasure_image = asset(self.app.asset_path, "clanTreasure.png")
            red_dot_image = asset(self.app.asset_path, "redNotificationDot.png")

            if locate_and_click(clan_btn_image, sleep_after=1):
                locate_and_click(clan_members_image, sleep_after=2)
                locate_and_click_loop(clan_check_in_image, sleep_after=1)
                locate_and_click(clan_treasure_image, sleep_after=1)

                # Click all red notification dots
                dots = list(pyautogui.locateAllOnScreen(red_dot_image, confidence=0.8) or [])
                for dot in dots:
                    dx, dy = pyautogui.center(dot)
                    pyautogui.click(dx, dy + 10)
                    time.sleep(3)

                self.app.steps["Daily_clan"] = "Accessed"
                self.app.back_to_bastion()
                logger.info("Completed Daily Clan task.")
            else:
                logger.warning("Clan button not found on screen.")
        except Exception as e:
            logger.error(f"Error in DailyClanCommand: {e}")
            self.app.back_to_bastion()
            self.app.delete_popup()


class DailyQuestClaimsCommand(Command):
    def __init__(self, app):
        self.app = app
        self.quests_completed = 0

    def execute(self):
        try:
            logger.info("Starting Daily Quest Claims task.")
            quests_image = asset(self.app.asset_path, "quests.png")
            quest_claim_image = asset(self.app.asset_path, "questClaim.png")
            advanced_quests_image = asset(self.app.asset_path, "advancedQuests.png")

            if locate_and_click(quests_image, sleep_after=2):
                self.quests_completed += locate_and_click_loop(quest_claim_image, sleep_after=1)

                if locate_and_click(advanced_quests_image, sleep_after=1):
                    # Claim advanced quest rewards too
                    self.quests_completed += locate_and_click_loop(quest_claim_image, confidence=0.8, sleep_after=1)

                self.app.steps["Quests_completed"] = self.quests_completed
                self.app.back_to_bastion()
                self.app.delete_popup()
                logger.info(f"Completed Daily Quest Claims: {self.quests_completed} claimed.")
            else:
                logger.warning("Quests button not found on screen.")
                self.app.steps["Quests_Completed"] = "Not Accessed"
        except Exception as e:
            logger.error(f"Error in DailyQuestClaimsCommand: {e}")
            self.app.back_to_bastion()
            self.app.delete_popup()


class DailyInboxCommand(Command):
    def __init__(self, app):
        self.app = app

    def execute(self):
        try:
            logger.info("Starting Daily Inbox task.")
            time.sleep(1)
            pyautogui.hotkey("i")

            inbox_items = [
                "inbox_energy", "inbox_brew", "inbox_purple_forge",
                "inbox_yellow_forge", "inbox_coin", "inbox_potion",
            ]
            for item in inbox_items:
                png = asset(self.app.asset_path, f"{item}.png")
                time.sleep(0.3)
                retries = 0
                while retries < MAX_RETRIES:
                    location = pyautogui.locateOnScreen(png, confidence=0.8)
                    if not location:
                        break
                    pyautogui.moveTo(location)
                    pyautogui.moveRel(250, 0)
                    pyautogui.click()
                    time.sleep(2)
                    retries += 1
                    logger.info(f"Collected inbox item: {item}")

            self.app.steps["daily_inbox"] = "Accessed"
            self.app.back_to_bastion()
            self.app.delete_popup()
            logger.info("Completed Daily Inbox task.")
        except Exception as e:
            logger.error(f"Error in DailyInboxCommand: {e}")
            self.app.back_to_bastion()
            self.app.delete_popup()


class RewardsCommand(Command):
    def __init__(self, app):
        self.app = app

    def execute(self):
        logger.info("Starting Rewards tasks.")
        commands = [
            DailyGemMineCommand(self.app),
            DailyMarketPurchaseCommand(self.app),
            DailyShopCommand(self.app),
            DailyGuardianRingCommand(self.app),
            DailyTimedRewardsCommand(self.app),
            DailyClanCommand(self.app),
            DailyQuestClaimsCommand(self.app),
            DailyInboxCommand(self.app),
        ]
        for command in commands:
            command.execute()
        logger.info("Completed Rewards tasks.")


class DailyTenClassicArenaCommand(Command):
    def __init__(self, app):
        self.app = app
        self.classic_battles = 0

    def execute(self):
        try:
            logger.info("Starting Daily Ten Classic Arena task.")
            self.app.delete_popup()

            battle_btn_image = asset(self.app.asset_path, "battleBTN.png")
            arena_tab_image = asset(self.app.asset_path, "arenaTab.png")
            classic_arena_image = asset(self.app.asset_path, "classicArena.png")
            arena_refresh_image = asset(self.app.asset_path, "arenaRefresh.png")
            arena_battle_image = asset(self.app.asset_path, "arenaBattle.png")
            arena_confirm_image = asset(self.app.asset_path, "arenaConfirm.png")
            classic_arena_refill_image = asset(self.app.asset_path, "classicArenaRefill.png")
            arena_start_image = asset(self.app.asset_path, "arenaStart.png")
            tap_to_continue_image = asset(self.app.asset_path, "tapToContinue.png")

            locate_and_click_loop(battle_btn_image, confidence=0.9, sleep_after=2)
            locate_and_click_loop(arena_tab_image, confidence=0.9, sleep_after=2)

            if not locate_and_click(classic_arena_image, confidence=0.9, sleep_after=2):
                logger.warning("Classic Arena not found.")
                return

            for page in range(2):
                locate_and_click_loop(arena_refresh_image, confidence=0.9, sleep_after=2)

                for rx, ry, rw, rh, cx, cy in ARENA_REGIONS:
                    if pyautogui.locateOnScreen(arena_battle_image, region=(rx, ry, rw, rh), confidence=0.6):
                        pyautogui.click(cx, cy)
                        time.sleep(3)

                        # Replenish tokens
                        locate_and_click_loop(arena_confirm_image, confidence=0.9, sleep_after=5)

                        # Out of coins check
                        if pyautogui.locateOnScreen(classic_arena_refill_image, confidence=0.8):
                            self.app.steps["Classic_Arena"] = "Ran out of coins"
                            self.app.steps["classic_arena_battles"] = f"{self.classic_battles} total"
                            self.app.back_to_bastion()
                            self.app.delete_popup()
                            logger.info("Ran out of arena coins.")
                            return

                        time.sleep(4)
                        locate_and_click(arena_start_image, confidence=0.9, sleep_after=0)

                        # Wait for battle to finish
                        logger.debug("Waiting for 'Tap to Continue' screen.")
                        wait_for_image(tap_to_continue_image, timeout=120)

                        # Click through results
                        retries = 0
                        while retries < MAX_RETRIES:
                            loc = pyautogui.locateOnScreen(tap_to_continue_image, confidence=0.8)
                            if not loc:
                                break
                            time.sleep(1)
                            x, y = pyautogui.center(loc)
                            pyautogui.click(x, y)
                            self.classic_battles += 1
                            logger.info(f"Arena battle #{self.classic_battles} completed.")
                            time.sleep(1)
                            pyautogui.click(x, y)
                            time.sleep(3)
                            retries += 1

                        if page == 1:
                            pyautogui.doubleClick(*ARENA_SCROLL_POS, interval=1)
                            pyautogui.dragRel(0, ARENA_SCROLL_DELTA - 1, duration=2)
                            time.sleep(3)

                    time.sleep(1)
                    pyautogui.doubleClick(*ARENA_SCROLL_POS, interval=1)

                time.sleep(1)
                if page == 0:
                    pyautogui.doubleClick(*ARENA_SCROLL_POS, interval=1)
                    pyautogui.dragRel(0, ARENA_SCROLL_DELTA, duration=2)
                    time.sleep(3)

            time.sleep(3)
            self.app.steps["classic_arena_battles"] = f"{self.classic_battles} total classic arena battles fought"
            self.app.back_to_bastion()
            self.app.delete_popup()
            logger.info(f"{self.classic_battles} total classic arena battles fought.")
        except Exception as e:
            logger.error(f"Error in DailyTenClassicArenaCommand: {e}")


class ClanBossCommand(Command):
    def __init__(self, app):
        self.app = app

    def execute(self):
        try:
            logger.info("Starting Clan Boss task.")
            CBDIFFICULTYS = [
                "ultra-nightmare", "nightmare", "brutal",
                "hard", "normal", "easy",
            ]
            time.sleep(1.5)
            self.app.delete_popup()

            battle_btn_image = asset(self.app.asset_path, "battleBTN.png")
            demon_lord2_image = asset(self.app.asset_path, "demonLord2.png")
            CB_card_image = asset(self.app.asset_path, "CB.png")
            CB_reward_image = asset(self.app.asset_path, "CBreward.png")
            nightmare_claimed_image = asset(self.app.asset_path, "nightmareClaimed.png")
            CB_claim_image = asset(self.app.asset_path, "CBclaim.png")
            CB_hard_image = asset(self.app.asset_path, "CBhard.png")
            CB_battle_image = asset(self.app.asset_path, "CBbattle.png")
            CB_no_key_image = asset(self.app.asset_path, "CBnokey.png")
            CB_start_image = asset(self.app.asset_path, "CBstart.png")
            goto_bastion_image = asset(self.app.asset_path, "gotoBastion.png")

            # Navigate to battle screen
            locate_and_click_loop(battle_btn_image, sleep_after=2)
            locate_and_click_loop(CB_card_image, sleep_after=2)
            locate_and_click_loop(demon_lord2_image, sleep_after=4)

            # Scroll and collect rewards
            pyautogui.click(*CB_SCROLL_POS)
            pyautogui.drag(0, CB_SCROLL_DELTA, duration=1)

            retries = 0
            while retries < MAX_RETRIES:
                loc = pyautogui.locateOnScreen(CB_reward_image, confidence=0.8)
                if not loc:
                    break
                for reward in pyautogui.locateAllOnScreen(CB_reward_image, confidence=0.8):
                    rx, ry = pyautogui.center(reward)
                    pyautogui.click(rx, ry)
                    time.sleep(2)
                    for claim in pyautogui.locateAllOnScreen(CB_claim_image, confidence=0.8):
                        cx, cy = pyautogui.center(claim)
                        pyautogui.click(cx, cy)
                        time.sleep(3)
                        pyautogui.click(cx, cy)
                retries += 1

            # Collect claimed rewards
            retries = 0
            while retries < MAX_RETRIES:
                if not pyautogui.locateOnScreen(nightmare_claimed_image, confidence=0.8):
                    break
                loc = pyautogui.locateOnScreen(CB_claim_image, confidence=0.8)
                if loc:
                    x, y = pyautogui.center(loc)
                    pyautogui.click(x, y)
                    time.sleep(1)
                    pyautogui.click()
                    time.sleep(1)
                    pyautogui.click()
                    logger.info("Collected claimed reward.")
                retries += 1

            retries = 0
            while retries < MAX_RETRIES:
                loc = pyautogui.locateOnScreen(CB_claim_image, confidence=0.8)
                if not loc:
                    break
                x, y = pyautogui.center(loc)
                pyautogui.click(x, y)
                time.sleep(1)
                pyautogui.click()
                logger.info("Collected Clan Boss claim.")
                retries += 1

            time.sleep(2)
            pyautogui.click(*CB_SCROLL_POS)
            pyautogui.drag(0, -CB_SCROLL_DELTA, duration=1)
            time.sleep(1)

            # Begin fighting clan boss
            retries = 0
            while retries < MAX_RETRIES and pyautogui.locateOnScreen(CB_hard_image, confidence=0.8):
                yCB = 690
                xCB = 1080
                difficulty = ''
                for diff in CBDIFFICULTYS:
                    ac = int(self.app.config["ActualClanBossFightsToday"][diff])
                    plan = int(self.app.config["PlannedClanBossFightsToday"][diff])
                    if ac < plan:
                        yCB = int(self.app.config["XYclanbossCoordinates"][diff + 'Y'])
                        xCB = int(self.app.config["XYclanbossCoordinates"][diff + 'X'])
                        difficulty = diff
                        break

                if yCB == 690:
                    pyautogui.click(*CB_SCROLL_POS)
                    pyautogui.drag(0, CB_SCROLL_DELTA, duration=1)
                    pyautogui.click(1080, 690)

                if not difficulty:
                    logger.info("No Clan Boss fights planned or available.")
                    break

                logger.info(f"Preparing to fight Clan Boss: {difficulty}")
                pyautogui.click(xCB, yCB)

                battle_retries = 0
                while battle_retries < MAX_RETRIES:
                    loc = pyautogui.locateOnScreen(CB_battle_image, confidence=0.8)
                    if not loc:
                        break
                    x, y = pyautogui.center(loc)
                    time.sleep(2)
                    pyautogui.click(x, y)
                    time.sleep(1)
                    if pyautogui.locateOnScreen(CB_no_key_image, confidence=0.8):
                        logger.warning("No keys available for Clan Boss.")
                        break
                    battle_retries += 1
                time.sleep(1)
                retries += 1

            time.sleep(5)
            if locate_and_click(CB_start_image, sleep_after=1):
                logger.info("Started Clan Boss battle.")

                # Wait for battle to finish
                wait_for_image(goto_bastion_image, timeout=600)
                locate_and_click(goto_bastion_image, sleep_after=1)
                logger.info("Returned to Bastion.")

                # Update config with new fight count
                if difficulty:
                    new_actual = int(self.app.config['ActualClanBossFightsToday'][difficulty]) + 1
                    self.app.config['ActualClanBossFightsToday'][difficulty] = str(new_actual)
                    with open('PARconfig.ini', 'w') as configfile:
                        self.app.config.write(configfile)
                    logger.info(f"Updated Clan Boss fights for {difficulty}: {new_actual}")

                self.app.delete_popup()
                self.app.back_to_bastion()
                self.app.delete_popup()

                return f"{difficulty.capitalize()} Clan Boss fought"
            else:
                logger.warning("No Clan Boss battle available to start.")
                self.app.back_to_bastion()
                return "No Clan Boss battle started."

        except Exception as e:
            logger.error(f"Error in ClanBossCommand: {e}", exc_info=True)
            self.app.back_to_bastion()
            self.app.delete_popup()


# ---------------------------------------------------------------------------
# Main Daily class (extends BaseDaily)
# ---------------------------------------------------------------------------
class Daily(BaseDaily):
    def __init__(self, master):
        self.config = configparser.ConfigParser()
        logging.basicConfig(
            filename='Logging.log',
            format='%(levelname)s:%(message)s',
            encoding='utf-8',
            level=logging.DEBUG,
        )
        with open('Logging.log', 'w'):
            pass

        # resetCBDay needs config before super().__init__ calls game window setup
        self.utc_now = datetime.datetime.now(datetime.timezone.utc)
        self._check_previous_days()

        super().__init__(master)

        self.classic_battles = 0
        self.GR_upgrades = 0
        self.quests_completed = 0
        self.AS_bought = 0
        self.MS_bought = 0

        self.command_registry = {
            'rewards': RewardsCommand(self),
            'daily_ten_classic_arena': DailyTenClassicArenaCommand(self),
            'clanboss': ClanBossCommand(self),
        }

    def _check_previous_days(self):
        try:
            today_str = self.utc_now.strftime("%d/%m/%Y")
            self._init_config(today_str)
            self.settings_config = dict(self.config.items("Settings"))
            self.config.read('PARconfig.ini')
            config_date = self.config.get('Settings', 'UTC_today')

            for day in range(1, 61):
                past_date = self.utc_now - datetime.timedelta(days=day)
                past_str = past_date.strftime("%d/%m/%Y")
                if past_str == config_date and self.utc_now.hour >= 10:
                    self._init_config(today_str, adjust=True)
                    logger.info("Previous day config adjusted.")
                    return True
        except Exception as e:
            logger.error(f"Error in _check_previous_days: {e}")

    def _init_config(self, day, adjust=False):
        try:
            if os.path.exists("PARconfig.ini"):
                self.config.read('PARconfig.ini')
            else:
                self.config['Settings'] = {
                    'UTC_today': day, 'rewards': True, 'clanboss': True,
                    'automated_mode': True, 'daily_ten_classic_arena': True,
                }
                self.config['PlannedClanBossFightsToday'] = {
                    'Easy': 0, 'Normal': 0, 'Hard': 0,
                    'Brutal': 0, 'Nightmare': 1, 'Ultra-Nightmare': 3,
                }
                self.config['ActualClanBossFightsToday'] = {
                    'Easy': 0, 'Normal': 0, 'Hard': 0,
                    'Brutal': 0, 'Nightmare': 0, 'Ultra-Nightmare': 0,
                }
                self.config['XYclanbossCoordinates'] = {
                    'EasyX': 1080, 'EasyY': 'IDK Coords yet',
                    'NormalX': 1080, 'NormalY': 'IDK Coords yet',
                    'HardX': 1080, 'HardY': 'IDK Coords yet',
                    'BrutalX': 1080, 'BrutalY': 647,
                    'NightmareX': 1080, 'NightmareY': 724,
                    'Ultra-NightmareX': 1080, 'Ultra-NightmareY': 690,
                }
                with open('PARconfig.ini', 'w') as f:
                    self.config.write(f)

            if adjust:
                self.config['Settings'] = {
                    'UTC_today': day,
                    'rewards': self.settings_config['rewards'],
                    'clanboss': self.settings_config['clanboss'],
                    'automated_mode': self.settings_config['automated_mode'],
                    'daily_ten_classic_arena': self.settings_config['daily_ten_classic_arena'],
                }
                self.config['ActualClanBossFightsToday'] = {
                    'Easy': 0, 'Normal': 0, 'Hard': 0,
                    'Brutal': 0, 'Nightmare': 0, 'Ultra-Nightmare': 0,
                }
                with open('PARconfig.ini', 'w') as f:
                    self.config.write(f)
            logger.info("Configuration file set up successfully.")
        except Exception as e:
            logger.error(f"Error in _init_config: {e}")

    def run(self):
        while self.running:
            try:
                self.config.read('PARconfig.ini')
                self.ToDo = dict(self.config.items("Settings"))
                self.settings_config = dict(self.config.items("Settings"))

                if self.settings_config.get("automated_mode", 'False') == 'True':
                    logger.info("Automated mode is enabled.")
                    try:
                        for key in self.ToDo:
                            if self.ToDo[key].lower() == 'true':
                                command = self.command_registry.get(key)
                                if command:
                                    logger.info(f"Executing task: {key}")
                                    command.execute()
                        self.close_gui()
                        self.kill_processes("Raid.exe")
                        break
                    except Exception as e:
                        logger.error(f"Error during automated tasks: {e}")
                        self.close_gui()
                        self.kill_processes("Raid.exe")
                        break
                else:
                    if self.manual_run_triggered:
                        logger.info("Manual run triggered.")
                        for key in self.ToDo:
                            if self.ToDo[key].lower() == 'true':
                                command = self.command_registry.get(key)
                                if command:
                                    logger.info(f"Executing task: {key}")
                                    command.execute()
                        self.trigger_manual_run(False)
                time.sleep(1)
            except Exception as e:
                logger.error(f"Unexpected error in run method: {e}")
                self.close_gui()
                self.kill_processes("Raid.exe")
                break


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------
class GUI:
    def __init__(self, master):
        try:
            self.app = Daily(master)
            self.timer_thread()
            self.daily_thread = threading.Thread(target=self.app.run)
            self.daily_thread.start()
            self.daily_thread.name = "PAR"
            self.config = configparser.ConfigParser()
            self.config.read('PARconfig.ini')
            tasks_config = dict(self.config.items("Settings"))
            settings_config = dict(self.config.items("Settings"))
            self.master = master
            master.title("PyAutoRaid Task Selector")

            main_frame = ttk.Frame(master)
            main_frame.pack(fill=tkinter.BOTH, expand=True)
            config_keys = ['rewards', 'daily_ten_classic_arena', 'clanboss']

            # Automated Mode Checkbox
            self.automated_mode = tkinter.IntVar()
            if settings_config.get("automated_mode") == 'True':
                self.automated_mode.set(1)
            self.chk_automated_mode = ttk.Checkbutton(
                main_frame, text="Automated Mode", variable=self.automated_mode,
            )
            self.chk_automated_mode.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="W")

            self.separator = ttk.Separator(main_frame, orient='horizontal')
            self.separator.grid(row=1, column=0, padx=10, pady=5, sticky="EW")

            def checkbox_callback(var_name, index, mode, config_key, var):
                updated_value = str(bool(var.get()))
                self.config['Settings'][config_key] = updated_value
                with open('PARconfig.ini', 'w') as configfile:
                    self.config.write(configfile)
                logger.info(f"Checkbox {config_key} updated to {updated_value}")

            self.checkbox_texts = [
                "Collect Rewards", "Ten Classic Arena Battles", "Clan Boss",
            ]
            self.checkboxes = []
            self.vars = []

            for i, text in enumerate(config_keys, start=2):
                guiname = self.checkbox_texts[i - 2]
                var = tkinter.IntVar()
                config_key = config_keys[i - 2]
                if tasks_config.get(config_key, 'False') == 'True':
                    var.set(1)
                var.trace_add(
                    'write',
                    lambda vn, idx, md, v=var, ck=config_key: checkbox_callback(vn, idx, md, ck, v),
                )
                chk = ttk.Checkbutton(main_frame, text=guiname, variable=var)
                chk.grid(row=i, column=0, padx=10, pady=(0, 5), sticky="W")
                self.checkboxes.append(chk)
                self.vars.append(var)

            self.btn_manual_run = ttk.Button(main_frame, text="Manual Run", command=self.manual_run)
            self.btn_manual_run.grid(row=len(self.checkbox_texts) + 3, column=0, padx=10, pady=(5, 5), sticky="W")

            self.btn_quit_all = ttk.Button(main_frame, text="Quit All", command=self.quit_all)
            self.btn_quit_all.grid(row=len(self.checkbox_texts) + 3, column=1, padx=10, pady=(5, 5), sticky="E")
            logger.info("GUI initialized successfully.")
        except Exception as e:
            logger.error(f"Error initializing GUI: {e}")

    def manual_run(self):
        try:
            logger.info("Manual run button clicked.")
            if self.app:
                self.app.trigger_manual_run(True)
        except Exception as e:
            logger.error(f"Error in manual_run: {e}")

    def quit_all(self, timer=False):
        try:
            logger.info("Quitting all processes.")
            processes = ["DailyQuests.exe", "PyAutoRaid.exe", "python.exe",
                         "DailyQuests.py", "PlariumPlay.exe"]
            if timer:
                processes.insert(0, "Raid.exe")
            BaseDaily.kill_processes(*processes)
        except Exception as e:
            logger.error(f"Error in quit_all: {e}")

    def timer_thread(self):
        try:
            timeout = 1800
            self.timer = threading.Timer(timeout, lambda: self.quit_all(timer=True))
            self.timer.name = "timer_thread"
            self.timer.daemon = True
            self.timer.start()
            logger.info("Timer thread started.")
        except Exception as e:
            logger.error(f"Error in timer_thread: {e}")


def on_closing():
    try:
        if my_gui.timer.is_alive():
            my_gui.timer.cancel()
            logger.info("Timer cancelled.")
        if my_gui.daily_thread.is_alive():
            my_gui.daily_thread.join(timeout=1)
            logger.info("Daily thread joined.")
        root.destroy()
        logger.info("Application closed.")
    except Exception as e:
        logger.error(f"Error on closing: {e}")
        root.destroy()


if __name__ == "__main__":
    root = ThemedTk(theme="equilux")
    root.geometry("500x560+10+240")
    my_gui = GUI(root)
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()
