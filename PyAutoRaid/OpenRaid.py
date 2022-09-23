# open Raid
import operator
from posixpath import expanduser
import time
import os, sys, subprocess
import pygetwindow
from quitAll import quitAll
import pyautogui
from CheckFilesExist import CheckOS
import pathlib


DIR = str(pathlib.Path().absolute())


def openRaid():
    quitAll()
    time.sleep(5)
    operating = CheckOS()
    if operating == "Darwin":
        PATH = "/Applications/Plarium Play.app"
        FULL_PATH = os.path.expanduser(PATH)
        subprocess.call(["open", FULL_PATH])
        time.sleep(30)
        # TODO: Fix the clicks to open raid
        # while pyautogui.locateOnScreen(r"assets\PPlay.png", confidence=0.8) != None:
        #     PPlayx, PPlayy = pyautogui.locateCenterOnScreen(
        #         r"assets\PPlay.png", confidence=0.8
        #     )
        #     pyautogui.click(PPlayx, PPlayy)
        #     with open("log.txt", mode="a") as file:
        #         file.write("\n playing PP")
        #     time.sleep(2)
    elif operating == "Windows":
        PATH = "~\AppData\Local\PlariumPlay\PlariumPlay.exe"
        FULL_PATH = os.path.expanduser(PATH)
        # os.startfile("C:\Program Files\RSL_Helper_X64\RSLHelper.exe")
        os.startfile(FULL_PATH)
        # skips after while
        time.sleep(30)
        if (
            pyautogui.locateOnScreen(DIR + r"\\assets\\MyLibraryPP.png", confidence=0.8)
            != None
        ):
            PPlayx, PPlayy = pyautogui.locateCenterOnScreen(
                DIR + r"\\assets\\MyLibraryPP.png", confidence=0.8
            )
            pyautogui.click(PPlayx, PPlayy)
            with open("log.txt", mode="a") as file:
                file.write("\n clicking library")
            time.sleep(5)
            if (
                pyautogui.locateOnScreen(DIR + r"\\assets\PPlay.png", confidence=0.8)
                != None
            ):
                PPlayx, PPlayy = pyautogui.locateCenterOnScreen(
                    DIR + r"\\assets\PPlay.png", confidence=0.8
                )
                pyautogui.click(PPlayx, PPlayy)
                with open("log.txt", mode="a") as file:
                    file.write("\n playing PP")
        else:
            pyautogui.click(440, 362)
            time.sleep(5)
            if (
                pyautogui.locateOnScreen(DIR + r"\\assets\PPlay.png", confidence=0.8)
                != None
            ):
                PPlayx, PPlayy = pyautogui.locateCenterOnScreen(
                    DIR + r"\\assets\PPlay.png", confidence=0.8
                )
                pyautogui.click(PPlayx, PPlayy)
                with open("log.txt", mode="a") as file:
                    file.write("\n playing PP")

    with open("log.txt", mode="a") as file:
        file.write("\n files opening")
    time_out = 0
    while (
        pyautogui.locateOnScreen(DIR + r"\\assets\exitAdd.png", confidence=0.8) == None
    ):
        time.sleep(0.5)
        time_out += 1
        if time_out >= 200:
            print("raid never opened lol")
            quitAll()
            pyautogui.hotkey("winleft", "m")
            pyautogui.doubleClick(440, 362)
        while (
            pyautogui.locateOnScreen(DIR + r"\\assets\exitAdd.png", confidence=0.8)
            != None
        ):
            try:
                win = pygetwindow.getWindowsWithTitle("Raid: Shadow Legends")[0]
                win.size = (900, 600)
                win.moveTo(510, 240)
                break
            except IndexError:
                time.sleep(20)
                win = pygetwindow.getWindowsWithTitle("Raid: Shadow Legends")[0]
                win.size = (900, 600)
                win.moveTo(510, 240)
                break
    os.system("taskkill /f /im PlariumPlay.exe")


if __name__ == "__main__":
    openRaid()
