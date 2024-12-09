import pyautogui
import platform
import tkinter
import logging
import os
import sys
import subprocess
import time
import configparser
import pygetwindow
import datetime
import threading
from screeninfo import get_monitors
from tkinter import messagebox
from tkinter import ttk
from tkinter import *
from ttkthemes import ThemedTk
import pyscreeze
pyscreeze.USE_IMAGE_NOT_FOUND_EXCEPTION = False
# Configure logging
logging.basicConfig(
    filename='PyAutoRaid.log',
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filemode='w',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

# Base Command class
class Command:
    def execute(self):
        pass

# Command classes for each task
class DailyGemMineCommand(Command):
    def __init__(self, app):
        self.app = app

    def execute(self):
        try:
            logger.info("Starting Daily Gem Mine task.")
            # Gem Mine
            pyautogui.click(583, 595)
            time.sleep(2)
            pyautogui.hotkey("esc")  # Escape gem mine
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
            self.app.delete_popup()
            time.sleep(5)
            market_image = os.path.join(self.app.asset_path, "theMarket.png")
            if pyautogui.locateOnScreen(market_image, confidence=0.8):
                theMarketx, theMarkety = pyautogui.locateCenterOnScreen(
                    market_image, confidence=0.8
                )
                pyautogui.click(theMarketx, theMarkety)
                time.sleep(2)
                shop_shard_image = os.path.join(self.app.asset_path, "shopShard.png")
                get_shard_image = os.path.join(self.app.asset_path, "getShard.png")
                market_AS_image = os.path.join(self.app.asset_path, "marketAS.png")
                get_AS_image = os.path.join(self.app.asset_path, "getAS.png")
                # Purchase Mystery Shards
                while pyautogui.locateOnScreen(shop_shard_image, confidence=0.8):
                    shopShardx, shopShardy = pyautogui.locateCenterOnScreen(
                        shop_shard_image, confidence=0.8
                    )
                    pyautogui.click(shopShardx, shopShardy)
                    time.sleep(2)
                    self.app.steps["Market"] = "Opened"
                    self.app.steps["Market_purchases"] = "None"
                    while pyautogui.locateOnScreen(get_shard_image, confidence=0.8):
                        getShardx, getShardy = pyautogui.locateCenterOnScreen(
                            get_shard_image, confidence=0.8
                        )
                        pyautogui.click(getShardx, getShardy, duration=2)
                        self.MS_bought += 1
                        logger.info(f"Purchased a Mystery Shard. Total purchased: {self.MS_bought}")
                        time.sleep(1)
                    time.sleep(2)
                # Purchase Ancient Shards
                while pyautogui.locateOnScreen(market_AS_image, confidence=0.8):
                    marketASx, marketASy = pyautogui.locateCenterOnScreen(
                        market_AS_image, confidence=0.8
                    )
                    pyautogui.click(marketASx, marketASy)
                    time.sleep(2)
                    while pyautogui.locateOnScreen(get_AS_image, confidence=0.8):
                        getASx, getASy = pyautogui.locateCenterOnScreen(
                            get_AS_image, confidence=0.8
                        )
                        pyautogui.click(getASx, getASy)
                        self.AS_bought += 1
                        logger.info(f"Purchased an Ancient Shard. Total purchased: {self.AS_bought}")
                        time.sleep(1)
                    time.sleep(2)
                self.app.steps[
                    "Market_purchases"
                ] = f"{self.MS_bought} mystery shards purchased, and {self.AS_bought} ancient shards purchased"
                self.app.back_to_bastion()
                self.app.delete_popup()
                logger.info("Completed Daily Market Purchase task.")
            else:
                logger.warning("Market button not found on screen.")
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
            self.app.steps["Shop_claimed"] = []
            shop_btn_image = os.path.join(self.app.asset_path, "shopBTN.png")
            claim_AS_image = os.path.join(self.app.asset_path, "claimAS.png")
            default_claim_image = os.path.join(self.app.asset_path, "defaultClaim.png")
            claim_MS_image = os.path.join(self.app.asset_path, "claimMS.png")
            offers_image = os.path.join(self.app.asset_path, "offers.png")
            claim_free_gift_image = os.path.join(self.app.asset_path, "claimFreeGift.png")

            if pyautogui.locateOnScreen(shop_btn_image, confidence=0.8):
                shopBTNx, shopBTNy = pyautogui.locateCenterOnScreen(
                    shop_btn_image, confidence=0.8
                )
                pyautogui.click(shopBTNx, shopBTNy)
                time.sleep(2)
                # Claim Ancient Shard
                while pyautogui.locateOnScreen(claim_AS_image, confidence=0.8):
                    claimASx, claimASy = pyautogui.locateCenterOnScreen(
                        claim_AS_image, confidence=0.8
                    )
                    pyautogui.click(claimASx, claimASy)
                    time.sleep(2)
                    while pyautogui.locateOnScreen(default_claim_image, confidence=0.8):
                        defaultClaimx, defaultClaimy = pyautogui.locateCenterOnScreen(
                            default_claim_image, confidence=0.8
                        )
                        pyautogui.click(defaultClaimx, defaultClaimy)
                        self.app.steps["Shop_claimed"].append("Ancient Shard")
                        logger.info("Claimed Ancient Shard from shop.")
                        time.sleep(3)
                # Claim Mystery Shard
                while pyautogui.locateOnScreen(claim_MS_image, confidence=0.8):
                    claimMSx, claimMSy = pyautogui.locateCenterOnScreen(
                        claim_MS_image, confidence=0.8
                    )
                    pyautogui.click(claimMSx, claimMSy)
                    time.sleep(5)
                    while pyautogui.locateOnScreen(default_claim_image, confidence=0.8):
                        defaultClaimx, defaultClaimy = pyautogui.locateCenterOnScreen(
                            default_claim_image, confidence=0.8
                        )
                        pyautogui.click(defaultClaimx, defaultClaimy)
                        self.app.steps["Shop_claimed"].append("Mystery Shard")
                        logger.info("Claimed Mystery Shard from shop.")
                        time.sleep(3)
                # Claim Free Gifts from offers
                while pyautogui.locateOnScreen(offers_image, confidence=0.9):
                    offersx, offersy = pyautogui.locateCenterOnScreen(
                        offers_image, confidence=0.8
                    )
                    pyautogui.click(offersx, offersy)
                    time.sleep(3)
                    # Click through all offers
                    for i in range(724, 1400, 50):
                        pyautogui.click(i, 333)
                        if pyautogui.locateOnScreen(claim_free_gift_image, confidence=0.8):
                            freegiftx, freegifty = pyautogui.locateCenterOnScreen(
                                claim_free_gift_image, confidence=0.8
                            )
                            pyautogui.click(freegiftx, freegifty)
                            self.app.steps["Shop_claimed"].append("Free Gift")
                            logger.info("Claimed Free Gift from offers.")
                            time.sleep(1)
                    time.sleep(1.5)
                self.app.back_to_bastion()
                self.app.delete_popup()
                logger.info("Completed Daily Shop task.")
            else:
                logger.warning("Shop button not found on screen.")
        except Exception as e:
            logger.error(f"Error in DailyShopCommand: {e}")
            self.app.back_to_bastion()
            self.app.delete_popup()

class DailyGuardianRingCommand(Command):
    def __init__(self, app):
        self.app = app
        self.GR_upgrades = 0

    def execute(self):
        try:
            logger.info("Starting Daily Guardian Ring task.")
            guardian_ring_image = os.path.join(self.app.asset_path, "guardianRing.png")
            GR_upgrade_image = os.path.join(self.app.asset_path, "GRupgrade.png")
            if pyautogui.locateOnScreen(guardian_ring_image, confidence=0.8):
                guardianRingx, guardianRingy = pyautogui.locateCenterOnScreen(
                    guardian_ring_image, confidence=0.8
                )
                pyautogui.click(guardianRingx, guardianRingy)
                time.sleep(4)
                while pyautogui.locateOnScreen(GR_upgrade_image, confidence=0.8):
                    GRupgradex, GRupgradey = pyautogui.locateCenterOnScreen(
                        GR_upgrade_image, confidence=0.8
                    )
                    pyautogui.click(GRupgradex, GRupgradey)
                    self.GR_upgrades += 1
                    logger.info(f"Performed Guardian Ring upgrade. Total upgrades: {self.GR_upgrades}")
                    time.sleep(2)
                self.app.steps["GR_upgrades"] = self.GR_upgrades
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
            time_rewards_image = os.path.join(self.app.asset_path, "timeRewards.png")
            red_dot_image = os.path.join(self.app.asset_path, "redNotificationDot.png")
            if pyautogui.locateOnScreen(time_rewards_image, confidence=0.8):
                timeRewardsx, timeRewardsy = pyautogui.locateCenterOnScreen(
                    time_rewards_image, confidence=0.8
                )
                pyautogui.click(timeRewardsx, timeRewardsy)
                time.sleep(2)
                while pyautogui.locateOnScreen(red_dot_image, confidence=0.8):
                    redx, redy = pyautogui.locateCenterOnScreen(
                        red_dot_image, confidence=0.8
                    )
                    pyautogui.click(redx, redy)
                    time.sleep(1)
                for i in range(669, 1269, 100):
                    time.sleep(0.2)
                    pyautogui.click(i, 500)
                time.sleep(1)
                pyautogui.click(1269, 500)
                pyautogui.click(1269, 500)
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
            clan_btn_image = os.path.join(self.app.asset_path, "clanBTN.png")
            clan_members_image = os.path.join(self.app.asset_path, "clanMembers.png")
            clan_check_in_image = os.path.join(self.app.asset_path, "clanCheckIn.png")
            clan_treasure_image = os.path.join(self.app.asset_path, "clanTreasure.png")
            red_dot_image = os.path.join(self.app.asset_path, "redNotificationDot.png")

            if pyautogui.locateOnScreen(clan_btn_image, confidence=0.8):
                clanBTNx, clanBTNy = pyautogui.locateCenterOnScreen(
                    clan_btn_image, confidence=0.8
                )
                pyautogui.click(clanBTNx, clanBTNy)
                time.sleep(1)
                if pyautogui.locateOnScreen(clan_members_image, confidence=0.8):
                    clanMembersx, clanMembersy = pyautogui.locateCenterOnScreen(
                        clan_members_image, confidence=0.8
                    )
                    pyautogui.click(clanMembersx, clanMembersy)
                    time.sleep(2)
                while pyautogui.locateOnScreen(clan_check_in_image, confidence=0.8):
                    clanCheckInx, clanCheckIny = pyautogui.locateCenterOnScreen(
                        clan_check_in_image, confidence=0.8
                    )
                    pyautogui.click(clanCheckInx, clanCheckIny)
                    time.sleep(1)
                if pyautogui.locateOnScreen(clan_treasure_image, confidence=0.8):
                    clanTreasurex, clanTreasurey = pyautogui.locateCenterOnScreen(
                        clan_treasure_image, confidence=0.8
                    )
                    pyautogui.click(clanTreasurex, clanTreasurey)
                    time.sleep(1)
                if pyautogui.locateAllOnScreen(red_dot_image, confidence=0.8):
                    for dotsx, doty, z, c in pyautogui.locateAllOnScreen(
                        red_dot_image, confidence=0.8
                    ):
                        pyautogui.click(dotsx, doty + 10)
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
            quests_image = os.path.join(self.app.asset_path, "quests.png")
            quest_claim_image = os.path.join(self.app.asset_path, "questClaim.png")
            advanced_quests_image = os.path.join(self.app.asset_path, "advancedQuests.png")

            if pyautogui.locateOnScreen(quests_image, confidence=0.8):
                questsx, questsy = pyautogui.locateCenterOnScreen(
                    quests_image, confidence=0.8
                )
                pyautogui.click(questsx, questsy)
                time.sleep(2)
                while pyautogui.locateOnScreen(quest_claim_image, confidence=0.8):
                    questClaimx, questClaimy = pyautogui.locateCenterOnScreen(
                        quest_claim_image, confidence=0.8
                    )
                    pyautogui.click(questClaimx, questClaimy)
                    self.quests_completed += 1
                    logger.info(f"Claimed a quest reward. Total claimed: {self.quests_completed}")
                    time.sleep(1)
                if pyautogui.locateOnScreen(advanced_quests_image, confidence=0.8):
                    advancedQuestsx, advancedQuestsy = pyautogui.locateCenterOnScreen(
                        advanced_quests_image, confidence=0.8
                    )
                    pyautogui.click(advancedQuestsx, advancedQuestsy)
                    time.sleep(1)
                if pyautogui.locateOnScreen(quest_claim_image, confidence=0.9):
                    questClaimx, questClaimy = pyautogui.locateCenterOnScreen(
                        quest_claim_image, confidence=0.8
                    )
                    pyautogui.click(questClaimx, questClaimy)
                    self.quests_completed += 1
                    logger.info(f"Claimed an advanced quest reward. Total claimed: {self.quests_completed}")
                    time.sleep(1)
                self.app.steps["Quests_completed"] = self.quests_completed
                self.app.back_to_bastion()
                self.app.delete_popup()
                logger.info("Completed Daily Quest Claims task.")
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
                "inbox_energy",
                "inbox_brew",
                "inbox_purple_forge",
                "inbox_yellow_forge",
                "inbox_coin",
                "inbox_potion",
            ]
            for i in inbox_items:
                png = os.path.join(self.app.asset_path, f"{i}.png")
                time.sleep(0.3)
                while pyautogui.locateOnScreen(png, confidence=0.8):
                    energy = pyautogui.locateOnScreen(png, confidence=0.8)
                    pyautogui.moveTo(energy)
                    pyautogui.moveRel(250, 0)
                    pyautogui.click()
                    time.sleep(2)
                    logger.info(f"Collected inbox item: {i}")
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
            battle_btn_image = os.path.join(self.app.asset_path, "battleBTN.png")
            arena_tab_image = os.path.join(self.app.asset_path, "arenaTab.png")
            classic_arena_image = os.path.join(self.app.asset_path, "classicArena.png")
            arena_refresh_image = os.path.join(self.app.asset_path, "arenaRefresh.png")
            arena_battle_image = os.path.join(self.app.asset_path, "arenaBattle.png")
            arena_confirm_image = os.path.join(self.app.asset_path, "arenaConfirm.png")
            classic_arena_refill_image = os.path.join(self.app.asset_path, "classicArenaRefill.png")
            arena_start_image = os.path.join(self.app.asset_path, "arenaStart.png")
            tap_to_continue_image = os.path.join(self.app.asset_path, "tapToContinue.png")

            while pyautogui.locateOnScreen(battle_btn_image, confidence=0.8):
                battlex, battley = pyautogui.locateCenterOnScreen(
                    battle_btn_image, confidence=0.9
                )
                pyautogui.click(battlex, battley)
                time.sleep(2)
            while pyautogui.locateOnScreen(arena_tab_image, confidence=0.8):
                battlex, battley = pyautogui.locateCenterOnScreen(
                    arena_tab_image, confidence=0.9
                )
                pyautogui.click(battlex, battley)
                time.sleep(2)
            while pyautogui.locateOnScreen(classic_arena_image, confidence=0.8):
                battlex, battley = pyautogui.locateCenterOnScreen(
                    classic_arena_image, confidence=0.9
                )
                pyautogui.click(battlex, battley)
                time.sleep(2)
                regions = [
                    [1215, 423, 167, 58, [1304, 457]],
                    [1215, 508, 167, 58, [1304, 540]],
                    [1215, 596, 167, 58, [1303, 625]],
                    [1215, 681, 167, 58, [1304, 711]],
                    [1208, 762, 190, 68, [1304, 800]],
                ]
                for j in range(0, 2):
                    while pyautogui.locateOnScreen(arena_refresh_image, confidence=0.8):
                        battlex, battley = pyautogui.locateCenterOnScreen(
                            arena_refresh_image, confidence=0.9
                        )
                        pyautogui.click(battlex, battley)
                        time.sleep(2)
                    for i in regions:
                        if pyautogui.locateOnScreen(
                            arena_battle_image,
                            region=(i[0], i[1], i[2], i[3]),
                            confidence=0.6,
                        ):
                            pyautogui.click(i[4][0], i[4][1])
                            time.sleep(3)
                            # Replenish tokens or quit if out of them
                            while pyautogui.locateOnScreen(arena_confirm_image, confidence=0.8):
                                battlex, battley = pyautogui.locateCenterOnScreen(
                                    arena_confirm_image, confidence=0.9
                                )
                                pyautogui.click(battlex, battley)
                                logger.info("Confirmed arena tokens.")
                                time.sleep(5)
                                pyautogui.click(i[4][0], i[4][1])
                            if pyautogui.locateOnScreen(classic_arena_refill_image, confidence=0.8):
                                self.app.steps["Classic_Arena"] = "Ran out of coins"
                                self.app.steps[
                                    "classic_arena_battles"
                                ] = f"{self.classic_battles} total classic arena battles fought"
                                self.app.back_to_bastion()
                                self.app.delete_popup()
                                logger.info("Ran out of arena coins. Exiting task.")
                                return
                            time.sleep(4)
                            if pyautogui.locateOnScreen(arena_start_image, confidence=0.8):
                                battlex, battley = pyautogui.locateCenterOnScreen(
                                    arena_start_image, confidence=0.9
                                )
                                pyautogui.click(battlex, battley)
                            # First battle
                                logger.debug("Waiting for 'Tap to Continue' screen.")
                            while not pyautogui.locateOnScreen(tap_to_continue_image, confidence=0.8):
                                time.sleep(1)
                            while pyautogui.locateOnScreen(tap_to_continue_image, confidence=0.8):
                                time.sleep(1)
                                goBackx, goBacky = pyautogui.locateCenterOnScreen(
                                    tap_to_continue_image, confidence=0.8
                                )
                                pyautogui.click(goBackx, goBacky)
                                self.classic_battles += 1
                                logger.info(f"Completed an arena battle. Total battles: {self.classic_battles}")
                                time.sleep(1)
                                pyautogui.click(goBackx, goBacky)
                                time.sleep(3)
                            if j == 1:
                                pyautogui.doubleClick(969, 788, interval=1)
                                pyautogui.dragRel(0, -381, duration=2)
                                time.sleep(3)
                        time.sleep(1)
                        pyautogui.doubleClick(969, 788, interval=1)

                    time.sleep(1)
                    if j == 0:
                        pyautogui.doubleClick(969, 788, interval=1)
                        pyautogui.dragRel(0, -380, duration=2)
                        time.sleep(3)
            time.sleep(3)
            self.app.steps[
                "classic_arena_battles"
            ] = f"{self.classic_battles} total classic arena battles fought"
            self.app.back_to_bastion()
            self.app.delete_popup()
            logger.info(f"{self.classic_battles} total classic arena battles fought")
            logger.info("Completed Daily Ten Classic Arena task.")
        except Exception as e:
            logger.error(f"Error in DailyTenClassicArenaCommand: {e}")

