import pyautogui
import logging
import os
import time
import random
import configparser
import tkinter
import threading
from tkinter import ttk
from ttkthemes import ThemedTk

from base import (
    BaseDaily, locate_and_click, locate_and_click_loop,
    wait_for_image, asset, MAX_RETRIES,
)

logging.basicConfig(
    filename='Logging.log',
    format='%(levelname)s:%(message)s',
    encoding='utf-8',
    level=logging.DEBUG,
)
# Clear log file on start
with open('Logging.log', 'w'):
    pass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Named pixel coordinates (1920x1080, game window 900x600 centered)
# ---------------------------------------------------------------------------
TAVERN_CHAMP_POS = (1101, 330)
TAVERN_SACRIFICE_POS = (560, 642)
TAVERN_SACRIFICE_X_RANGE = range(560, 700, 60)
TAVERN_SACRIFICE_Y_RANGE = range(570, 750, 90)
ARTIFACT_POSITIONS = [(1218, 400), (1069, 411), (963, 797)]
ARTIFACT_SELECT_POS = (1123, 665)
ARTIFACT_RANDOM_X = (770, 1145)
ARTIFACT_RANDOM_Y = (371, 814)
ARTIFACT_PIECE_POS = (729, 309)
TIMED_REWARDS_Y = 500
TIMED_REWARDS_X_RANGE = range(669, 1269, 100)
TIMED_REWARDS_END_X = 1269
ARENA_SCROLL_POS = (969, 788)
ARENA_REGIONS = [
    (1215, 423, 167, 58, 1304, 457),
    (1215, 508, 167, 58, 1304, 540),
    (1215, 596, 167, 58, 1303, 625),
    (1215, 681, 167, 58, 1304, 711),
    (1208, 762, 190, 68, 1304, 800),
]


