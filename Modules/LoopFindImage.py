# shortened finding an image
import pyautogui
import time


def LoopFindImage(image, txtfile):
    while pyautogui.locateOnScreen(image, confidence=0.8) != None:
        time.sleep(0.5)
        adx, ady = pyautogui.locateCenterOnScreen(image, confidence=0.8)
        pyautogui.click(adx, ady)
        time.sleep(3)


def IfFindImage(image, txtfile):
    if pyautogui.locateOnScreen(image, confidence=0.8):
        time.sleep(0.5)
        adx, ady = pyautogui.locateCenterOnScreen(image, confidence=0.8)
        pyautogui.click(adx, ady)
        time.sleep(2)


if __name__ == "__main__":
    LoopFindImage()
    IfFindImage()