class ClanBossCommand(Command):
    def __init__(self, app):
        self.app = app

    def execute(self):
        try:
            logger.info("Starting Clan Boss task.")
            CBDIFFICULTYS = [
                "ultra-nightmare",
                "nightmare",
                "brutal",
                "hard",
                "normal",
                "easy",
            ]
            time.sleep(1.5)
            logger.debug(f"self.app is an instance of {type(self.app)}")
            self.app.delete_popup()

            # Construct image paths
            battle_btn_image = os.path.join(self.app.asset_path, "battleBTN.png")
            demon_lord2_image = os.path.join(self.app.asset_path, "demonLord2.png")
            CB_card_image = os.path.join(self.app.asset_path, "CB.png")
            CB_reward_image = os.path.join(self.app.asset_path, "CBreward.png")
            nightmare_claimed_image = os.path.join(self.app.asset_path, "nightmareClaimed.png")
            CB_claim_image = os.path.join(self.app.asset_path, "CBclaim.png")
            CB_hard_image = os.path.join(self.app.asset_path, "CBhard.png")
            CB_battle_image = os.path.join(self.app.asset_path, "CBbattle.png")
            CB_no_key_image = os.path.join(self.app.asset_path, "CBnokey.png")
            CB_start_image = os.path.join(self.app.asset_path, "CBstart.png")
            # CB_continue_image = os.path.join(self.app.asset_path, "CBcontinue.png")
            goto_bastion_image = os.path.join(self.app.asset_path, "gotoBastion.png")

            # Navigate to battle screen
            while pyautogui.locateOnScreen(battle_btn_image, confidence=0.8):
                battlex, battley = pyautogui.locateCenterOnScreen(
                    battle_btn_image, confidence=0.8
                )
                pyautogui.click(battlex, battley)
                time.sleep(2)

            while pyautogui.locateOnScreen(CB_card_image, confidence=0.8):
                battlex, battley = pyautogui.locateCenterOnScreen(
                    CB_card_image, confidence=0.8
                )
                pyautogui.click(battlex, battley)
                time.sleep(2)

            # Navigate to demon lord
            while pyautogui.locateOnScreen(demon_lord2_image, confidence=0.8):
                demonLord2x, demonLord2y = pyautogui.locateCenterOnScreen(
                    demon_lord2_image, confidence=0.8
                )
                pyautogui.click(demonLord2x, demonLord2y)
                time.sleep(4)

            # Scroll and collect rewards
            pyautogui.click(1080, 724)
            pyautogui.drag(0, -200, duration=1)
            while pyautogui.locateOnScreen(CB_reward_image, confidence=0.8):
                for CBreward in pyautogui.locateAllOnScreen(CB_reward_image, confidence=0.8):
                    CBrewardx, CBrewardy = pyautogui.center(CBreward)
                    pyautogui.click(CBrewardx, CBrewardy)
                    time.sleep(2)
                    for ClaimButton in pyautogui.locateAllOnScreen(CB_claim_image, confidence=0.8):
                        Claimx, Claimy = pyautogui.center(ClaimButton)
                        pyautogui.click(Claimx, Claimy)
                        time.sleep(3)
                        pyautogui.click(Claimx, Claimy)

            # Collect claimed rewards
            while pyautogui.locateOnScreen(nightmare_claimed_image, confidence=0.8):
                nightmareClaimedx, nightmareClaimedy = pyautogui.locateCenterOnScreen(
                    CB_claim_image, confidence=0.8
                )
                pyautogui.click(nightmareClaimedx, nightmareClaimedy)
                time.sleep(1)
                pyautogui.click()
                time.sleep(1)
                pyautogui.click()
                logger.info("Collected claimed reward.")

            while pyautogui.locateOnScreen(CB_claim_image, confidence=0.8):
                CBclaimx, CBclaimy = pyautogui.locateCenterOnScreen(
                    CB_claim_image, confidence=0.8
                )
                pyautogui.click(CBclaimx, CBclaimy)
                time.sleep(1)
                pyautogui.click()
                logger.info("Collected Clan Boss claim.")

            time.sleep(2)
            pyautogui.click(1080, 724)
            pyautogui.drag(0, +200, duration=1)
            time.sleep(1)

            # Begin fighting clan boss
            while pyautogui.locateOnScreen(CB_hard_image, confidence=0.8):
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
                    pyautogui.click(1080, 724)
                    pyautogui.drag(0, -200, duration=1)
                    pyautogui.click(1080, 690)

                if difficulty == '':
                    logger.info("No Clan Boss fights planned or available.")
                    break

                logger.info(f"Preparing to fight Clan Boss at difficulty: {difficulty}")
                pyautogui.click(xCB, yCB)

                while pyautogui.locateOnScreen(CB_battle_image, confidence=0.8):
                    CBbattlex, CBbattley = pyautogui.locateCenterOnScreen(
                        CB_battle_image, confidence=0.8
                    )
                    time.sleep(2)
                    pyautogui.click(CBbattlex, CBbattley)
                    time.sleep(1)
                    if pyautogui.locateOnScreen(CB_no_key_image, confidence=0.8):
                        logger.warning("No keys available for Clan Boss battle.")
                        break
                time.sleep(1)

            time.sleep(5)
            if pyautogui.locateOnScreen(CB_start_image, confidence=0.8):
                CBstartx, CBstarty = pyautogui.locateCenterOnScreen(
                    CB_start_image, confidence=0.8
                )
                time.sleep(2)
                pyautogui.click(CBstartx, CBstarty)
                logger.info("Started Clan Boss battle.")
                time.sleep(1)

                # Wait for battle to finish
                # battle_in_progress = True
                # while battle_in_progress:
                #     if pyautogui.locateOnScreen(CB_continue_image, confidence=0.8):
                #         CBcontinuex, CBcontinuey = pyautogui.locateCenterOnScreen(
                #             CB_continue_image, confidence=0.8
                #         )
                #         pyautogui.click(CBcontinuex, CBcontinuey)
                #         logger.info("Clan Boss battle finished.")
                #         battle_in_progress = False
                #     else:
                #         time.sleep(10)  # Wait before checking again

                # Return to Bastion
                while not pyautogui.locateOnScreen(goto_bastion_image, confidence=0.8):
                    time.sleep(1)
                gotoBastionx, gotoBastiony = pyautogui.locateCenterOnScreen(
                goto_bastion_image, confidence=0.8
                )
                pyautogui.click(gotoBastionx, gotoBastiony)
                time.sleep(1)
                logger.info("Returned to Bastion.")

                # Update config with new fight count
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

