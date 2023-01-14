# fight the CB, this one is NM
import sqlite3
import pyautogui
import time
from datetime import datetime
from Modules.AutoRewards import AutoRewards
from Modules.BlackOutMonitor import BlackOutMonitor
from Modules.quitAll import quitAll
from Modules.OpenRaid import openRaid
import os
import sys
from Modules.TimeBetween import is_time_between
import pathlib
import sqlite3 as sql

DIR = os.getcwd()
DB_PATH = os.path.join(DIR, "Data", "Settings.db")

ASSETS_PATH = os.path.join(DIR, "assets")
connection = sql.connect(DB_PATH)
cursor = connection.cursor()
# between 4am to 10pm
if is_time_between() == False:
    # NM
    xCB = 1080
    yCB = 724
# between 10pm to 4am
if is_time_between() == True:
    # Brutal
    xCB = 1080
    yCB = 647


def ClanBoss(xCB, yCB):
    cursor.execute("SELECT * FROM PyAutoRaid")
    results = cursor.fetchall()
    connection.commit()
    Run = results
    Run = Run[0][2]
    if Run == "True":
        time.sleep(1.5)
        with open("log.txt", mode="a") as file:
            file.write("\n deleting ads now")
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
            with open("log.txt", mode="a") as file:
                file.write("\n ad closed")
            time.sleep(2)
        while (
            pyautogui.locateOnScreen(
                ASSETS_PATH + "\\battleBTN.png",
                confidence=0.8,
            )
            != None
        ):
            battlex, battley = pyautogui.locateCenterOnScreen(
                ASSETS_PATH + "\\battleBTN.png",
                confidence=0.9,
            )
            pyautogui.click(battlex, battley)
            with open("log.txt", mode="a") as file:
                file.write("\n battle button pressed")
            time.sleep(2)
        while (
            pyautogui.locateOnScreen(ASSETS_PATH + "\\CB.png", confidence=0.9) != None
        ):
            CBx, CBy = pyautogui.locateCenterOnScreen(
                ASSETS_PATH + "\\CB.png", confidence=0.9
            )
            pyautogui.click(CBx, CBy)
            with open("log.txt", mode="a") as file:
                file.write("\n cb tab clicked")
            time.sleep(3)
        while (
            pyautogui.locateOnScreen(ASSETS_PATH + "\\CB2.png", confidence=0.9) != None
        ):
            CB2x, CB2y = pyautogui.locateCenterOnScreen(
                ASSETS_PATH + "\\CB2.png", confidence=0.9
            )
            pyautogui.click(CB2x, CB2y)
            with open("log.txt", mode="a") as file:
                file.write("\n cb tab clicked")
            time.sleep(3)
        while (
            pyautogui.locateOnScreen(
                ASSETS_PATH + "\\demonLord.png",
                confidence=0.9,
            )
            != None
        ):
            demonLordx, demonLordy = pyautogui.locateCenterOnScreen(
                ASSETS_PATH + "\\demonLord.png",
                confidence=0.8,
            )
            pyautogui.click(demonLordx, demonLordy)
            with open("log.txt", mode="a") as file:
                file.write("\n demonlord clicked")
            time.sleep(2)
        while (
            pyautogui.locateOnScreen(
                ASSETS_PATH + "\\demonLord2.png",
                confidence=0.9,
            )
            != None
        ):
            demonLord2x, demonLord2y = pyautogui.locateCenterOnScreen(
                ASSETS_PATH + "\\demonLord2.png",
                confidence=0.8,
            )
            pyautogui.click(demonLord2x, demonLord2y)
            with open("log.txt", mode="a") as file:
                file.write("\n demonlord clicked")
            time.sleep(4)
        while (
            pyautogui.locateOnScreen(
                ASSETS_PATH + "\\CBreward.png",
                confidence=0.8,
            )
            != None
        ):
            CBrewardx, CBrewardy = pyautogui.locateCenterOnScreen(
                ASSETS_PATH + "\\CBreward.png",
                confidence=0.8,
            )
            time.sleep(2)
            pyautogui.click(CBrewardx, CBrewardy)
            with open("log.txt", mode="a") as file:
                file.write("\n rewards checked")
            time.sleep(2)
            while (
                pyautogui.locateOnScreen(
                    ASSETS_PATH + "\\nightmareClaimed.png",
                    confidence=0.8,
                )
                != None
            ):
                nightmareClaimedx, nightmareClaimedy = pyautogui.locateCenterOnScreen(
                    ASSETS_PATH + "\\CBclaim.png",
                    confidence=0.5,
                )
                pyautogui.click(nightmareClaimedx, nightmareClaimedy)
                time.sleep(1)
                pyautogui.click()
                with open("log.txt", mode="a") as file:
                    file.write("\n claim rewards checked")
                # the second click needs to recognize the continue
                time.sleep(1)
                pyautogui.click()
        while (
            pyautogui.locateOnScreen(
                ASSETS_PATH + "\\CBclaim.png",
                confidence=0.8,
            )
            != None
        ):
            CBclaimx, CBclaimy = pyautogui.locateCenterOnScreen(
                ASSETS_PATH + "\\CBclaim.png",
                confidence=0.5,
            )
            pyautogui.click(CBclaimx, CBclaimy)
            time.sleep(1)
            pyautogui.click()
            with open("log.txt", mode="a") as file:
                file.write("\n claim rewards checked")
        time.sleep(2)
        while (
            pyautogui.locateOnScreen(
                ASSETS_PATH + "\\CBhard.png",
                confidence=0.8,
            )
            != None
        ):
            pyautogui.click(xCB, yCB)
            with open("log.txt", mode="a") as file:
                file.write("\n clicked random location, nightmare")
            while (
                pyautogui.locateOnScreen(
                    ASSETS_PATH + "\\CBbattle.png",
                    confidence=0.8,
                )
                != None
            ):
                CBbattlex, CBbattley = pyautogui.locateCenterOnScreen(
                    ASSETS_PATH + "\\CBbattle.png",
                    confidence=0.8,
                )
                time.sleep(2)
                pyautogui.click(CBbattlex, CBbattley)
                with open("log.txt", mode="a") as file:
                    file.write("\n about to battle clan boss")
                time.sleep(1)
                if (
                    pyautogui.locateOnScreen(
                        ASSETS_PATH + "\\CBnokey.png",
                        confidence=0.8,
                    )
                    != None
                ):
                    with open("log.txt", mode="a") as file:
                        file.write("\n no keys left")
                    break
            time.sleep(1)
        while (
            pyautogui.locateOnScreen(
                ASSETS_PATH + "\\CBstart.png",
                confidence=0.8,
            )
            != None
        ):
            CBstartx, CBstarty = pyautogui.locateCenterOnScreen(
                ASSETS_PATH + "\\CBstart.png",
                confidence=0.8,
            )
            time.sleep(2)
            pyautogui.click(CBstartx, CBstarty)
            with open("log.txt", mode="a") as file:
                file.write("\n\n battling clan boss")
            now = datetime.now()
            dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
            with open("log.txt", mode="a") as file:
                file.write(dt_string)
            with open("log.txt", mode="a") as file:
                file.write("\n Date and time of CB battle ")
                file.write(dt_string)
            time.sleep(1)
            while (
                pyautogui.locateOnScreen(
                    ASSETS_PATH + "\\CBcontinue.png",
                    confidence=0.8,
                )
                != None
            ):
                CBcontinuex, CBcontinuey = pyautogui.locateCenterOnScreen(
                    ASSETS_PATH + "\\CBcontinue.png",
                    confidence=0.8,
                )
                time.sleep(2)
                pyautogui.click(CBcontinuex, CBcontinuey)
                time.sleep(200)

            while (
                pyautogui.locateOnScreen(
                    ASSETS_PATH + "\\gotoBastion.png",
                    confidence=0.8,
                )
                == None
            ):
                while (
                    pyautogui.locateOnScreen(
                        ASSETS_PATH + "\\CBcrashed.png",
                        confidence=0.8,
                    )
                    != None
                ):
                    quitAll()
                    with open("log.txt", mode="a") as file:
                        file.write("\n RESTARTING DUE TO CRASH")
                    time.sleep(2)
                    with open("log.txt", mode="a") as file:
                        file.write("\n Closing for restart")
                    time.sleep(2)
                    openRaid()
                    AutoRewards()
                    os.system("taskkill /pid RSLHelper.exe")
                    ClanBoss()
                    quitAll()
                    BlackOutMonitor()
                    sys.exit()
                while (
                    pyautogui.locateOnScreen(
                        ASSETS_PATH + "\\CBcrashed2.png",
                        confidence=0.8,
                    )
                    != None
                ):
                    quitAll()
                    with open("log.txt", mode="a") as file:
                        file.write("\n RESTARTING DUE TO CRASH")
                    time.sleep(2)
                    with open("log.txt", mode="a") as file:
                        file.write("\n Closing for restart")
                    time.sleep(2)
                    openRaid()
                    AutoRewards()
                    os.system("taskkill /pid RSLHelper.exe")
                    ClanBoss()
                    quitAll()
                    BlackOutMonitor()
                    sys.exit()
                while (
                    pyautogui.locateOnScreen(
                        ASSETS_PATH + "\\gotoBastion.png",
                        confidence=0.8,
                    )
                    != None
                ):
                    gotoBastionx, gotoBastiony = pyautogui.locateCenterOnScreen(
                        ASSETS_PATH + "\\gotoBastion.png",
                        confidence=0.8,
                    )
                    with open("log.txt", mode="a") as file:
                        file.write("\n finished CB battle")
                    pyautogui.click(gotoBastionx, gotoBastiony)
                    break
        pyautogui.click(566, 790)
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
            with open("log.txt", mode="a") as file:
                file.write("\n ad closed")
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
            with open("log.txt", mode="a") as file:
                file.write("\n Back to bastion")
            time.sleep(1)
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
            with open("log.txt", mode="a") as file:
                file.write("\n ad closed")


if __name__ == "__main__":
    # between 4am to 10pm
    if is_time_between() == False:
        # NM
        ClanBoss(1080, 724)
    # between 10pm to 4am
    if is_time_between() == True:
        # Brutal
        ClanBoss(1080, 647)
