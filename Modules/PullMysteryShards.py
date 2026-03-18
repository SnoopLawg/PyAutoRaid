"""Standalone mystery shard farming script."""

import pyautogui
import time
import logging

from base import BaseDaily, locate_and_click, locate_and_click_loop, asset

logging.basicConfig(
    filename='Logging.log',
    format='%(levelname)s:%(message)s',
    encoding='utf-8',
    level=logging.DEBUG,
)
with open('Logging.log', 'w'):
    pass

logger = logging.getLogger(__name__)


class Daily(BaseDaily):
    def __init__(self):
        super().__init__(master=None)
        self.summoned_champs = 0

    def daily_summon_three(self):
        portal_image = asset(self.asset_path, "portal.png")
        daily_as_image = asset(self.asset_path, "dailyAS.png")
        summon_ten_image = asset(self.asset_path, "summonTen.png")
        summon_ten_more_image = asset(self.asset_path, "summonTenMore.png")

        locate_and_click_loop(portal_image, confidence=0.9, sleep_after=2)

        if locate_and_click(daily_as_image, confidence=0.9, sleep_after=2):
            self.summoned_champs = 0
            if locate_and_click(summon_ten_image, confidence=0.9, sleep_after=10):
                self.summoned_champs += 10
                logger.info(f"{self.summoned_champs} summoned")
                for i in range(9):
                    if locate_and_click(summon_ten_more_image, confidence=0.9, sleep_after=10):
                        self.summoned_champs += 10
                        logger.info(f"{self.summoned_champs} summoned")

        self.steps["Daily_summon"] = "Accessed"
        self.delete_popup()
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
            for _ in range(8):
                time.sleep(1)
                pyautogui.click(1101, 330)
                time.sleep(1)
                pyautogui.click(560, 642)
                time.sleep(1)
                for _ in range(2):
                    for x in range(560, 700, 60):
                        for y in range(570, 750, 90):
                            pyautogui.click(x, y)
                            time.sleep(1)
                            locate_and_click(sacrifice1_image, confidence=0.9, sleep_after=2)
                    time.sleep(3)
                    if locate_and_click(tavern_upgrade_image, confidence=0.9, sleep_after=2):
                        loc = pyautogui.locateOnScreen(tavern_upgrade_image, confidence=0.9)
                        if loc:
                            px, py = pyautogui.center(loc)
                            pyautogui.click(px, py)
                        time.sleep(3)
                    time.sleep(2)
                    locate_and_click(sacrifice_image, confidence=0.9, sleep_after=2)

        self.steps["Tavern_upgrades"] = "True"
        self.delete_popup()
        self.back_to_bastion()


if __name__ == "__main__":
    daily = Daily()
    daily.daily_summon_three()
    daily.daily_tavern_upgrade()
