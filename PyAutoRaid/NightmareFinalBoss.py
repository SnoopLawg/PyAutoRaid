import pyautogui
import time
import pathlib

dir = str(pathlib.Path().absolute())
while True:
    if (
        pyautogui.locateOnScreen(
            dir + r"\\assets\Paragon2.png",
            confidence=0.9,
        )
        != None
    ):
        while (
            pyautogui.locateOnScreen(
                dir + r"\\assets\Paragon2.png",
                confidence=0.8,
            )
            != None
        ):
            goBackx, goBacky = pyautogui.locateCenterOnScreen(
                dir + r"\\assets\Paragon2.png",
                confidence=0.8,
            )
            pyautogui.click(goBackx, goBacky)
            print("invincible paragon")
            pyautogui.click(853, 625)
    elif (
        pyautogui.locateOnScreen(
            dir + r"\\assets\Paragon2.png",
            confidence=0.9,
        )
        != None
    ):
        while (
            pyautogui.locateOnScreen(
                dir + r"\\assets\Paragon2.png",
                confidence=0.8,
            )
            != None
        ):
            goBackx, goBacky = pyautogui.locateCenterOnScreen(
                dir + r"\\assets\Paragon2.png",
                confidence=0.8,
            )
            pyautogui.click(goBackx, goBacky)
            print("invincible paragon")
            pyautogui.click(853, 625)
    elif (
        pyautogui.locateOnScreen(
            dir + r"\\assets\Paragon1.png",
            confidence=0.8,
        )
        != None
    ):
        while (
            pyautogui.locateOnScreen(
                dir + r"\\assets\Paragon1.png",
                confidence=0.8,
            )
            != None
        ):
            goBackx, goBacky = pyautogui.locateCenterOnScreen(
                dir + r"\\assets\Paragon1.png",
                confidence=0.8,
            )
            pyautogui.click(goBackx, goBacky)
            print("a1 paragon")
            time.sleep(1)
            pyautogui.click(913, 451)
            pyautogui.click(1001, 459)
            pyautogui.click(1109, 519)
            pyautogui.click(1260, 566)
