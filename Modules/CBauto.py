# fight the CB, this one is NM
import sqlite3
import pyautogui
import time
from datetime import datetime
from Modules.AutoRewards import AutoRewards
from Modules.BlackOutMonitor import BlackOutMonitor
from Modules.quitAll import quitAll
from Modules.OpenRaid import openRaid
from Modules.PyAutoRaid_Configure_Settings import PyAutoRaid_Configure_Settings
import os
import sys
from Modules.TimeBetween import is_time_between
import pathlib
import sqlite3 as sql
from Modules.Logger import *

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

CBDIFFICULTYS = ["UltraNightmare", "Nightmare", "Brutal", "Hard", "Normal", "Easy"]


def ClanBoss():
    Log_start("ClanBoss")
    difficulty = ""
    cursor.execute("SELECT * FROM PyAutoRaid")
    results = cursor.fetchall()
    connection.commit()
    Run = results
    Run = Run[0][2]
    if Run == "True":
        donewithbattles = []
        for i in CBDIFFICULTYS:
            #read what user set their desired battles per difficulty setting was
            cursor.execute(f"SELECT {i} FROM PyAutoRaid_DailyCompleted")
            num_dailybattles = cursor.fetchone()[0]
            battlesetting = i + "_set"
            cursor.execute(f"SELECT {battlesetting} FROM PyAutoRaid_DailyCompleted")
            battlesettingvalue = cursor.fetchone()[0]
            if battlesettingvalue == 0:
                Log_info(f"{battlesettingvalue} battles set for {i}")
                donewithbattles.append(i)
                if donewithbattles == CBDIFFICULTYS:
                    #all battles done... default to fight UNM
                    print(donewithbattles, CBDIFFICULTYS)
                    xCB = 1080
                    yCB = 690
                    break
            elif num_dailybattles >= battlesettingvalue:
                #checking to see if desired amt of battles were already completed
                Log_info(f"{num_dailybattles} / {battlesettingvalue} battles have been completed today for {i}. Moving on to next Clan Boss levels")
                donewithbattles.append(i)
                if donewithbattles == CBDIFFICULTYS:
                    #all battles done... default to fight UNM
                    print(donewithbattles, CBDIFFICULTYS)
                    xCB = 1080
                    yCB = 690
                    break
            else:
                if i == "UltraNightmare":
                    diff=i
                    xCB = 1080
                    yCB = 690
                    break
                elif i == "Nightmare":
                    # NM
                    diff=i
                    xCB = 1080
                    yCB = 724
                    break
                elif i == "Brutal":
                    # Brutal
                    diff=i
                    xCB = 1080
                    yCB = 647
                    break
                elif i == "Hard":
                    diff=i
                    print("not able to click Hard cb yet")
                    break
                elif i == "Normal":
                    diff=i
                    print("not able to click Brutal cb yet")
                    break
                elif i == "Easy":
                    diff=i
                    print("not able to click Easy cb yet")
                    break
        cursor.execute("SELECT * FROM PyAutoRaid_DailyCompleted")
        results = cursor.fetchall()
        trimmed_results = results[0][2:-6]
        totaltoday=sum(trimmed_results)
        Log_info(f"{totaltoday} total battles fought today so far")
        time.sleep(1.5)
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
        time.sleep(3)
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
        pyautogui.click(1080, 724)
        pyautogui.drag(0, -200, duration=1)
        Log_info("-Checking for CB rewards")
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
            time.sleep(2)
            while (
                pyautogui.locateOnScreen(
                    ASSETS_PATH + "\\nightmareClaimed.png",
                    confidence=0.8,
                )
                != None
            ):
                (
                    nightmareClaimedx,
                    nightmareClaimedy,
                ) = pyautogui.locateCenterOnScreen(
                    ASSETS_PATH + "\\CBclaim.png",
                    confidence=0.5,
                )
                pyautogui.click(nightmareClaimedx, nightmareClaimedy)
                time.sleep(1)
                pyautogui.click()
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
        pyautogui.click(1080, 724)
        pyautogui.drag(0, +200, duration=1)
        while (
            pyautogui.locateOnScreen(
                ASSETS_PATH + "\\CBhard.png",
                confidence=0.8,
            )
            != None
        ):
            if yCB == 690:
                pyautogui.click(1080, 724)
                pyautogui.drag(0, -200, duration=1)
                pyautogui.click(1080, 690)
            else:
                pyautogui.click(xCB, yCB)

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
                Log_start("CB battle")
                time.sleep(1)
                if (
                    pyautogui.locateOnScreen(
                        ASSETS_PATH + "\\CBnokey.png",
                        confidence=0.8,
                    )
                    != None
                ):
                    Log_info("-No keys currently available")
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
            Log_info(f"-Battling {diff} Clan Boss")
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
                        ASSETS_PATH + "\\gotoBastion.png",
                        confidence=0.8,
                    )
                    != None
                ):
                    gotoBastionx, gotoBastiony = pyautogui.locateCenterOnScreen(
                        ASSETS_PATH + "\\gotoBastion.png",
                        confidence=0.8,
                    )
                    Log_finish("ClanBoss")
                    pyautogui.click(gotoBastionx, gotoBastiony)
                    break
            if yCB == 724:
                difficulty = "Nightmare"
                PyAutoRaid_Configure_Settings("Nightmare")
            elif yCB == 647:
                difficulty = "Brutal"
                PyAutoRaid_Configure_Settings("Brutal")
            elif yCB == 690:
                difficulty = "UltraNightmare"
                PyAutoRaid_Configure_Settings("UltraNightmare")
            elif yCB == 647:
                difficulty = "Hard"
                PyAutoRaid_Configure_Settings("Hard")
            elif yCB == 724:
                difficulty = "Normal"
                PyAutoRaid_Configure_Settings("Normal")
            elif yCB == 647:
                difficulty = "Easy"
                PyAutoRaid_Configure_Settings("Easy")
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
            time.sleep(1.5)
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
            time.sleep(1)
            
    if difficulty == "":
        difficulty = "No"
    Log_finish("ClanBoss")
    Log_info()
    return f"{difficulty} Clan boss fought"


if __name__ == "__main__":
    ClanBoss()