class Daily(BaseDaily):
    def __init__(self, master):
        super().__init__(master)
        self.classic_battles = 0
        self.AS_bought = 0
        self.MS_bought = 0
        self.GR_upgrades = 0
        self.quests_completed = 0
        self.summoned_champs = 0
        self.config = configparser.ConfigParser()

    def run(self):
        while self.running:
            self.config.read('DQconfig.ini')
            self.ToDo = dict(self.config.items("QuestsToDo"))
            self.settings_config = dict(self.config.items("Settings"))

            if self.settings_config.get("automated_mode", 'False') == 'True':
                try:
                    for key in self.ToDo:
                        if self.ToDo[key].lower() == 'true':
                            method = getattr(self, key, None)
                            if method:
                                method()
                            else:
                                logger.warning(f"Method for {key} not found.")
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
                    for key in self.ToDo:
                        if self.ToDo[key].lower() == 'true':
                            method = getattr(self, key, None)
                            if method:
                                method()
                            else:
                                logger.warning(f"Method for {key} not found.")
                    self.trigger_manual_run(False)
            time.sleep(1)

    # --- Quest methods ---

    def rewards(self):
        """Collect daily rewards (shop, guardian ring, timed rewards, clan, quests, inbox)."""
        shop_image = asset(self.asset_path, "shop.png")
        offers_image = asset(self.asset_path, "offers.png")
        free_gift_image = asset(self.asset_path, "claimFreeGift.png")
        default_claim_image = asset(self.asset_path, "defaultClaim.png")
        mystery_shard_image = asset(self.asset_path, "mysteryShard.png")

        self.steps["Shop_claimed"] = []

        # Shop
        locate_and_click_loop(shop_image, sleep_after=2)
        time.sleep(2)

        # Mystery shards
        if locate_and_click(mystery_shard_image, sleep_after=2):
            if locate_and_click(default_claim_image, sleep_after=3):
                self.steps["Shop_claimed"].append("Mystery Shard")

        # Offers
        if locate_and_click(offers_image, confidence=0.9, sleep_after=3):
            for i in range(724, 1400, 50):
                pyautogui.click(i, 333)
                if locate_and_click(free_gift_image, sleep_after=1):
                    self.steps["Shop_claimed"].append("Free Gift")
            time.sleep(1.5)
        self.back_to_bastion()
        self.delete_popup()

        # Guardian Ring
        self.daily_guardian_ring()
        # Timed Rewards
        self.daily_timed_rewards()
        # Clan
        self.daily_clan()
        # Quests
        self.daily_quest_claims()
        # Inbox
        self.daily_inbox()

    def daily_guardian_ring(self):
        guardian_ring_image = asset(self.asset_path, "guardianRing.png")
        gr_upgrade_image = asset(self.asset_path, "GRupgrade.png")

        if locate_and_click(guardian_ring_image, sleep_after=4):
            self.GR_upgrades = locate_and_click_loop(gr_upgrade_image, sleep_after=2)
            self.steps["GR_upgrades"] = self.GR_upgrades
            self.back_to_bastion()
            self.delete_popup()

    def daily_timed_rewards(self):
        time_rewards_image = asset(self.asset_path, "timeRewards.png")
        red_dot_image = asset(self.asset_path, "redNotificationDot.png")

        if locate_and_click(time_rewards_image, sleep_after=2):
            locate_and_click_loop(red_dot_image, sleep_after=1)
            for i in TIMED_REWARDS_X_RANGE:
                time.sleep(0.2)
                pyautogui.click(i, TIMED_REWARDS_Y)
            time.sleep(1)
            pyautogui.click(TIMED_REWARDS_END_X, TIMED_REWARDS_Y)
            pyautogui.click(TIMED_REWARDS_END_X, TIMED_REWARDS_Y)
            self.steps["Timed_rewards"] = "Collected"
            self.back_to_bastion()
            self.delete_popup()
        self.steps["7_campaign_battles"] = "Not Collected"

    def daily_clan(self):
        clan_btn_image = asset(self.asset_path, "clanBTN.png")
        clan_members_image = asset(self.asset_path, "clanMembers.png")
        clan_check_in_image = asset(self.asset_path, "clanCheckIn.png")
        clan_treasure_image = asset(self.asset_path, "clanTreasure.png")
        red_dot_image = asset(self.asset_path, "redNotificationDot.png")

        if locate_and_click(clan_btn_image, sleep_after=1):
            locate_and_click(clan_members_image, sleep_after=1)
            locate_and_click_loop(clan_check_in_image, sleep_after=1)
            locate_and_click(clan_treasure_image, sleep_after=1)

            dots = list(pyautogui.locateAllOnScreen(red_dot_image, confidence=0.8) or [])
            for dot in dots:
                dx, dy = pyautogui.center(dot)
                pyautogui.click(dx, dy + 10)
                time.sleep(3)
            self.steps["Daily_clan"] = "Accessed"
            self.back_to_bastion()

    def daily_quest_claims(self):
        quests_image = asset(self.asset_path, "quests.png")
        quest_claim_image = asset(self.asset_path, "questClaim.png")
        advanced_quests_image = asset(self.asset_path, "advancedQuests.png")

        if locate_and_click(quests_image, sleep_after=2):
            self.quests_completed += locate_and_click_loop(quest_claim_image, sleep_after=1)
            if locate_and_click(advanced_quests_image, sleep_after=1):
                self.quests_completed += locate_and_click_loop(quest_claim_image, sleep_after=1)
            self.steps["Quests_completed"] = self.quests_completed
            self.back_to_bastion()
            self.delete_popup()
        else:
            self.steps["Quests_Completed"] = "Not Accessed"

    def daily_inbox(self):
        time.sleep(1)
        pyautogui.hotkey("i")
        inbox_items = [
            "inbox_energy", "inbox_brew", "inbox_purple_forge",
            "inbox_yellow_forge", "inbox_coin", "inbox_potion",
        ]
        for item in inbox_items:
            png = asset(self.asset_path, f"{item}.png")
            time.sleep(0.3)
            retries = 0
            while retries < MAX_RETRIES:
                location = pyautogui.locateOnScreen(png, confidence=0.7)
                if not location:
                    break
                pyautogui.moveTo(location)
                pyautogui.moveRel(250, 0)
                pyautogui.click()
                time.sleep(2)
                retries += 1
        self.steps["daily_inbox"] = "Accessed"
        self.back_to_bastion()
        self.delete_popup()

    def daily_seven_boss_battles(self):
        campaign_images = ["battleBTN.png", "campaignButtonJump.png", "campaignStart.png"]
        self.campaignreached = 0
        for img in campaign_images:
            if locate_and_click(asset(self.asset_path, img), confidence=0.9, sleep_after=2):
                self.campaignreached += 1

        if self.campaignreached == 3:
            replay_image = asset(self.asset_path, "replayCampaign.png")
            bastion_image = asset(self.asset_path, "bastion.png")

            for _ in range(6):
                wait_for_image(replay_image, timeout=120)
                locate_and_click_loop(replay_image, confidence=0.9, sleep_after=2)

            wait_for_image(replay_image, timeout=120)
            locate_and_click_loop(bastion_image, confidence=0.9, sleep_after=2)
            self.steps["7_campaign_battles"] = "Accessed"
            self.back_to_bastion()
            self.delete_popup()

    def daily_summon_three(self):
        portal_image = asset(self.asset_path, "portal.png")
        daily_as_image = asset(self.asset_path, "dailyAS.png")
        summon_one_image = asset(self.asset_path, "summonOne.png")
        summon_one_more_image = asset(self.asset_path, "summonOneMore.png")

        locate_and_click_loop(portal_image, confidence=0.9, sleep_after=2)

        if locate_and_click(daily_as_image, confidence=0.9, sleep_after=2):
            self.summoned_champs = 0
            if locate_and_click(summon_one_image, confidence=0.9, sleep_after=6):
                self.summoned_champs += 1
                for _ in range(5):
                    locate_and_click(summon_one_more_image, confidence=0.9, sleep_after=8)
                    self.summoned_champs += 1

        self.steps["Daily_summon"] = "Accessed"
        self.delete_popup()
        self.back_to_bastion()
        self.delete_popup()

    def daily_artifact_upgrade(self):
        upgrade_artifact_image = asset(self.asset_path, "upgradeArtifact.png")
        upgrade_image = asset(self.asset_path, "upgrade.png")

        pyautogui.hotkey('c')
        time.sleep(1)
        for pos in ARTIFACT_POSITIONS:
            pyautogui.click(*pos)
            time.sleep(1)
        pyautogui.dragRel(0, -800, duration=3)
        time.sleep(1)
        pyautogui.click(*ARTIFACT_SELECT_POS)
        time.sleep(1)
        pyautogui.dragRel(0, -800, duration=3)
        time.sleep(2)
        pyautogui.click(*ARTIFACT_PIECE_POS)

        x = random.randint(*ARTIFACT_RANDOM_X)
        y = random.randint(*ARTIFACT_RANDOM_Y)
        pyautogui.click(x, y)

        # Wait for upgrade artifact button
        retries = 0
        while retries < MAX_RETRIES:
            if pyautogui.locateOnScreen(upgrade_artifact_image, confidence=0.8):
                break
            time.sleep(2)
            x = random.randint(*ARTIFACT_RANDOM_X)
            y = random.randint(*ARTIFACT_RANDOM_Y)
            pyautogui.click(x, y)
            time.sleep(2)
            retries += 1

        locate_and_click_loop(upgrade_artifact_image, confidence=0.9, sleep_after=2)

        for _ in range(6):
            locate_and_click(upgrade_image, confidence=0.9, sleep_after=4)

        self.steps["Artifact_upgrades"] = "True"
        self.back_to_bastion()
        self.delete_popup()

    def daily_tavern_upgrade(self):
        tav_image = asset(self.asset_path, "tav.png")
        tavern_descending_image = asset(self.asset_path, "tavern_descending.png")
        sacrifice1_image = asset(self.asset_path, "sacrifice1.png")
        tavern_upgrade_image = asset(self.asset_path, "tavernUpgrade.png")
        sacrifice_image = asset(self.asset_path, "sacrifice.png")

        locate_and_click(tav_image, confidence=0.9, sleep_after=2)

        if locate_and_click(tavern_descending_image, confidence=0.9, sleep_after=2):
            pyautogui.click(560, 390)
            for _ in range(1):
                for x in TAVERN_SACRIFICE_X_RANGE:
                    for y in TAVERN_SACRIFICE_Y_RANGE:
                        pyautogui.click(x, y)
                        time.sleep(1)
                        if self.summoned_champs == 6:
                            locate_and_click(sacrifice1_image, confidence=0.9, sleep_after=2)
                time.sleep(2)

                if locate_and_click(tavern_upgrade_image, confidence=0.9, sleep_after=2):
                    loc = pyautogui.locateOnScreen(tavern_upgrade_image, confidence=0.9)
                    if loc:
                        x, y = pyautogui.center(loc)
                        pyautogui.click(x, y)
                    time.sleep(3)
                time.sleep(1)
                locate_and_click(sacrifice_image, confidence=0.9, sleep_after=2)

        self.steps["Tavern_upgrades"] = "True"
        self.delete_popup()
        self.back_to_bastion()

    def daily_five_classic_arena(self):
        self.delete_popup()

        battle_btn_image = asset(self.asset_path, "battleBTN.png")
        arena_tab_image = asset(self.asset_path, "arenaTab.png")
        classic_arena_image = asset(self.asset_path, "classicArena.png")
        arena_refresh_image = asset(self.asset_path, "arenaRefresh.png")
        arena_battle_image = asset(self.asset_path, "arenaBattle.png")
        arena_confirm_image = asset(self.asset_path, "arenaConfirm.png")
        classic_arena_refill_image = asset(self.asset_path, "classicArenaRefill.png")
        arena_start_image = asset(self.asset_path, "arenaStart.png")
        tap_to_continue_image = asset(self.asset_path, "tapToContinue.png")

        locate_and_click_loop(battle_btn_image, confidence=0.9, sleep_after=2)
        locate_and_click_loop(arena_tab_image, confidence=0.9, sleep_after=2)

        if not locate_and_click(classic_arena_image, confidence=0.9, sleep_after=2):
            logger.warning("Classic Arena not found.")
            return

        locate_and_click_loop(arena_refresh_image, confidence=0.9, sleep_after=2)

        for rx, ry, rw, rh, cx, cy in ARENA_REGIONS:
            if pyautogui.locateOnScreen(arena_battle_image, region=(rx, ry, rw, rh), confidence=0.6):
                pyautogui.click(cx, cy)
                time.sleep(3)

                # Confirm tokens
                locate_and_click_loop(arena_confirm_image, confidence=0.9, sleep_after=4)

                if pyautogui.locateOnScreen(classic_arena_refill_image, confidence=0.8):
                    break

                time.sleep(4)
                locate_and_click(arena_start_image, confidence=0.9, sleep_after=0)

                # Wait for battle to finish
                wait_for_image(tap_to_continue_image, timeout=120)

                retries = 0
                while retries < MAX_RETRIES:
                    loc = pyautogui.locateOnScreen(tap_to_continue_image, confidence=0.8)
                    if not loc:
                        break
                    time.sleep(1)
                    x, y = pyautogui.center(loc)
                    pyautogui.click(x, y)
                    self.classic_battles += 1
                    time.sleep(1)
                    pyautogui.click(x, y)
                    time.sleep(3)
                    retries += 1

            time.sleep(1)
            pyautogui.doubleClick(*ARENA_SCROLL_POS, interval=1)

        self.steps["classic_arena_battles"] = f"{self.classic_battles} total classic arena battles fought"
        self.back_to_bastion()
        self.delete_popup()


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------
class GUI:
    def __init__(self, master):
        self.app = Daily(master)
        self.timer_thread()
        self.daily_thread = threading.Thread(target=self.app.run)
        self.daily_thread.start()
        self.config = configparser.ConfigParser()
        self.config.read('DQconfig.ini')
        tasks_config = dict(self.config.items("QuestsToDo"))
        settings_config = dict(self.config.items("Settings"))
        self.master = master
        master.title("DailyQuests Task Selector")

        main_frame = ttk.Frame(master)
        main_frame.pack(fill=tkinter.BOTH, expand=True)
        config_keys = [
            'rewards', 'daily_seven_boss_battles', 'daily_summon_three',
            'daily_artifact_upgrade', 'daily_tavern_upgrade', 'daily_five_classic_arena',
        ]

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
            self.config['QuestsToDo'][config_key] = updated_value
            with open('DQconfig.ini', 'w') as configfile:
                self.config.write(configfile)

        self.checkbox_texts = [
            "Collect Rewards", "Campaign Battles", "Summon Six Mystery Shards",
            "Upgrade Artifact", "Upgrade Champion", "5 Classic Arena Battles",
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

    def manual_run(self):
        if self.app:
            self.app.trigger_manual_run(True)

    def quit_all(self, timer=False):
        processes = ["DailyQuests.exe", "PyAutoRaid.exe", "python.exe",
                     "DailyQuests.py", "PlariumPlay.exe"]
        if timer:
            processes.insert(0, "Raid.exe")
        BaseDaily.kill_processes(*processes)

    def timer_thread(self):
        timeout = 1800
        self.timer = threading.Timer(timeout, lambda: self.quit_all(timer=True))
        self.timer.name = "timer_thread"
        self.timer.daemon = True
        self.timer.start()


def on_closing():
    try:
        if my_gui.timer.is_alive():
            my_gui.timer.cancel()
        if my_gui.daily_thread.is_alive():
            my_gui.daily_thread.join(timeout=1)
        root.destroy()
    except Exception:
        root.destroy()


if __name__ == "__main__":
    root = ThemedTk(theme="equilux")
    root.geometry("500x560+10+240")
    my_gui = GUI(root)
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()
