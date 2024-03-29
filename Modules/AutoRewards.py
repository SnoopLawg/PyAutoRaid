# Retrieve all rewards at Bastion
from re import sub
import pyautogui
import time
from Modules.Logger import *
from Modules.LoopFindImage import LoopFindImage
import pathlib

from Modules.RAIDGUI import AutoReward, submission
import sqlite3 as sql
import os
import pygetwindow as gw
import sys

if getattr(sys, "frozen", False):
    # we are running in a bundle
    DIR = sys._MEIPASS
    setting=os.getcwd()
else:
    # we are running in a normal Python environment
    DIR = os.getcwd()
    setting=os.getcwd()
ASSETS_PATH = os.path.join(DIR, "assets")
DB_PATH = os.path.join(setting, "Settings.db")
connection = sql.connect(DB_PATH)
cursor = connection.cursor()


def AutoRewards():
    cursor.execute("SELECT * FROM PyAutoRaid")
    results = cursor.fetchall()
    connection.commit()
    Run = results
    Run = Run[0][1]
    active_raid_window = 0
    if Run == "True":
        Log_start("AutoRewards")
        while (
            pyautogui.locateOnScreen(
                ASSETS_PATH + "\\exitAdd.png",
                confidence=0.8,
            )
            == None
        ):
            active_raid_window += 1
            if active_raid_window <= 1:
                Raid = gw.getWindowsWithTitle("Raid: Shadow Legends")[0]
                Raid.minimize()
                Raid.restore()
            while (
                pyautogui.locateOnScreen(
                    ASSETS_PATH + "\\tapToContinue.png",
                    confidence=0.8,
                )
                != None
            ):
                time.sleep(1)
                goBackx, goBacky = pyautogui.locateCenterOnScreen(
                    ASSETS_PATH + "\\tapToContinue.png",
                    confidence=0.8,
                )
                pyautogui.click(goBackx, goBacky)
                print("weekly classic arena")
                time.sleep(1)
                LoopFindImage(
                    ASSETS_PATH + "\\goBack.png",
                    "\n back to Bastion x ",
                )
        while (
            pyautogui.locateOnScreen(
                ASSETS_PATH + "\\exitAdd.png",
                confidence=0.8,
            )
            != None
        ):
            adx, ady = pyautogui.locateCenterOnScreen(
                ASSETS_PATH + "\\exitAdd.png",
                confidence=0.8,
            )
            pyautogui.click(adx, ady)
            time.sleep(2)
            Closelightningvar = ASSETS_PATH + "\\closeLightningDeal.png"
            while (
                pyautogui.locateOnScreen(
                    r"{}".format(Closelightningvar),
                    confidence=0.8,
                )
                != None
            ):
                ldx, ldy = pyautogui.locateCenterOnScreen(
                    ASSETS_PATH + "\\closeLightningDeal.png",
                    confidence=0.8,
                )
                pyautogui.click(ldx, ldy)
                time.sleep(2)
        ##
        os.system("taskkill /f /im PlariumPlay.exe")
        # Gem Mine
        Log_start("to click Gem Mine")
        pyautogui.click(583, 595)
        time.sleep(2)
        pyautogui.hotkey("esc")  # esc gem mine
        time.sleep(2)
        LoopFindImage(
            ASSETS_PATH + "\\exitAdd.png",
            "\n ad closed ",
        )  # if gem mine empty closes the quit window so doesnt quit
        time.sleep(1)
        Log_finish("Gem Mine")
        # MARKET - check for shards-
        if pyautogui.locateOnScreen(
            ASSETS_PATH + "\\theMarket.png",
            confidence=0.8,
        ):
            theMarketx, theMarkety = pyautogui.locateCenterOnScreen(
                ASSETS_PATH + "\\theMarket.png",
                confidence=0.8,
            )
            Log_start("Checking Market")
            pyautogui.click(theMarketx, theMarkety)
            time.sleep(2)
            while (
                pyautogui.locateOnScreen(
                    ASSETS_PATH + "\\shopShard.png",
                    confidence=0.8,
                )
                != None
            ):
                shopShardx, shopShardy = pyautogui.locateCenterOnScreen(
                    ASSETS_PATH + "\\shopShard.png",
                    confidence=0.8,
                )
                Log_start("clicking mystery shard in Market")
                pyautogui.click(shopShardx, shopShardy,)
                time.sleep(2)
                while (
                    pyautogui.locateOnScreen(
                        ASSETS_PATH + "\\getShard.png",
                        confidence=0.8,
                    )
                    != None
                ):
                    getShardx, getShardy = pyautogui.locateCenterOnScreen(
                        ASSETS_PATH + "\\getShard.png",
                        confidence=0.8,
                    )
                    pyautogui.click(getShardx, getShardy,duration=2)
                    Log_finish("buying shard in Market")
                    continue
                
                time.sleep(2)
            while (
                pyautogui.locateOnScreen(
                    ASSETS_PATH + "\\marketAS.png",
                    confidence=0.8,
                )
                != None
            ):
                marketASx, marketASy = pyautogui.locateCenterOnScreen(
                    ASSETS_PATH + "\\marketAS.png",
                    confidence=0.8,
                )
                pyautogui.click(marketASx, marketASy)
                time.sleep(2)
                while (
                    pyautogui.locateOnScreen(
                        ASSETS_PATH + "\\getAS.png",
                        confidence=0.8,
                    )
                    != None
                ):
                    getASx, getASy = pyautogui.locateCenterOnScreen(
                        ASSETS_PATH + "\\getAS.png",
                        confidence=0.8,
                    )
                    Log_finish("buying Ancient Shard")
                    pyautogui.click(getASx, getASy)
                    continue
                
                time.sleep(2)
            LoopFindImage(
                ASSETS_PATH + "\\goBack.png",
                "\n back to Bastion x ",
            )
            LoopFindImage(
                ASSETS_PATH + "\\exitAdd.png",
                "\n ad closed ",
            )

        # SHOP - claim AS, claim MS, check offers for goodieBag,miniPack,smallPack,regularPack, then claim
        if pyautogui.locateOnScreen(
            ASSETS_PATH + "\\shopBTN.png",
            confidence=0.8,
        ):
            shopBTNx, shopBTNy = pyautogui.locateCenterOnScreen(
                ASSETS_PATH + "\\shopBTN.png",
                confidence=0.8,
            )
            pyautogui.click(shopBTNx, shopBTNy)
            Log_start("Shop")
            time.sleep(2)
            while (
                pyautogui.locateOnScreen(
                    ASSETS_PATH + "\\claimAS.png",
                    confidence=0.8,
                )
                != None
            ):
                claimASx, claimASy = pyautogui.locateCenterOnScreen(
                    ASSETS_PATH + "\\claimAS.png",
                    confidence=0.8,
                )
                pyautogui.click(claimASx, claimASy)
                Log_finish("claiming Ancient Shard")
                time.sleep(2)
                while (
                    pyautogui.locateOnScreen(
                        ASSETS_PATH + "\\defaultClaim.png",
                        confidence=0.8,
                    )
                    != None
                ):
                    defaultClaimx, defaultClaimy = pyautogui.locateCenterOnScreen(
                        ASSETS_PATH + "\\defaultClaim.png",
                        confidence=0.8,
                    )
                    pyautogui.click(defaultClaimx, defaultClaimy)
                    
                    time.sleep(3)
            while (
                pyautogui.locateOnScreen(
                    ASSETS_PATH + "\\claimMS.png",
                    confidence=0.8,
                )
                != None
            ):
                claimMSx, claimMSy = pyautogui.locateCenterOnScreen(
                    ASSETS_PATH + "\\claimMS.png",
                    confidence=0.8,
                )
                pyautogui.click(claimMSx, claimMSy)
                Log_finish("claiming Mystery Shard")
                time.sleep(5)
                while (
                    pyautogui.locateOnScreen(
                        ASSETS_PATH + "\\defaultClaim.png",
                        confidence=0.8,
                    )
                    != None
                ):
                    defaultClaimx, defaultClaimy = pyautogui.locateCenterOnScreen(
                        ASSETS_PATH + "\\defaultClaim.png",
                        confidence=0.8,
                    )
                    pyautogui.click(defaultClaimx, defaultClaimy)
                    Log_finish("Claiming free bundle")
                    time.sleep(3)
            while (
                pyautogui.locateOnScreen(
                    ASSETS_PATH + "\\offers.png",
                    confidence=0.9,
                )
                != None
            ):
                offersx, offersy = pyautogui.locateCenterOnScreen(
                    ASSETS_PATH + "\\offers.png",
                    confidence=0.8,
                )
                pyautogui.click(offersx, offersy)
                time.sleep(3)
                if pyautogui.locateOnScreen(
                    ASSETS_PATH + "\\goodieBag.png",
                    confidence=0.8,
                ):
                    goodieBagx, goodieBagy = pyautogui.locateCenterOnScreen(
                        ASSETS_PATH + "\\goodieBag.png",
                        confidence=0.8,
                    )
                    pyautogui.click(goodieBagx, goodieBagy)
                    Log_finish("Claiming free bundle")
                    time.sleep(1)
                if pyautogui.locateOnScreen(
                    ASSETS_PATH + "\\miniPack.png",
                    confidence=0.8,
                ):
                    goodieBagx, goodieBagy = pyautogui.locateCenterOnScreen(
                        ASSETS_PATH + "\\miniPack.png",
                        confidence=0.8,
                    )
                    pyautogui.click(goodieBagx, goodieBagy)
                    Log_finish("Claiming free bundle")
                    time.sleep(1)
                if pyautogui.locateOnScreen(
                    ASSETS_PATH + "\\smallPack.png",
                    confidence=0.8,
                ):
                    smallPackx, smallPacky = pyautogui.locateCenterOnScreen(
                        ASSETS_PATH + "\\smallPack.png",
                        confidence=0.8,
                    )
                    pyautogui.click(smallPackx, smallPacky)
                    Log_finish("Claiming free bundle")
                    time.sleep(1)
                LoopFindImage(
                    ASSETS_PATH + "\\regularPack.png",
                    "\n regualr pack claimed ",
                )
                pyautogui.click(724, 333)
                LoopFindImage(
                    ASSETS_PATH + "\\claimFreeGift.png",
                    "\n claiming free gift ",
                )
                time.sleep(1)
                pyautogui.click(793, 333)
                LoopFindImage(
                    ASSETS_PATH + "\\claimFreeGift.png",
                    "\n claiming free gift ",
                )
                time.sleep(1.5)
                pyautogui.click(860, 333)
                LoopFindImage(
                    ASSETS_PATH + "\\claimFreeGift.png",
                    "\n claiming free gift ",
                )
                time.sleep(1.5)
                pyautogui.click(928, 333)
                LoopFindImage(
                    ASSETS_PATH + "\\claimFreeGift.png",
                    "\n claiming free gift ",
                )
                time.sleep(1.5)
                pyautogui.click(998, 333)
                LoopFindImage(
                    ASSETS_PATH + "\\claimFreeGift.png",
                    "\n claiming free gift ",
                )
                time.sleep(1.5)
                pyautogui.click(1072, 333)
                LoopFindImage(
                    ASSETS_PATH + "\\claimFreeGift.png",
                    "\n claiming free gift ",
                )
                time.sleep(1.5)
                pyautogui.click(1138, 333)
                LoopFindImage(
                    ASSETS_PATH + "\\claimFreeGift.png",
                    "\n claiming free gift ",
                )
                time.sleep(1.5)
                pyautogui.click(1207, 333)
                LoopFindImage(
                    ASSETS_PATH + "\\claimFreeGift.png",
                    "\n claiming free gift ",
                )
                time.sleep(1.5)
                pyautogui.click(1278, 333)
                LoopFindImage(
                    ASSETS_PATH + "\\claimFreeGift.png",
                    "\n claiming free gift ",
                )
                time.sleep(1.5)
                pyautogui.click(1351, 333)
                LoopFindImage(
                    ASSETS_PATH + "\\claimFreeGift.png",
                    "\n regualr pack claimed ",
                )
                Log_finish("Claiming free bundle")
                time.sleep(1.5)
                # keep adding offers
                while (
                    pyautogui.locateOnScreen(
                        ASSETS_PATH + "\\claimFreeGift.png",
                        confidence=0.8,
                    )
                    != None
                ):
                    miniPackx, miniPacky = pyautogui.locateCenterOnScreen(
                        ASSETS_PATH + "\\claimFreeGift.png",
                        confidence=0.8,
                    )
                    pyautogui.click(miniPackx, miniPacky)
                    Log_finish("Claiming free bundle")
                    time.sleep(1)
            while (
                pyautogui.locateOnScreen(
                    ASSETS_PATH + "\\goBack.png",
                    confidence=0.8,
                )
                != None
            ):
                goBackx, goBacky = pyautogui.locateCenterOnScreen(
                    ASSETS_PATH + "\\goBack.png",
                    confidence=0.8,
                )
                Log_finish("Shop")
                pyautogui.click(goBackx, goBacky)
                time.sleep(1)
            LoopFindImage(
                ASSETS_PATH + "\\exitAdd.png",
                "\n ad closed ",
            )

        # GUARDIAN RING - Upgrade champions
        if pyautogui.locateOnScreen(
            ASSETS_PATH + "\\guardianRing.png",
            confidence=0.8,
        ):
            guardianRingx, guardianRingy = pyautogui.locateCenterOnScreen(
                ASSETS_PATH + "\\guardianRing.png",
                confidence=0.8,
            )
            pyautogui.click(guardianRingx, guardianRingy)
            Log_start("opening Guardian Ring")
            time.sleep(4)
            while (
                pyautogui.locateOnScreen(
                    ASSETS_PATH + "\\GRupgrade.png",
                    confidence=0.8,
                )
                != None
            ):
                GRupgradex, GRupgradey = pyautogui.locateCenterOnScreen(
                    ASSETS_PATH + "\\GRupgrade.png",
                    confidence=0.8,
                )
                pyautogui.click(GRupgradex, GRupgradey)
                Log_start("upgrading champions")
                time.sleep(2)
            while (
                pyautogui.locateOnScreen(
                    ASSETS_PATH + "\\goBack.png",
                    confidence=0.8,
                )
                != None
            ):
                goBackx, goBacky = pyautogui.locateCenterOnScreen(
                    ASSETS_PATH + "\\goBack.png",
                    confidence=0.8,
                )
                pyautogui.click(goBackx, goBacky)
                Log_finish("Guardian Ring")
                time.sleep(2)
            LoopFindImage(
                ASSETS_PATH + "\\exitAdd.png",
                "\n ad closed ",
            )

        # TIME REWARDS
        if pyautogui.locateOnScreen(
            ASSETS_PATH + "\\timeRewards.png",
            confidence=0.8,
        ):
            timeRewardsx, timeRewardsy = pyautogui.locateCenterOnScreen(
                ASSETS_PATH + "\\timeRewards.png",
                confidence=0.8,
            )
            pyautogui.click(timeRewardsx, timeRewardsy)
            Log_start("Time Rewards")
            time.sleep(2)
            while (
                pyautogui.locateOnScreen(
                    ASSETS_PATH + "\\redNotificationDot.png",
                    confidence=0.8,
                )
                != None
            ):
                redx, redy = pyautogui.locateCenterOnScreen(
                    ASSETS_PATH + "\\redNotificationDot.png",
                    confidence=0.8,
                )
                pyautogui.click(redx, redy)
                time.sleep(1)
            pyautogui.click(669, 500)
            pyautogui.click(769, 500)
            pyautogui.click(869, 500)
            pyautogui.click(969, 500)
            pyautogui.click(1069, 500)
            pyautogui.click(1069, 500)
            pyautogui.click(1169, 500)
            pyautogui.click(1269, 500)
            time.sleep(1)
            pyautogui.click(1269, 500)
            Log_finish("Time Rewards")
            while (
                pyautogui.locateOnScreen(
                    ASSETS_PATH + "\\exitAdd.png",
                    confidence=0.8,
                )
                != None
            ):
                adx, ady = pyautogui.locateCenterOnScreen(
                    ASSETS_PATH + "\\exitAdd.png",
                    confidence=0.8,
                )
                pyautogui.click(adx, ady)
                time.sleep(3)

        # CLAN - check in and claim rewards
        if pyautogui.locateOnScreen(
            ASSETS_PATH + "\\clanBTN.png",
            confidence=0.8,
        ):
            clanBTNx, clanBTNy = pyautogui.locateCenterOnScreen(
                ASSETS_PATH + "\\clanBTN.png",
                confidence=0.8,
            )
            pyautogui.click(clanBTNx, clanBTNy)
            Log_start("Clan rewards")
            time.sleep(1)
            while (
                pyautogui.locateOnScreen(
                    ASSETS_PATH + "\\clanMembers.png",
                    confidence=0.8,
                )
                != None
            ):
                clanMembersx, clanMembersy = pyautogui.locateCenterOnScreen(
                    ASSETS_PATH + "\\clanMembers.png",
                    confidence=0.8,
                )
                pyautogui.click(clanMembersx, clanMembersy)
                time.sleep(1)
            while (
                pyautogui.locateOnScreen(
                    ASSETS_PATH + "\\clanCheckIn.png",
                    confidence=0.8,
                )
                != None
            ):
                clanCheckInx, clanCheckIny = pyautogui.locateCenterOnScreen(
                    ASSETS_PATH + "\\clanCheckIn.png",
                    confidence=0.8,
                )
                pyautogui.click(clanCheckInx, clanCheckIny)
                time.sleep(1)
            if pyautogui.locateOnScreen(
                ASSETS_PATH + "\\clanTreasure.png",
                confidence=0.8,
            ):
                clanTreasurex, clanTreasurey = pyautogui.locateCenterOnScreen(
                    ASSETS_PATH + "\\clanTreasure.png",
                    confidence=0.8,
                )
                pyautogui.click(clanTreasurex, clanTreasurey)
                time.sleep(1)
            if (
                pyautogui.locateAllOnScreen(
                    ASSETS_PATH + "\\redNotificationDot.png",
                    confidence=0.8,
                )
                != None
            ):
                for dotsx, doty, z, c in pyautogui.locateAllOnScreen(
                    ASSETS_PATH + "\\redNotificationDot.png",
                    confidence=0.8,
                ):
                    pyautogui.click(dotsx, doty + 10)
                    time.sleep(3)

            while (
                pyautogui.locateOnScreen(
                    ASSETS_PATH + "\\goBack.png",
                    confidence=0.8,
                )
                != None
            ):
                goBackx, goBacky = pyautogui.locateCenterOnScreen(
                    ASSETS_PATH + "\\goBack.png",
                    confidence=0.8,
                )
                pyautogui.click(goBackx, goBacky)
                Log_finish("Clan Rewards")
                time.sleep(3)

        # QUESTS - Check for completed daily and advanced quests and claim
        if pyautogui.locateOnScreen(
            ASSETS_PATH + "\\quests.png",
            confidence=0.8,
        ):
            questsx, questsy = pyautogui.locateCenterOnScreen(
                ASSETS_PATH + "\\quests.png",
                confidence=0.8,
            )
            pyautogui.click(questsx, questsy)
            Log_start("Claiming quest rewards")
            time.sleep(2)
            while (
                pyautogui.locateOnScreen(
                    ASSETS_PATH + "\\questClaim.png",
                    confidence=0.8,
                )
                != None
            ):
                questClaimx, questClaimy = pyautogui.locateCenterOnScreen(
                    ASSETS_PATH + "\\questClaim.png",
                    confidence=0.8,
                )
                pyautogui.click(questClaimx, questClaimy)
                time.sleep(1)
            if pyautogui.locateOnScreen(
                ASSETS_PATH + "\\advancedQuests.png",
                confidence=0.8,
            ):
                advancedQuestsx, advancedQuestsy = pyautogui.locateCenterOnScreen(
                    ASSETS_PATH + "\\advancedQuests.png",
                    confidence=0.8,
                )
                pyautogui.click(advancedQuestsx, advancedQuestsy)
                time.sleep(1)
            while (
                pyautogui.locateOnScreen(
                    ASSETS_PATH + "\\questClaim.png",
                    confidence=0.8,
                )
                != None
            ):
                questClaimx, questClaimy = pyautogui.locateCenterOnScreen(
                    ASSETS_PATH + "\\questClaim.png",
                    confidence=0.8,
                )
                pyautogui.click(questClaimx, questClaimy)
                time.sleep(1)
            while (
                pyautogui.locateOnScreen(
                    ASSETS_PATH + "\\goBack.png",
                    confidence=0.8,
                )
                != None
            ):
                goBackx, goBacky = pyautogui.locateCenterOnScreen(
                    ASSETS_PATH + "\\goBack.png",
                    confidence=0.8,
                )
                pyautogui.click(goBackx, goBacky)
                Log_finish("Claiming Quest rewards")
                time.sleep(1)
    else:
        pass
    ###################################
    # inbox collect
    time.sleep(1)
    pyautogui.hotkey("i")
    Log_start("Inbox")
    while (
        pyautogui.locateOnScreen(
            ASSETS_PATH + "\\inbox_energy.png",
            confidence=0.8,
        )
        != None
    ):
        energy = pyautogui.locateOnScreen(
            ASSETS_PATH + "\\inbox_energy.png",
            confidence=0.8,
        )

        pyautogui.moveTo(energy)
        pyautogui.moveRel(250, 0)
        pyautogui.click()
        time.sleep(2)
    while (
        pyautogui.locateOnScreen(
            ASSETS_PATH + "\\inbox_brew.png",
            confidence=0.8,
        )
        != None
    ):
        brew = pyautogui.locateOnScreen(
            ASSETS_PATH + "\\inbox_brew.png",
            confidence=0.8,
        )

        pyautogui.moveTo(brew)
        pyautogui.moveRel(250, 0)
        pyautogui.click()
        time.sleep(2)
    while (
        pyautogui.locateOnScreen(
            ASSETS_PATH + "\\inbox_purple_forge.png",
            confidence=0.8,
        )
        != None
    ):
        forgepurple = pyautogui.locateOnScreen(
            ASSETS_PATH + "\\inbox_purple_forge.png",
            confidence=0.8,
        )

        pyautogui.moveTo(forgepurple)
        pyautogui.moveRel(250, 0)
        pyautogui.click()
        time.sleep(2)
    while (
        pyautogui.locateOnScreen(
            ASSETS_PATH + "\\inbox_yellow_forge.png",
            confidence=0.8,
        )
        != None
    ):
        forgeyellow = pyautogui.locateOnScreen(
            ASSETS_PATH + "\\inbox_yellow_forge.png",
            confidence=0.8,
        )

        pyautogui.moveTo(forgeyellow)
        pyautogui.moveRel(250, 0)
        pyautogui.click()
        time.sleep(2)
    while (
        pyautogui.locateOnScreen(
            ASSETS_PATH + "\\inbox_coin.png",
            confidence=0.8,
        )
        != None
    ):
        inboxcoin = pyautogui.locateOnScreen(
            ASSETS_PATH + "\\inbox_coin.png",
            confidence=0.8,
        )

        pyautogui.moveTo(inboxcoin)
        pyautogui.moveRel(250, 0)
        pyautogui.click()
        time.sleep(2)
    while (
        pyautogui.locateOnScreen(
            ASSETS_PATH + "\\inbox_potion.png",
            confidence=0.8,
        )
        != None
    ):
        potion = pyautogui.locateOnScreen(
            ASSETS_PATH + "\\inbox_potion.png",
            confidence=0.8,
        )

        pyautogui.moveTo(potion)
        pyautogui.moveRel(250, 0)
        pyautogui.click()
        time.sleep(2)
    while (
        pyautogui.locateOnScreen(
            ASSETS_PATH + "\\goBack.png",
            confidence=0.8,
        )
        != None
    ):
        goBackx, goBacky = pyautogui.locateCenterOnScreen(
            ASSETS_PATH + "\\goBack.png",
            confidence=0.8,
        )
        pyautogui.click(goBackx, goBacky)
        Log_finish("Inbox")
        time.sleep(1)
    Log_finish("AutoRewards")
    Log_info()


if __name__ == "__main__":
    AutoRewards()
