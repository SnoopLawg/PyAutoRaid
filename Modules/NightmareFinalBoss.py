import pyautogui
import time
import pathlib
import os
import sys

if getattr(sys, "frozen", False):
    # we are running in a bundle
    DIR = sys._MEIPASS
else:
    # we are running in a normal Python environment
    DIR = os.getcwd()

ASSETS_PATH = os.path.join(DIR, "assets")
while True:
    if (
        pyautogui.locateOnScreen(
            ASSETS_PATH +"\\Paragon2.png",
            confidence=0.9,
        )
        != None
    ):
        while (
            pyautogui.locateOnScreen(
                ASSETS_PATH +"\\Paragon2.png",
                confidence=0.8,
            )
            != None
        ):
            goBackx, goBacky = pyautogui.locateCenterOnScreen(
                ASSETS_PATH +"\\Paragon2.png",
                confidence=0.8,
            )
            pyautogui.click(goBackx, goBacky)
            print("invincible paragon")
            pyautogui.click(853, 625)
    elif (
        pyautogui.locateOnScreen(
            ASSETS_PATH +"\\Paragon2.png",
            confidence=0.9,
        )
        != None
    ):
        while (
            pyautogui.locateOnScreen(
                ASSETS_PATH +"\\Paragon2.png",
                confidence=0.8,
            )
            != None
        ):
            goBackx, goBacky = pyautogui.locateCenterOnScreen(
                ASSETS_PATH +"\\Paragon2.png",
                confidence=0.8,
            )
            pyautogui.click(goBackx, goBacky)
            print("invincible paragon")
            pyautogui.click(853, 625)
    elif (
        pyautogui.locateOnScreen(
            ASSETS_PATH +"\\Paragon1.png",
            confidence=0.8,
        )
        != None
    ):
        while (
            pyautogui.locateOnScreen(
                ASSETS_PATH +"\\Paragon1.png",
                confidence=0.8,
            )
            != None
        ):
            goBackx, goBacky = pyautogui.locateCenterOnScreen(
                ASSETS_PATH +"\\Paragon1.png",
                confidence=0.8,
            )
            pyautogui.click(goBackx, goBacky)
            print("a1 paragon")
            time.sleep(1)
            pyautogui.click(913, 451)
            pyautogui.click(1001, 459)
            pyautogui.click(1109, 519)
            pyautogui.click(1260, 566)
