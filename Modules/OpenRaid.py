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
        PATH_PP = "~\AppData\Local\PlariumPlay\PlariumPlay.exe"
        FULL_PATH_PP = os.path.expanduser(PATH_PP)
        # PATH_RSL = (
        #     "~\\AppData\\Local\\PlariumPlay\\StandAloneApps\\raid\\36484\\Raid.exe"
        # )
        # FULL_PATH_RSL = os.path.expanduser(PATH_PP)
        # os.startfile("C:\Program Files\RSL_Helper_X64\RSLHelper.exe")
        os.startfile(FULL_PATH_PP)
        # skips after while
        all_windows = pygetwindow.getAllTitles()
        while "Plarium Play" not in all_windows:
            all_windows = pygetwindow.getAllTitles()
            print("Waiting for Plarium Play to open")
            time.sleep(1)
        # time.sleep(5)
        # os.startfile(FULL_PATH_RSL)
        # count = 0
        # while "Raid: Shadow Legends" not in all_windows or count == 30:
        #     all_windows = pygetwindow.getAllTitles()
        #     print("Waiting for Raid to open")
        #     time.sleep(1)
        #     count += 1
        while (
            pyautogui.locateOnScreen(
                ASSETS_PATH + "\\MyLibraryPP.png",
                confidence=0.8,
            )
            is None
        ):
            print("waiting to click library")
            time.sleep(1)
        time.sleep(1.5)
        PPlibraryx, PPlibraryy = pyautogui.locateCenterOnScreen(
            ASSETS_PATH + "\\MyLibraryPP.png",
            confidence=0.8,
        )
        pyautogui.click(PPlibraryx, PPlibraryy)
        with open("log.txt", mode="a") as file:
            file.write("\n clicking library")
        # wait till plarium play button becomes available
        time.sleep(3.5)
        if (
            pyautogui.locateOnScreen(
                ASSETS_PATH + "\\PPlay.png",
                confidence=0.8,
            )
            != None
        ):
            while (
                pyautogui.locateOnScreen(
                    ASSETS_PATH + "\\PPlay.png",
                    confidence=0.8,
                )
                == None
            ):
                print("waiting to click play")
            PPlayx, PPlayy = pyautogui.locateCenterOnScreen(
                ASSETS_PATH + "\\PPlay.png", confidence=0.8
            )
            time.sleep(1)
            pyautogui.click(PPlayx, PPlayy)
            with open("log.txt", mode="a") as file:
                file.write("\n playing PP")
        else:
            win = pygetwindow.getWindowsWithTitle("Plarium Play")[0]
            win.size = (900, 600)
            win.moveTo(0, 0)
            time.sleep(1)
            pyautogui.click(84, 240)
            time.sleep(5)
            while (
                pyautogui.locateOnScreen(
                    ASSETS_PATH + "\\PPlay.png",
                    confidence=0.8,
                )
                == None
            ):
                time.sleep(1)
                pyautogui.click(84, 240)
                pyautogui.click(953, 139)
                time_out = 0
                all_windows = pygetwindow.getAllTitles()
                if "Raid: Shadow Legends" in all_windows:
                    break
                time_out += 1
                if time_out >= 100:
                    print("raid never opened lol")
                    quitAll()
                    import Main

                    Main.main()

    with open("log.txt", mode="a") as file:
        file.write("\n files opening")
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
            time.sleep(1)

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
