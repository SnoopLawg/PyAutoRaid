#open Raid
import operator
import time
import os
import pygetwindow
from quitAll import quitAll
import pyautogui
from CheckFilesExist import CheckFilesExist, CheckOS

def openRaid():
    quitAll()
    operating=CheckOS()
    if operating == 'Windows':
        # os.startfile(r"C:\Users\logan\AppData\Local\PlariumPlay\PlariumPlay.exe")
        # time.sleep(8)
        # while pyautogui.locateOnScreen(r"assets\PPlay.png",confidence=0.8) ==None:
        #     time.sleep(2)
        #     while pyautogui.locateOnScreen(r"assets\PPlay.png",confidence=0.8) !=None:
        #         PPlayx,PPlayy=pyautogui.locateCenterOnScreen(r"assets\PPlay.png",confidence=0.8)
        #         pyautogui.click(PPlayx,PPlayy)
        #         with open("log.txt", mode='a') as file:
        #             file.write("\n playing PP")
        #         time.sleep(2)
        os.startfile("C:\Program Files\RSL_Helper_X64\RSLHelper.exe")
        time.sleep(10)
    elif operating == 'Darwin':
        os.startfile(r"C:\Users\logan\AppData\Local\PlariumPlay\PlariumPlay.exe")
        time.sleep(8)
        while pyautogui.locateOnScreen(r"assets\PPlay.png",confidence=0.8) !=None:
            PPlayx,PPlayy=pyautogui.locateCenterOnScreen(r"assets\PPlay.png",confidence=0.8)
            pyautogui.click(PPlayx,PPlayy)
            with open("log.txt", mode='a') as file:
                file.write("\n playing PP")
            time.sleep(2)

    with open("log.txt", mode='a') as file:
            file.write("\n files opening")
    os.system("taskkill /f /im PlariumPlay.exe")
    time.sleep(20)
  
    try:
        win = pygetwindow.getWindowsWithTitle('Raid: Shadow Legends')[0]
        win.size = (900, 600)
        win.moveTo(510,240)
    except IndexError:
        time.sleep(20)
        win = pygetwindow.getWindowsWithTitle('Raid: Shadow Legends')[0]
        win.size = (900, 600)
        win.moveTo(510,240)

if __name__=='__main__':
    openRaid()