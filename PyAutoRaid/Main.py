# Run all of the raid functions.

from CBauto import AutoCB
from AutoRewards import AutoRewards
from BlackOutMonitor import BlackOutMonitor
from ClassicArena import ClassicArena
from OpenRaid import openRaid
from quitAll import quitAll
from NightmareAttemptText import NightmareAttemptText
from CheckFilesExist import CheckFilesExist, CheckOS
from TagTeamArena import TagTeamArena
from TimeBetween import is_time_between
import sys
import pyautogui
import multiprocessing
from datetime import datetime
import time
from multiprocessing import Process
import os
from RAIDGUI import gui
import pathlib

DIR = str(pathlib.Path().absolute())


def main():

    # wake up pc
    pyautogui.click(0, 5)
    # CheckFilesExist()
    CheckOS()
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
            AutoCB(1080, 724)
        # between 10pm to 4am
        if is_time_between() == True:
            # Brutal
            AutoCB(1080, 647)
    except TypeError:
        # between 4am to 10pm
        if is_time_between() == False:
            # NM
            AutoCB(1080, 724)
        # between 10pm to 4am
        if is_time_between() == True:
            # Brutal
            AutoCB(1080, 647)
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

    p.start()

    g.start()
    count = 0
    while True:
        if (
            pyautogui.locateOnScreen(
                DIR + "\\PyAutoRaid\\assets\\CBcrashed.png", confidence=0.8
            )
            != None
        ):
            time.sleep(5)
            if (
                pyautogui.locateOnScreen(
                    DIR + "\\PyAutoRaid\\assets\\CBcrashed.png", confidence=0.8
                )
                != None
            ):
                quitAll()
                os.system("taskkill /f /im Main.exe")
                # os.system("taskkill /f /im python.exe")
                p.start()
                g.start()
        if (
            pyautogui.locateOnScreen(
                DIR + "\\PyAutoRaid\\assets\\CBcrashed2.png", confidence=0.8
            )
            != None
        ):
            time.sleep(5)
            if (
                pyautogui.locateOnScreen(
                    DIR + "\\PyAutoRaid\\assets\\CBcrashed.png", confidence=0.8
                )
                != None
            ):
                quitAll()
                os.system("taskkill /f /im Main.exe")
                # os.system("taskkill /f /im python.exe")
                p.start()
                g.start()
        count += 1
        if count >= 2400:
            # Terminate
            p.terminate()
            g.terminate()
            # Cleanup
            p.join()
            g.join()

    # # Wait 20 min for process
    # time.sleep(2400)

    # # Terminate
    # p.terminate()
    # g.terminate()
    # # Cleanup
    # p.join()
    # g.join()
