# Fight 10 classic arena battles
import sqlite3
import pyautogui
import time
from Modules.LoopFindImage import LoopFindImage
import pathlib
# from Modules.SQL_test import SQL
import sqlite3 as sql
import os
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


def ClassicArena():
    cursor.execute("SELECT * FROM PyAutoRaid")
    results = cursor.fetchall()
    connection.commit()
    Run = results
    Run = Run[0][3]
    if Run == "True":
        Log_start("ClassicArena")
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
            pyautogui.locateOnScreen(
                ASSETS_PATH + "\\arenaTab.png",
                confidence=0.8,
            )
            != None
        ):
            battlex, battley = pyautogui.locateCenterOnScreen(
                ASSETS_PATH + "\\arenaTab.png",
                confidence=0.9,
            )
            pyautogui.click(battlex, battley)
            with open("log.txt", mode="a") as file:
                file.write("\n arena tab clicked")
            time.sleep(2)
        while (
            pyautogui.locateOnScreen(
                ASSETS_PATH + "\\classicArena.png",
                confidence=0.8,
            )
            != None
        ):
            battlex, battley = pyautogui.locateCenterOnScreen(
                ASSETS_PATH + "\\classicArena.png",
                confidence=0.9,
            )
            pyautogui.click(battlex, battley)

            time.sleep(2)
        ######################################################Need to not make this forever loop happen
        done = 0
        battles = 0
        for i in range(0, 2):
            # Top battle
            if (
                pyautogui.locateOnScreen(
                    ASSETS_PATH + "\\arenaBattle.png",
                    region=(1215, 423, 167, 58),
                    confidence=0.8,
                )
                != None
            ):
                pyautogui.click(1304, 457)
                time.sleep(2)
                while (
                    pyautogui.locateOnScreen(
                        ASSETS_PATH + "\\arenaConfirm.png",
                        confidence=0.8,
                    )
                    != None
                ):
                    battlex, battley = pyautogui.locateCenterOnScreen(
                        ASSETS_PATH + "\\arenaConfirm.png",
                        confidence=0.9,
                    )
                    pyautogui.click(battlex, battley)
                    print("confirm tokens")
                    time.sleep(4)
                    pyautogui.click(1304, 457)
                if (
                    pyautogui.locateOnScreen(
                        ASSETS_PATH + "\\classicArenaRefill.png",
                        confidence=0.8,
                    )
                    != None
                ):
                    battlex, battley = pyautogui.locateCenterOnScreen(
                        ASSETS_PATH + "\\classicArenaRefill.png",
                        confidence=0.9,
                    )
                    break
                time.sleep(2)
                LoopFindImage(
                    ASSETS_PATH + "\\arenaStart.png",
                    "\n arena battle started",
                )
                print("First Battle")
                while (
                    pyautogui.locateOnScreen(
                        ASSETS_PATH + "\\tapToContinue.png",
                        confidence=0.8,
                    )
                    == None
                ):
                    if done == 1:
                        break
                    print("First time looking for continue")
                    time.sleep(1)
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
                        print("finishing arena battle")
                        time.sleep(1)
                        pyautogui.click(goBackx, goBacky)
                        print("breaking first battle")
                        done = 1
                        battles += 1
                        continue
            time.sleep(1)
            pyautogui.doubleClick(969, 788, interval=1)
            # Second battle
            if (
                pyautogui.locateOnScreen(
                    ASSETS_PATH + "\\arenaBattle.png",
                    region=(1212, 508, 170, 59),
                    confidence=0.8,
                )
                != None
            ):
                pyautogui.click(1304, 540)
                time.sleep(4)
                while (
                    pyautogui.locateOnScreen(
                        ASSETS_PATH + "\\arenaConfirm.png",
                        confidence=0.8,
                    )
                    != None
                ):
                    battlex, battley = pyautogui.locateCenterOnScreen(
                        ASSETS_PATH + "\\arenaConfirm.png",
                        confidence=0.9,
                    )
                    pyautogui.click(battlex, battley)
                    print("confirm tokens")
                    time.sleep(2)
                    pyautogui.click(1304, 540)
                if (
                    pyautogui.locateOnScreen(
                        ASSETS_PATH + "\\classicArenaRefill.png",
                        confidence=0.8,
                    )
                    != None
                ):
                    battlex, battley = pyautogui.locateCenterOnScreen(
                        ASSETS_PATH + "\\classicArenaRefill.png",
                        confidence=0.9,
                    )
                    break
                time.sleep(2)
                LoopFindImage(
                    ASSETS_PATH + "\\arenaStart.png",
                    "\n arena battle started",
                )
                print("Second Battle")
                while (
                    pyautogui.locateOnScreen(
                        ASSETS_PATH + "\\tapToContinue.png",
                        confidence=0.8,
                    )
                    == None
                ):
                    if done == 2:
                        break
                    print("Second time looking for continue")
                    time.sleep(1)
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
                        print("finishing arena battle")
                        time.sleep(1)
                        pyautogui.click(goBackx, goBacky)
                        print("breaking second battle")
                        done = 2
                        battles += 1
                        continue
            time.sleep(1)
            pyautogui.doubleClick(969, 788, interval=1)
            # Third battle
            if (
                pyautogui.locateOnScreen(
                    ASSETS_PATH + "\\arenaBattle.png",
                    region=(1217, 596, 164, 58),
                    confidence=0.8,
                )
                != None
            ):
                pyautogui.click(1303, 625)
                time.sleep(4)
                while (
                    pyautogui.locateOnScreen(
                        ASSETS_PATH + "\\arenaConfirm.png",
                        confidence=0.8,
                    )
                    != None
                ):
                    battlex, battley = pyautogui.locateCenterOnScreen(
                        ASSETS_PATH + "\\arenaConfirm.png",
                        confidence=0.9,
                    )
                    pyautogui.click(battlex, battley)
                    print("confirm tokens")
                    time.sleep(2)
                    pyautogui.click(1303, 625)
                if (
                    pyautogui.locateOnScreen(
                        ASSETS_PATH + "\\classicArenaRefill.png",
                        confidence=0.8,
                    )
                    != None
                ):
                    battlex, battley = pyautogui.locateCenterOnScreen(
                        ASSETS_PATH + "\\classicArenaRefill.png",
                        confidence=0.9,
                    )
                    break
                time.sleep(2)
                LoopFindImage(
                    ASSETS_PATH + "\\arenaStart.png",
                    "\n arena battle started",
                )
                print("Third Battle")
                while (
                    pyautogui.locateOnScreen(
                        ASSETS_PATH + "\\tapToContinue.png",
                        confidence=0.8,
                    )
                    == None
                ):
                    if done == 3:
                        break
                    print("Third time looking for continue")
                    time.sleep(2)
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
                        print("finishing arena battle")
                        time.sleep(1)
                        pyautogui.click(goBackx, goBacky)
                        print("breaking third battle")
                        done = 3
                        battles += 1
                        continue
            time.sleep(1)
            pyautogui.doubleClick(969, 788, interval=1)
            time.sleep(1)
            if (
                pyautogui.locateOnScreen(
                    ASSETS_PATH + "\\arenaBattle.png",
                    region=(1212, 679, 170, 62),
                    confidence=0.9,
                )
                != None
            ):
                # Fourth battle
                pyautogui.click(1304, 711)
                time.sleep(2)
                while (
                    pyautogui.locateOnScreen(
                        ASSETS_PATH + "\\arenaConfirm.png",
                        confidence=0.8,
                    )
                    != None
                ):
                    battlex, battley = pyautogui.locateCenterOnScreen(
                        ASSETS_PATH + "\\arenaConfirm.png",
                        confidence=0.9,
                    )
                    pyautogui.click(battlex, battley)
                    print("confirm tokens")
                    time.sleep(4)
                    pyautogui.click(1304, 711)
                if (
                    pyautogui.locateOnScreen(
                        ASSETS_PATH + "\\classicArenaRefill.png",
                        confidence=0.8,
                    )
                    != None
                ):
                    battlex, battley = pyautogui.locateCenterOnScreen(
                        ASSETS_PATH + "\\classicArenaRefill.png",
                        confidence=0.9,
                    )
                    break
                time.sleep(2)
                LoopFindImage(
                    ASSETS_PATH + "\\arenaStart.png",
                    "\n arena battle started",
                )
                print("Fourth Battle")
                while (
                    pyautogui.locateOnScreen(
                        ASSETS_PATH + "\\tapToContinue.png",
                        confidence=0.8,
                    )
                    == None
                ):
                    if done == 4:
                        break
                    print("Fourth time looking for continue")
                    time.sleep(1)
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
                        print("finishing arena battle")
                        time.sleep(1)
                        pyautogui.click(goBackx, goBacky)
                        print("breaking fourth battle")
                        done = 4
                        battles += 1
                        continue
            time.sleep(1)
            pyautogui.doubleClick(969, 788, interval=1)
            time.sleep(1)
            if (
                pyautogui.locateOnScreen(
                    ASSETS_PATH + "\\arenaBattle.png",
                    region=(1208, 761, 177, 68),
                    confidence=0.8,
                )
                != None
            ):
                # Fifth battle
                pyautogui.click(1304, 798)
                time.sleep(1)
                while (
                    pyautogui.locateOnScreen(
                        ASSETS_PATH + "\\arenaConfirm.png",
                        confidence=0.8,
                    )
                    != None
                ):
                    battlex, battley = pyautogui.locateCenterOnScreen(
                        ASSETS_PATH + "\\arenaConfirm.png",
                        confidence=0.9,
                    )
                    pyautogui.click(battlex, battley)
                    print("confirm tokens")
                    time.sleep(4)
                    pyautogui.click(1304, 798)
                if (
                    pyautogui.locateOnScreen(
                        ASSETS_PATH + "\\classicArenaRefill.png",
                        confidence=0.8,
                    )
                    != None
                ):
                    battlex, battley = pyautogui.locateCenterOnScreen(
                        ASSETS_PATH + "\\classicArenaRefill.png",
                        confidence=0.9,
                    )
                    break
                time.sleep(2)
                LoopFindImage(
                    ASSETS_PATH + "\\arenaStart.png",
                    "\n arena battle started",
                )
                print("Fifth Battle")
                while (
                    pyautogui.locateOnScreen(
                        ASSETS_PATH + "\\tapToContinue.png",
                        confidence=0.8,
                    )
                    == None
                ):
                    if done == 5:
                        break
                    print("fifth time looking for continue")
                    time.sleep(1)
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
                        print("finishing arena battle")
                        time.sleep(1)
                        pyautogui.click(goBackx, goBacky)
                        print("breaking fifth battle")
                        done = 5
                        battles += 1
                        continue
            time.sleep(1)
            pyautogui.doubleClick(969, 788, interval=1)

            while (
                pyautogui.locateOnScreen(
                    ASSETS_PATH + "\\arenaRefresh.png",
                    confidence=0.8,
                )
                != None
            ):
                goBackx, goBacky = pyautogui.locateCenterOnScreen(
                    ASSETS_PATH + "\\arenaRefresh.png",
                    confidence=0.8,
                )
                pyautogui.click(goBackx, goBacky)
                print("arena refreshed")
                time.sleep(1)
                done = 6
        print(battles, "Arena Battles Completed")
        # Out of the loop back out now
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
            time.sleep(2)
        Log_finish(f"Classic Arena, {battles} Battles Fought ")
        Log_info()
        return f"{battles} Fought in Classic Arena"


if __name__ == "__main__":
    try:
        ClassicArena()
        time.sleep(2)
    except TypeError:
        print(TypeError)
        quit()