# Main Daily class
class Daily:
    def __init__(self, master):
        self.running = True
        self.master = master
        logging.basicConfig(filename='Logging.log', format='%(levelname)s:%(message)s', encoding='utf-8', level=logging.DEBUG)
        with open('Logging.log', 'w'):
            pass
        self.steps = {}
        self.resetCBDay()
        self.OS = self.Check_os()
        self.raidLoc = self.find_raid_path()
        self.asset_path = self.get_asset_path()
        self.folders_for_exe()
        if len(pygetwindow.getWindowsWithTitle("Raid: Shadow Legends")) < 1:
            self.open_raid()
        else:
            self.initiate_raid(False)
        os.system("taskkill /f /im PlariumPlay.exe")
        self.width = 0
        self.height = 0
        self.classic_battles = 0
        self.GR_upgrades = 0
        self.quests_completed = 0
        self.AS_bought = 0
        self.MS_bought = 0
        self.manual_run_triggered = False

        self.command_registry = {
            'rewards': RewardsCommand(self),
            'daily_ten_classic_arena': DailyTenClassicArenaCommand(self),
            'clanboss': ClanBossCommand(self),
            # Add other commands as needed
        }

    # Initialization methods with error handling and logging
    def resetCBDay(self):
        try:
            self.config = configparser.ConfigParser()
            self.utc_now = datetime.datetime.now(datetime.timezone.utc)
            self.check_previous_days()
            logger.info("Reset CB Day successfully.")
        except Exception as e:
            logger.error(f"Error in resetCBDay: {e}")

    def check_previous_days(self):
        try:
            today_date_str = self.utc_now.strftime("%d/%m/%Y")
            self.config_file(today_date_str)
            self.settings_config = dict(self.config.items("Settings"))
            self.config.read('PARconfig.ini')
            configdate = self.config.get('Settings', 'UTC_today')
            days_to_check = 60  # Example: Check up to 60 days in the past

            for day in range(1, days_to_check + 1):
                past_date = self.utc_now - datetime.timedelta(days=day)
                past_date_str = past_date.strftime("%d/%m/%Y")
                if past_date_str == configdate and self.utc_now.hour >= 10:
                    self.config_file(today_date_str, True)
                    logger.info("Previous day config adjusted.")
                    return True
        except Exception as e:
            logger.error(f"Error in check_previous_days: {e}")

    def config_file(self, day, adjust=False):
        try:
            if os.path.exists("PARconfig.ini"):
                self.config.read('PARconfig.ini')
            else:
                self.config['Settings'] = {'UTC_today': day, 'rewards': True, 'clanboss': True, 'automated_mode': True, 'daily_ten_classic_arena': True}
                self.config['PlannedClanBossFightsToday'] = {'Easy': 0, 'Normal': 0, 'Hard': 0, 'Brutal': 0, 'Nightmare': 1, 'Ultra-Nightmare': 3}
                self.config['ActualClanBossFightsToday'] = {'Easy': 0, 'Normal': 0, 'Hard': 0, 'Brutal': 0, 'Nightmare': 0, 'Ultra-Nightmare': 0}
                self.config['XYclanbossCoordinates'] = {'EasyX': 1080, 'EasyY': 'IDK Coords yet', 'NormalX': 1080, 'NormalY': 'IDK Coords yet', 'HardX': 1080, 'HardY': 'IDK Coords yet', 'BrutalX': 1080, 'BrutalY': 647, 'NightmareX': 1080, 'NightmareY': 724, 'Ultra-NightmareX': 1080, 'Ultra-NightmareY': 690}
                with open('PARconfig.ini', 'w') as configfile:
                    self.config.write(configfile)
            if adjust:
                self.config['Settings'] = {'UTC_today': day, 'rewards': self.settings_config['rewards'], 'clanboss': self.settings_config['clanboss'], 'automated_mode': self.settings_config['automated_mode'], 'daily_ten_classic_arena': self.settings_config['daily_ten_classic_arena']}
                self.config['ActualClanBossFightsToday'] = {'Easy': 0, 'Normal': 0, 'Hard': 0, 'Brutal': 0, 'Nightmare': 0, 'Ultra-Nightmare': 0}
                with open('PARconfig.ini', 'w') as configfile:
                    self.config.write(configfile)
            logger.info("Configuration file set up successfully.")
        except Exception as e:
            logger.error(f"Error in config_file: {e}")

    def trigger_manual_run(self, TF):
        self.manual_run_triggered = TF
        logger.info(f"Manual run triggered: {TF}")

    def folders_for_exe(self):
        try:
            if getattr(sys, 'frozen', False):
                # The application is frozen
                self.asset_path = os.path.join(sys._MEIPASS, 'assets')
                self.steps["Exe_path"] = "True"
                return True
            else:
                self.steps["Exe_path"] = "False"
                return False
        except Exception as e:
            logger.error(f"Error in folders_for_exe: {e}")

    def Check_os(self):
        try:
            operating_system = platform.system()
            if operating_system == "Windows":
                self.steps["OS"] = "True"
                return operating_system
            else:
                tkinter.messagebox.showerror(
                    "Error",
                    "Unrecognized operating system (WINDOWS ONLY)",
                )
                logging.error("Identified this computer as something other than Windows operating system. This program only works with Windows.")
                sys.exit(1)
        except Exception as e:
            logger.error(f"Error in Check_os: {e}")

    def find_raid_path(self):
        try:
            appdata_local = os.path.join(os.environ['LOCALAPPDATA'])
            raid_feature = "Raid.exe"
            for root, dirs, files in os.walk(appdata_local):
                if raid_feature in dirs or raid_feature in files:
                    raidloc = os.path.join(root, raid_feature)
                    logging.debug(f"Found Raid.exe installed at {raidloc}")
                    self.steps["Raid_path"] = "True"
                    return raidloc
            self.steps["Raid_path"] = "False"
            logging.error("Raid.exe was not found.")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Error in find_raid_path: {e}")

    def get_asset_path(self):
        try:
            # Start with the directory of the current script
            current_dir = os.path.dirname(os.path.abspath(__file__))
            while True:
                # Construct the path to the assets folder
                self.asset_path = os.path.join(current_dir, 'assets')

                # Check if the assets path exists
                if os.path.exists(self.asset_path):
                    self.steps["Asset_path"] = "True"
                    logger.info(f"Assets folder found at {self.asset_path}")
                    return self.asset_path

                # Move up one directory level
                new_dir = os.path.dirname(current_dir)
                if new_dir == current_dir:
                    # We are at the root directory and didn't find the assets folder
                    logger.error("Assets folder not found.")
                    self.steps["Asset_path"] = "False"
                    if self.folders_for_exe() == False:
                        logging.error("Could not find the assets folder. This folder contains all of the images needed for this program to use. It must be in the same folder as this program.")
                        sys.exit(1)
                    return None
                else:
                    current_dir = new_dir
        except Exception as e:
            logger.error(f"Error in get_asset_path: {e}")
            sys.exit(1)

    def open_raid(self):
        try:
            logger.info("Attempting to open Raid: Shadow Legends.")
            subprocess.Popen(
                [
                    os.path.join(os.getenv("LOCALAPPDATA"), "PlariumPlay\\PlariumPlay.exe"),
                    "--args",
                    "-gameid=101",
                    "-tray-start",
                ]
            )
            self.wait_for_game_window(title="Raid: Shadow Legends", timeout=100)
        except Exception as e:
            logger.error(f"Error in open_raid: {e}")

    def wait_for_game_window(self, title, timeout):
        try:
            logger.info("Waiting for game window to appear.")
            start_time = time.time()
            while time.time() - start_time < timeout:
                if pyautogui.getWindowsWithTitle(title):
                    logging.debug("Game window found, game should be loading in now.")
                    self.steps["Open_raid"] = "True"
                    self.initiate_raid(True)
                    return
                time.sleep(5)
            self.steps["Open_raid"] = "False"
            logging.error("Raid took too long to open, game window not found.")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Error in wait_for_game_window: {e}")

    # Utility methods with error handling and logging
    def delete_popup(self):
        logger.info("Attempting to close any pop-up ads.")
        exit_add_image = os.path.join(self.asset_path, "exitAdd.png")
        logger.debug(f"Looking for exitAdd.png at: {exit_add_image}")
        max_attempts = 5
        attempts = 0
        while attempts < max_attempts:
            try:
                location = pyautogui.locateOnScreen(exit_add_image, confidence=0.8)
                if location:
                    adx, ady = pyautogui.center(location)
                    pyautogui.click(adx, ady)
                    time.sleep(4)
                    attempts += 1
                    logger.debug(f"Closed a pop-up ad. Attempt {attempts}.")
                else:
                    logger.info("No pop-up ads found.")
                    break  # Exit the loop since no ad is found
            except Exception as e:
                break  # Exit the loop or handle as needed
        if attempts >= max_attempts:
            logger.warning("Reached maximum attempts to close pop-up ads.")
        else:
            logger.info("No pop-up ads found or all ads closed.")



    def back_to_bastion(self):
        try:
            logger.info("Navigating back to Bastion.")
            close_LO = None
            max_attempts = 3
            attempts = 0
            go_back_image = os.path.join(self.asset_path, "goBack.png")
            lightning_offer_text_image = os.path.join(self.asset_path, "lightningOfferText.png")
            while attempts < max_attempts:
                if pyautogui.locateOnScreen(lightning_offer_text_image, confidence=0.7):
                    close_LO = os.path.join(self.asset_path, "closeLO.png")
                while pyautogui.locateOnScreen(go_back_image, confidence=0.7):
                    bastionx, bastiony = pyautogui.locateCenterOnScreen(
                        go_back_image, confidence=0.7
                    )
                    pyautogui.click(bastionx, bastiony)
                    time.sleep(2)
                    if close_LO:
                        if pyautogui.locateOnScreen(close_LO, confidence=0.7):
                            bastionx, bastiony = pyautogui.locateCenterOnScreen(
                                close_LO, confidence=0.7
                            )
                            pyautogui.click(bastionx, bastiony)
                            time.sleep(2)
                    logger.info("Successfully navigated back to Bastion.")
                return
            else:
                attempts += 1
                logger.debug(f"goBack.png not found. Attempt {attempts}/{max_attempts}. Retrying...")
                time.sleep(1)
            logger.warning("Failed to navigate back to Bastion after several attempts.")
        except Exception as e:
            logger.error(f"Error in back_to_bastion: {e}")

    def get_screen_info(self):
        try:
            for m in get_monitors():
                self.width = m.width
                self.height = m.height
                main = m.is_primary
                if self.width != 1920 or self.height != 1080:
                    tkinter.messagebox.showerror(
                        "Warning",
                        "Your Screen pixel is not 1920 by 1080. This may cause issues",
                    )
                    logger.warning("Screen resolution is not 1920x1080.")
                if main == True:
                    center_width = int((self.width / 2) - 450)
                    center_height = int((self.height / 2) - 300)
                    logger.info(f"Screen info obtained: width={self.width}, height={self.height}")
                    return (center_width, center_height)
        except Exception as e:
            logger.error(f"Error in get_screen_info: {e}")

    def window_sizing_centering(self):
        try:
            center = self.get_screen_info()
            win_list = pygetwindow.getWindowsWithTitle("Raid: Shadow Legends")
            if win_list:
                win = win_list[0]
                # Minimize and then maximize the window
                win.minimize()
                win.restore()
                win.size = (900, 600)
                win.moveTo(center[0], center[1])
                logger.info("Game window resized and centered.")
            else:
                logger.warning("No window found with the title 'Raid: Shadow Legends'")
        except Exception as e:
            logger.error(f"Error in window_sizing_centering: {e}")

    def initiate_raid(self, not_open):
        try:
            self.window_sizing_centering()
            exit_add_image = os.path.join(self.asset_path, "exitAdd.png")
            while True:
                try:
                    # Attempt to locate the image
                    if pyautogui.locateOnScreen(exit_add_image, confidence=0.7) is not None:
                        logger.info("Image found. Breaking the loop.")
                        break
                    else:
                        logger.info("Image not found; retrying...")
                    time.sleep(1)  # Pause between checks
                except pyautogui.ImageNotFoundException:
                    logger.error("Error during image search.")
                    time.sleep(1)  # Optional: slight delay before retrying in case of error
            self.back_to_bastion()
            self.delete_popup()
            self.steps["Initiate_raid"] = "True"
            logger.info("Raid game initiated.")
        except Exception as e:
            logger.error(f"Error in initiate_raid: {e}")

    def close_gui(self):
        try:
            if self.master:
                self.master.after(0, self.master.destroy)
                logger.info("GUI closed.")
        except Exception as e:
            logger.error(f"Error in close_gui: {e}")

    # Implement the rewards command
    def rewards_command(self):
        # Create a composite command to run all reward-related tasks
        logger.info("Starting Rewards tasks.")
        commands = [
            DailyGemMineCommand(self),
            DailyMarketPurchaseCommand(self),
            DailyShopCommand(self),
            DailyGuardianRingCommand(self),
            DailyTimedRewardsCommand(self),
            DailyClanCommand(self),
            DailyQuestClaimsCommand(self),
            DailyInboxCommand(self),
            # Add other reward-related commands
        ]
        for command in commands:
            command.execute()
        logger.info("Completed Rewards tasks.")

    # Main run method with error handling and logging
    def run(self):
        while self.running:
            try:
                # Re-read the config file to update the settings
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
                                else:
                                    logger.warning(f"Command for {key} not found.")
                        self.close_gui()
                        os.system("taskkill /f /im Raid.exe")
                        break
                    except Exception as e:
                        logger.error(f"Error during automated tasks: {e}")
                        self.close_gui()
                        os.system("taskkill /f /im Raid.exe")
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
                                else:
                                    logger.warning(f"Command for {key} not found.")
                        self.trigger_manual_run(False)
                time.sleep(1)  # Sleep to prevent busy waiting
            except Exception as e:
                logger.error(f"Unexpected error in run method: {e}")
                self.close_gui()
                os.system("taskkill /f /im Raid.exe")
                break

