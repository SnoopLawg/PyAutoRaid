# Retrieve all rewards at Bastion
from re import sub
import pyautogui
import time
from LoopFindImage import LoopFindImage
import pathlib
from RAIDGUI import AutoReward, submission
import sqlite3 as sql
import os
import pygetwindow as gw

DIR = str(pathlib.Path().absolute())

connection = sql.connect(DIR + "/AutoRaidAutomate/Settings.db")

cursor = connection.cursor()


def AutoRewards():
    cursor.execute("SELECT * FROM PyAutoRaid")
    results = cursor.fetchall()
    connection.commit()
    Run = results
    Run = Run[0][1]
    active_raid_window = 0
    if Run == "True":
        while (
            pyautogui.locateOnScreen(
                DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\exitAdd.png",
                confidence=0.8,
            )
            == None
        ):

            with open("log.txt", mode="a") as file:
                file.write("\n deleting ads now")

            active_raid_window += 1
            if active_raid_window <= 1:
                Raid = gw.getWindowsWithTitle("Raid: Shadow Legends")[0]
                Raid.minimize()
                Raid.restore()

        LoopFindImage(
            DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\exitAdd.png",
            "\n ad ",
        )
        os.system("taskkill /f /im PlariumPlay.exe")
        # Gem Mine
        pyautogui.click(579, 684)
        time.sleep(2)
        pyautogui.hotkey("esc")  # esc gem mine
        time.sleep(2)
        LoopFindImage(
            DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\exitAdd.png",
            "\n ad closed ",
        )  # if gem mine empty closes the quit window so doesnt quit
        time.sleep(1)

        # MARKET - check for shards
        if pyautogui.locateOnScreen(
            DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\theMarket.png",
            confidence=0.8,
        ):
            theMarketx, theMarkety = pyautogui.locateCenterOnScreen(
                DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\theMarket.png",
                confidence=0.8,
            )
            pyautogui.click(theMarketx, theMarkety)
            with open("log.txt", mode="a") as file:
                file.write("\n shop clicked")
            time.sleep(2)
            while (
                pyautogui.locateOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\shopShard.png",
                    confidence=0.8,
                )
                != None
            ):
                shopShardx, shopShardy = pyautogui.locateCenterOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\shopShard.png",
                    confidence=0.8,
                )
                pyautogui.click(shopShardx, shopShardy)
                time.sleep(2)
                while (
                    pyautogui.locateOnScreen(
                        DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\getShard.png",
                        confidence=0.8,
                    )
                    != None
                ):
                    getShardx, getShardy = pyautogui.locateCenterOnScreen(
                        DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\getShard.png",
                        confidence=0.8,
                    )
                    pyautogui.click(getShardx, getShardy)
                    continue
                with open("log.txt", mode="a") as file:
                    file.write("\n shard bought")
                time.sleep(2)
            while (
                pyautogui.locateOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\marketAS.png",
                    confidence=0.8,
                )
                != None
            ):
                marketASx, marketASy = pyautogui.locateCenterOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\marketAS.png",
                    confidence=0.8,
                )
                pyautogui.click(marketASx, marketASy)
                time.sleep(2)
                while (
                    pyautogui.locateOnScreen(
                        DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\getAS.png",
                        confidence=0.8,
                    )
                    != None
                ):
                    getASx, getASy = pyautogui.locateCenterOnScreen(
                        DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\getAS.png",
                        confidence=0.8,
                    )
                    pyautogui.click(getASx, getASy)
                    continue
                with open("log.txt", mode="a") as file:
                    file.write("\n shard bought")
                time.sleep(2)
            LoopFindImage(
                DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\goBack.png",
                "\n back to Bastion x ",
            )
            LoopFindImage(
                DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\exitAdd.png",
                "\n ad closed ",
            )

        # SHOP - claim AS, claim MS, check offers for goodieBag,miniPack,smallPack,regularPack, then claim
        if pyautogui.locateOnScreen(
            DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\shopBTN.png",
            confidence=0.8,
        ):
            shopBTNx, shopBTNy = pyautogui.locateCenterOnScreen(
                DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\shopBTN.png",
                confidence=0.8,
            )
            pyautogui.click(shopBTNx, shopBTNy)
            with open("log.txt", mode="a") as file:
                file.write("\n opening shop")
            time.sleep(2)
            while (
                pyautogui.locateOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\claimAS.png",
                    confidence=0.8,
                )
                != None
            ):
                claimASx, claimASy = pyautogui.locateCenterOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\claimAS.png",
                    confidence=0.8,
                )
                pyautogui.click(claimASx, claimASy)
                with open("log.txt", mode="a") as file:
                    file.write("\n claiming Ancient Shard")
                time.sleep(2)
                while (
                    pyautogui.locateOnScreen(
                        DIR
                        + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\defaultClaim.png",
                        confidence=0.8,
                    )
                    != None
                ):
                    defaultClaimx, defaultClaimy = pyautogui.locateCenterOnScreen(
                        DIR
                        + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\defaultClaim.png",
                        confidence=0.8,
                    )
                    pyautogui.click(defaultClaimx, defaultClaimy)
                    with open("log.txt", mode="a") as file:
                        file.write("\n claimed")
                    time.sleep(3)
            while (
                pyautogui.locateOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\claimMS.png",
                    confidence=0.8,
                )
                != None
            ):
                claimMSx, claimMSy = pyautogui.locateCenterOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\claimMS.png",
                    confidence=0.8,
                )
                pyautogui.click(claimMSx, claimMSy)
                with open("log.txt", mode="a") as file:
                    file.write("\n claiming mystery Shard")
                time.sleep(3)
                while (
                    pyautogui.locateOnScreen(
                        DIR
                        + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\defaultClaim.png",
                        confidence=0.8,
                    )
                    != None
                ):
                    defaultClaimx, defaultClaimy = pyautogui.locateCenterOnScreen(
                        DIR
                        + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\defaultClaim.png",
                        confidence=0.8,
                    )
                    pyautogui.click(defaultClaimx, defaultClaimy)
                    with open("log.txt", mode="a") as file:
                        file.write("\n claimed")
                    time.sleep(3)
            while (
                pyautogui.locateOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\offers.png",
                    confidence=0.9,
                )
                != None
            ):
                offersx, offersy = pyautogui.locateCenterOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\offers.png",
                    confidence=0.8,
                )
                pyautogui.click(offersx, offersy)
                time.sleep(3)
                if pyautogui.locateOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\goodieBag.png",
                    confidence=0.8,
                ):
                    goodieBagx, goodieBagy = pyautogui.locateCenterOnScreen(
                        DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\goodieBag.png",
                        confidence=0.8,
                    )
                    pyautogui.click(goodieBagx, goodieBagy)
                    time.sleep(1)
                if pyautogui.locateOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\miniPack.png",
                    confidence=0.8,
                ):
                    goodieBagx, goodieBagy = pyautogui.locateCenterOnScreen(
                        DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\miniPack.png",
                        confidence=0.8,
                    )
                    pyautogui.click(goodieBagx, goodieBagy)
                    time.sleep(1)
                if pyautogui.locateOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\smallPack.png",
                    confidence=0.8,
                ):
                    smallPackx, smallPacky = pyautogui.locateCenterOnScreen(
                        DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\smallPack.png",
                        confidence=0.8,
                    )
                    pyautogui.click(smallPackx, smallPacky)
                    time.sleep(1)
                LoopFindImage(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\regularPack.png",
                    "\n regualr pack claimed ",
                )
                pyautogui.click(724, 333)
                LoopFindImage(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\claimFreeGift.png",
                    "\n claiming free gift ",
                )
                time.sleep(1)
                pyautogui.click(793, 333)
                LoopFindImage(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\claimFreeGift.png",
                    "\n claiming free gift ",
                )
                time.sleep(1.5)
                pyautogui.click(860, 333)
                LoopFindImage(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\claimFreeGift.png",
                    "\n claiming free gift ",
                )
                time.sleep(1.5)
                pyautogui.click(928, 333)
                LoopFindImage(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\claimFreeGift.png",
                    "\n claiming free gift ",
                )
                time.sleep(1.5)
                pyautogui.click(998, 333)
                LoopFindImage(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\claimFreeGift.png",
                    "\n claiming free gift ",
                )
                time.sleep(1.5)
                pyautogui.click(1072, 333)
                LoopFindImage(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\claimFreeGift.png",
                    "\n claiming free gift ",
                )
                time.sleep(1.5)
                pyautogui.click(1138, 333)
                LoopFindImage(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\claimFreeGift.png",
                    "\n claiming free gift ",
                )
                time.sleep(1.5)
                pyautogui.click(1207, 333)
                LoopFindImage(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\claimFreeGift.png",
                    "\n claiming free gift ",
                )
                time.sleep(1.5)
                pyautogui.click(1278, 333)
                LoopFindImage(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\claimFreeGift.png",
                    "\n claiming free gift ",
                )
                time.sleep(1.5)
                pyautogui.click(1351, 333)
                LoopFindImage(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\claimFreeGift.png",
                    "\n regualr pack claimed ",
                )
                time.sleep(1.5)
                # keep adding offers
                while (
                    pyautogui.locateOnScreen(
                        DIR
                        + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\claimFreeGift.png",
                        confidence=0.8,
                    )
                    != None
                ):
                    miniPackx, miniPacky = pyautogui.locateCenterOnScreen(
                        DIR
                        + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\claimFreeGift.png",
                        confidence=0.8,
                    )
                    pyautogui.click(miniPackx, miniPacky)
                    time.sleep(1)
            while (
                pyautogui.locateOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\goBack.png",
                    confidence=0.8,
                )
                != None
            ):
                goBackx, goBacky = pyautogui.locateCenterOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\goBack.png",
                    confidence=0.8,
                )
                pyautogui.click(goBackx, goBacky)
                with open("log.txt", mode="a") as file:
                    file.write("\n Back to bastion")
                time.sleep(1)
            LoopFindImage(
                DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\exitAdd.png",
                "\n ad closed ",
            )

        # GUARDIAN RING - Upgrade cgampions
        if pyautogui.locateOnScreen(
            DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\guardianRing.png",
            confidence=0.8,
        ):
            guardianRingx, guardianRingy = pyautogui.locateCenterOnScreen(
                DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\guardianRing.png",
                confidence=0.8,
            )
            pyautogui.click(guardianRingx, guardianRingy)
            with open("log.txt", mode="a") as file:
                file.write("\n open guardian ring")
            time.sleep(2)
            while (
                pyautogui.locateOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\GRupgrade.png",
                    confidence=0.8,
                )
                != None
            ):
                GRupgradex, GRupgradey = pyautogui.locateCenterOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\GRupgrade.png",
                    confidence=0.8,
                )
                pyautogui.click(GRupgradex, GRupgradey)
                with open("log.txt", mode="a") as file:
                    file.write("\n upgrading champions")
                time.sleep(2)
            while (
                pyautogui.locateOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\goBack.png",
                    confidence=0.8,
                )
                != None
            ):
                goBackx, goBacky = pyautogui.locateCenterOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\goBack.png",
                    confidence=0.8,
                )
                pyautogui.click(goBackx, goBacky)
                with open("log.txt", mode="a") as file:
                    file.write("\n Back to bastion")
                time.sleep(2)
            LoopFindImage(
                DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\exitAdd.png",
                "\n ad closed ",
            )

        # TIME REWARDS
        if pyautogui.locateOnScreen(
            DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\timeRewards.png",
            confidence=0.8,
        ):
            timeRewardsx, timeRewardsy = pyautogui.locateCenterOnScreen(
                DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\timeRewards.png",
                confidence=0.8,
            )
            pyautogui.click(timeRewardsx, timeRewardsy)
            with open("log.txt", mode="a") as file:
                file.write("\n claiming timed rewards")
            time.sleep(2)
            while (
                pyautogui.locateOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\5min.png",
                    confidence=0.8,
                )
                != None
            ):
                fiveminx, fiveminy = pyautogui.locateCenterOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\5min.png",
                    confidence=0.8,
                )
                pyautogui.click(fiveminx, fiveminy)
                time.sleep(1)
            while (
                pyautogui.locateOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\20min.png",
                    confidence=0.8,
                )
                != None
            ):
                twentyminx, twentyminy = pyautogui.locateCenterOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\20min.png",
                    confidence=0.8,
                )
                pyautogui.click(twentyminx, twentyminy)
                time.sleep(1)
            while (
                pyautogui.locateOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\40min.png",
                    confidence=0.8,
                )
                != None
            ):
                fortyminx, fortyminy = pyautogui.locateCenterOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\40min.png",
                    confidence=0.8,
                )
                pyautogui.click(fortyminx, fortyminy)
                time.sleep(1)
            while (
                pyautogui.locateOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\60min.png",
                    confidence=0.8,
                )
                != None
            ):
                sixtyminx, sixtyminy = pyautogui.locateCenterOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\60min.png",
                    confidence=0.8,
                )
                pyautogui.click(sixtyminx, sixtyminy)
                time.sleep(1)
            while (
                pyautogui.locateOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\90min.png",
                    confidence=0.8,
                )
                != None
            ):
                ninetyminx, ninetyminy = pyautogui.locateCenterOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\90min.png",
                    confidence=0.8,
                )
                pyautogui.click(ninetyminx, ninetyminy)
                time.sleep(1)
            while (
                pyautogui.locateOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\180min.png",
                    confidence=0.8,
                )
                != None
            ):
                lastminx, lastminy = pyautogui.locateCenterOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\180min.png",
                    confidence=0.8,
                )
                pyautogui.click(lastminx, lastminy)
                time.sleep(1)
            while (
                pyautogui.locateOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\exitAdd.png",
                    confidence=0.8,
                )
                != None
            ):
                adx, ady = pyautogui.locateCenterOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\exitAdd.png",
                    confidence=0.8,
                )
                pyautogui.click(adx, ady)
                with open("log.txt", mode="a") as file:
                    file.write("\n ad closed")
                time.sleep(3)

        # CLAN - check in and claim rewards
        if pyautogui.locateOnScreen(
            DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\clanBTN.png",
            confidence=0.8,
        ):
            clanBTNx, clanBTNy = pyautogui.locateCenterOnScreen(
                DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\clanBTN.png",
                confidence=0.8,
            )
            pyautogui.click(clanBTNx, clanBTNy)
            with open("log.txt", mode="a") as file:
                file.write("\n opening clan button")
            time.sleep(1)
            while (
                pyautogui.locateOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\clanMembers.png",
                    confidence=0.8,
                )
                != None
            ):
                clanMembersx, clanMembersy = pyautogui.locateCenterOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\clanMembers.png",
                    confidence=0.8,
                )
                pyautogui.click(clanMembersx, clanMembersy)
                time.sleep(1)
            while (
                pyautogui.locateOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\clanCheckIn.png",
                    confidence=0.8,
                )
                != None
            ):
                clanCheckInx, clanCheckIny = pyautogui.locateCenterOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\clanCheckIn.png",
                    confidence=0.8,
                )
                pyautogui.click(clanCheckInx, clanCheckIny)
                time.sleep(1)
            if pyautogui.locateOnScreen(
                DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\clanTreasure.png",
                confidence=0.8,
            ):
                clanTreasurex, clanTreasurey = pyautogui.locateCenterOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\clanTreasure.png",
                    confidence=0.8,
                )
                pyautogui.click(clanTreasurex, clanTreasurey)
                time.sleep(1)
            while (
                pyautogui.locateOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\goBack.png",
                    confidence=0.8,
                )
                != None
            ):
                goBackx, goBacky = pyautogui.locateCenterOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\goBack.png",
                    confidence=0.8,
                )
                pyautogui.click(goBackx, goBacky)
                with open("log.txt", mode="a") as file:
                    file.write("\n Back to bastion")
                time.sleep(3)

        # QUESTS - Check for completed daily and advanced quests and claim
        if pyautogui.locateOnScreen(
            DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\quests.png",
            confidence=0.8,
        ):
            questsx, questsy = pyautogui.locateCenterOnScreen(
                DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\quests.png",
                confidence=0.8,
            )
            pyautogui.click(questsx, questsy)
            with open("log.txt", mode="a") as file:
                file.write("\n opening quests button")
            time.sleep(2)
            while (
                pyautogui.locateOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\questClaim.png",
                    confidence=0.8,
                )
                != None
            ):
                questClaimx, questClaimy = pyautogui.locateCenterOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\questClaim.png",
                    confidence=0.8,
                )
                pyautogui.click(questClaimx, questClaimy)
                time.sleep(1)
            if pyautogui.locateOnScreen(
                DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\advancedQuests.png",
                confidence=0.8,
            ):
                advancedQuestsx, advancedQuestsy = pyautogui.locateCenterOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\advancedQuests.png",
                    confidence=0.8,
                )
                pyautogui.click(advancedQuestsx, advancedQuestsy)
                time.sleep(1)
            while (
                pyautogui.locateOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\questClaim.png",
                    confidence=0.8,
                )
                != None
            ):
                questClaimx, questClaimy = pyautogui.locateCenterOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\questClaim.png",
                    confidence=0.8,
                )
                pyautogui.click(questClaimx, questClaimy)
                time.sleep(1)
            while (
                pyautogui.locateOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\goBack.png",
                    confidence=0.8,
                )
                != None
            ):
                goBackx, goBacky = pyautogui.locateCenterOnScreen(
                    DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\goBack.png",
                    confidence=0.8,
                )
                pyautogui.click(goBackx, goBacky)
                with open("log.txt", mode="a") as file:
                    file.write("\n Back to bastion")
                time.sleep(1)
    else:
        pass
    ###################################
    # inbox collect
    time.sleep(1)
    pyautogui.hotkey("i")
    while (
        pyautogui.locateOnScreen(
            DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\inbox_brew.png",
            confidence=0.8,
        )
        != None
    ):
        brew = pyautogui.locateOnScreen(
            DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\inbox_brew.png",
            confidence=0.8,
        )

        pyautogui.moveTo(brew)
        pyautogui.moveRel(250, 0)
        pyautogui.click()
        time.sleep(2)
    while (
        pyautogui.locateOnScreen(
            DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\inbox_purple_forge.png",
            confidence=0.8,
        )
        != None
    ):
        forgepurple = pyautogui.locateOnScreen(
            DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\inbox_purple_forge.png",
            confidence=0.8,
        )

        pyautogui.moveTo(forgepurple)
        pyautogui.moveRel(250, 0)
        pyautogui.click()
        time.sleep(2)
    while (
        pyautogui.locateOnScreen(
            DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\inbox_yellow_forge.png",
            confidence=0.8,
        )
        != None
    ):
        forgeyellow = pyautogui.locateOnScreen(
            DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\inbox_yellow_forge.png",
            confidence=0.8,
        )

        pyautogui.moveTo(forgeyellow)
        pyautogui.moveRel(250, 0)
        pyautogui.click()
        time.sleep(2)
    while (
        pyautogui.locateOnScreen(
            DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\inbox_coin.png",
            confidence=0.8,
        )
        != None
    ):
        inboxcoin = pyautogui.locateOnScreen(
            DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\inbox_coin.png",
            confidence=0.8,
        )

        pyautogui.moveTo(inboxcoin)
        pyautogui.moveRel(250, 0)
        pyautogui.click()
        time.sleep(2)
    while (
        pyautogui.locateOnScreen(
            DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\inbox_potion.png",
            confidence=0.8,
        )
        != None
    ):
        potion = pyautogui.locateOnScreen(
            DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\inbox_potion.png",
            confidence=0.8,
        )

        pyautogui.moveTo(potion)
        pyautogui.moveRel(250, 0)
        pyautogui.click()
        time.sleep(2)
    while (
        pyautogui.locateOnScreen(
            DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\goBack.png",
            confidence=0.8,
        )
        != None
    ):
        goBackx, goBacky = pyautogui.locateCenterOnScreen(
            DIR + "\\AutoRaidAutomate\\PyAutoRaid\\assets\\goBack.png",
            confidence=0.8,
        )
        pyautogui.click(goBackx, goBacky)
        with open("log.txt", mode="a") as file:
            file.write("\n Back to bastion")
        time.sleep(1)


if __name__ == "__main__":
    AutoRewards()
