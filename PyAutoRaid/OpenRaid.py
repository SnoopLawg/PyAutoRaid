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
import os


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
    elif operating == "Windows":
        PATH = "~\AppData\Local\PlariumPlay\PlariumPlay.exe"
        FULL_PATH = os.path.expanduser(PATH)
        # os.startfile("C:\Program Files\RSL_Helper_X64\RSLHelper.exe")
        os.startfile(FULL_PATH)
        # skips after while
        all_windows = pygetwindow.getAllTitles()
        while "Plarium Play" not in all_windows:
            all_windows = pygetwindow.getAllTitles()
            print("Waiting for Plarium Play to open")
            time.sleep(1)
        while (
            pyautogui.locateOnScreen(
                DIR + "\\PyAutoRaid\\assets\\MyLibraryPP.png", confidence=0.8
            )
            is None
        ):
            print("waiting to click library")
            time.sleep(1)
        time.sleep(1.5)
        PPlibraryx, PPlibraryy = pyautogui.locateCenterOnScreen(
            DIR + "\\PyAutoRaid\\assets\\MyLibraryPP.png", confidence=0.8
        )
        pyautogui.click(PPlibraryx, PPlibraryy)
        with open("log.txt", mode="a") as file:
            file.write("\n clicking library")
        # wait till plarium play button becomes available
        time.sleep(3.5)
        if (
            pyautogui.locateOnScreen(
                DIR + "\\PyAutoRaid\\assets\\PPlay.png", confidence=0.8
            )
            != None
        ):
            while (
                pyautogui.locateOnScreen(
                    DIR + "\\PyAutoRaid\\assets\\PPlay.png", confidence=0.8
                )
                == None
            ):
                print("waiting to click play")
            PPlayx, PPlayy = pyautogui.locateCenterOnScreen(
                DIR + "\\PyAutoRaid\\\\assets\PPlay.png", confidence=0.8
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
                    DIR + "\\PyAutoRaid\\assets\\PPlay.png", confidence=0.8
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
                if time_out >= 200:
                    print("raid never opened lol")
                    quitAll()

    with open("log.txt", mode="a") as file:
        file.write("\n files opening")
    time_out = 0
    while (
        pyautogui.locateOnScreen(
            DIR + "\\PyAutoRaid\\assets\\exitAdd.png", confidence=0.8
        )
        == None
    ):
        time_out += 1
        time.sleep(0.5)

        if time_out >= 200:
            print("raid never opened lol")
            quitAll()
            pyautogui.hotkey("winleft", "m")
            pyautogui.doubleClick(440, 362)
        while "Raid: Shadow Legends" not in all_windows:
            all_windows = pygetwindow.getAllTitles()
            print("Waiting for Raid to open")
            time.sleep(1)
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
    time.sleep(15)


if __name__ == "__main__":
    openRaid()
