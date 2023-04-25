# open Raid
import operator
from posixpath import expanduser
import time
import os, sys, subprocess
import pygetwindow
from Modules.quitAll import quitAll
from Modules.CheckFilesExist import *
import pyautogui
import pathlib
from screeninfo import Monitor, get_monitors

# import Main

import sys

if getattr(sys, "frozen", False):
    # we are running in a bundle
    DIR = sys._MEIPASS
else:
    # we are running in a normal Python environment
    DIR = os.getcwd()
ASSETS_PATH = os.path.join(DIR, "assets")
import os


def get_screen():
    for m in get_monitors():
        width = m.width
        height = m.height
        main = m.is_primary
        if main == True:
            center_width = int((width / 2) - 450)
            center_height = int((height / 2) - 300)
            return (center_width, center_height)


def openRaid():
    quitAll()
    time.sleep(5)
    operating = Check_os()
    if operating == "Darwin":
        PATH = "/Applications/Plarium Play.app"
        FULL_PATH = os.path.expanduser(PATH)
        subprocess.call(["open", FULL_PATH])
        time.sleep(30)
        # TODO: Fix the clicks to open raid
    elif operating == "Windows":
        all_windows = pygetwindow.getAllTitles()
        subprocess.Popen(
            [
                os.path.join(os.getenv("LOCALAPPDATA"), "PlariumPlay\PlariumPlay.exe"),
                "--args",
                "-gameid=101",
                "-tray-start",
            ]
        )
        time.sleep(30)
        time_out = 0
        while (
            pyautogui.locateOnScreen(
                ASSETS_PATH + "\\exitAdd.png",
                confidence=0.8,
            )
            == None
        ):
            time_out += 1
            time.sleep(0.5)

            if time_out >= 100:
                print("raid never opened lol")
                quitAll()
                pyautogui.hotkey("winleft", "m")
                pyautogui.doubleClick(440, 362)
            while "Raid: Shadow Legends" not in all_windows:
                all_windows = pygetwindow.getAllTitles()
                print("Waiting for Raid to open")
                time.sleep(10)

            center = get_screen()

            try:
                win = pygetwindow.getWindowsWithTitle("Raid: Shadow Legends")[0]
                win.size = (900, 600)
                win.moveTo(center[0], center[1])
                break
            except IndexError:
                time.sleep(20)
                win = pygetwindow.getWindowsWithTitle("Raid: Shadow Legends")[0]
                win.size = (900, 600)
                win.moveTo(center[0], center[1])
                break
    time.sleep(15)
    return "Raid Opened"


if __name__ == "__main__":
    openRaid()