# GUI class with error handling and logging
class GUI:
    def __init__(self, master):
        try:
            self.app = Daily(master)  # Create the Daily instance
            self.timer_thread()
            self.daily_thread = threading.Thread(target=self.app.run)  # Create the thread
            self.daily_thread.start()  # Start the thread
            self.daily_thread.name = "PAR"
            self.config = configparser.ConfigParser()
            self.config.read('PARconfig.ini')
            tasks_config = dict(self.config.items("Settings"))
            settings_config = dict(self.config.items("Settings"))
            self.master = master
            master.title("PyAutoRaid Task Selector")

            # Creating a ttk Frame which will contain all other widgets
            main_frame = ttk.Frame(master)
            main_frame.pack(fill=tkinter.BOTH, expand=True)
            config_keys = ['rewards', 'daily_ten_classic_arena', 'clanboss']
            # Automated Mode Checkbox
            self.automated_mode = tkinter.IntVar()
            if settings_config.get("automated_mode") == 'True':
                self.automated_mode.set(1)
            self.chk_automated_mode = ttk.Checkbutton(main_frame, text="Automated Mode", variable=self.automated_mode)
            self.chk_automated_mode.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="W")

            # Separator
            self.separator = ttk.Separator(main_frame, orient='horizontal')
            self.separator.grid(row=1, column=0, padx=10, pady=5, sticky="EW")

            def checkbox_callback(var_name, index, mode, config_key, var):
                updated_value = str(bool(var.get()))
                self.config['Settings'][config_key] = updated_value
                with open('PARconfig.ini', 'w') as configfile:
                    self.config.write(configfile)
                logger.info(f"Checkbox {config_key} updated to {updated_value}")

            # Other Checkboxes
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
                # Set trace on the variable
                var.trace_add('write', lambda var_name, index, mode, var=var, config_key=config_key: checkbox_callback(var_name, index, mode, config_key, var))
                chk = ttk.Checkbutton(main_frame, text=guiname, variable=var)
                chk.grid(row=i, column=0, padx=10, pady=(0, 5), sticky="W")
                self.checkboxes.append(chk)
                self.vars.append(var)
            # Buttons in the main_frame
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
            if timer:
                os.system("taskkill /f /im Raid.exe")
            os.system("taskkill /f /im DailyQuests.exe")
            os.system("taskkill /f /im PyAutoRaid.exe")
            os.system("taskkill /f /im python.exe")
            os.system("taskkill /f /im DailyQuests.py")
            os.system("taskkill /f /im PlariumPlay.exe")
        except Exception as e:
            logger.error(f"Error in quit_all: {e}")

    def timer_thread(self):
        try:
            timeout = 1800
            # Create a timer that will call quit_all() after the timeout
            self.timer = threading.Timer(timeout, lambda: self.quit_all(timer=True))
            self.timer.name = "timer_thread"
            self.timer.daemon = True
            # Start the timer
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
    root.protocol("WM_DELETE_WINDOW", on_closing)  # To ensure clean exit
    root.mainloop()
