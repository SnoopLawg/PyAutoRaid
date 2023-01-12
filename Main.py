# Run all of the raid functions.

from Modules.CBauto import ClanBoss
from Modules.AutoRewards import AutoRewards
from Modules.BlackOutMonitor import BlackOutMonitor
from Modules.ClassicArena import ClassicArena
from Modules.OpenRaid import openRaid
from Modules.quitAll import quitAll
from Modules.NightmareAttemptText import NightmareAttemptText

from Modules.TagTeamArena import TagTeamArena
from Modules.TimeBetween import is_time_between
import sys
import pyautogui
import multiprocessing
from datetime import datetime
import time
from multiprocessing import Process
import os
from Modules.RAIDGUI import gui
import pathlib
from Modules.CheckFilesExist import Check_files_exist, Check_os

DIR = str(pathlib.Path().absolute())


def main():

    # wake up pc
    pyautogui.click(0, 5)
    Check_files_exist()
    Check_os()
    is_time_between()

    try:
        openRaid()
    except TypeError:
        openRaid()
    except IndexError:
        openRaid()
    try:
        NightmareAttemptText()
    except TypeError:
        NightmareAttemptText()
    AutoRewards()
    try:
        # between 4am to 10pm
        if is_time_between() == False:
            # NM
            ClanBoss(1080, 724)
        # between 10pm to 4am
        if is_time_between() == True:
            # Brutal
            ClanBoss(1080, 647)
    except TypeError:
        # between 4am to 10pm
        if is_time_between() == False:
            # NM
            ClanBoss(1080, 724)
        # between 10pm to 4am
        if is_time_between() == True:
            # Brutal
            ClanBoss(1080, 647)
    try:
        ClassicArena()
    except TypeError:
        pass
    try:
        TagTeamArena()
    except TypeError:
        TagTeamArena()

    quitAll()
    BlackOutMonitor()
    os.system("taskkill /f /im Main.exe")
    os.system("taskkill /f /im python.exe")
    sys.exit()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    p = multiprocessing.Process(target=main, name="main")
    g = multiprocessing.Process(target=gui, name="PyAutoRaidGui")
    p2 = multiprocessing.Process(target=main, name="main")
    g2 = multiprocessing.Process(target=gui, name="PyAutoRaidGui")
    p.start()

    g.start()
    count = 0
    while True:
        if (
            pyautogui.locateOnScreen(DIR + "\\assets\\CBcrashed.png", confidence=0.8)
            != None
        ):
            time.sleep(5)
            if (
                pyautogui.locateOnScreen(
                    DIR + "\\assets\\CBcrashed.png", confidence=0.8
                )
                != None
            ):
                quitAll()
                os.system("taskkill /f /im Main.exe")
                # os.system("taskkill /f /im python.exe")
                p2.start()
                g2.start()
        if (
            pyautogui.locateOnScreen(DIR + "\\assets\\CBcrashed2.png", confidence=0.8)
            != None
        ):
            time.sleep(5)
            if (
                pyautogui.locateOnScreen(
                    DIR + "\\assets\\CBcrashed.png", confidence=0.8
                )
                != None
            ):
                quitAll()
                os.system("taskkill /f /im Main.exe")
                # os.system("taskkill /f /im python.exe")
                p2.start()
                g2.start()
        count += 1
        if count >= 2400:
            # Terminate
            try:
                p.terminate()
                g.terminate()
                p2.terminate()
                g2.terminate()
                # Cleanup
                p.join()
                g.join()
                p2.join()
                g2.join()
            except:
                pass

    # # Wait 20 min for process
    # time.sleep(2400)

    # # Terminate
    # p.terminate()
    # g.terminate()
    # # Cleanup
    # p.join()
    # g.join()
