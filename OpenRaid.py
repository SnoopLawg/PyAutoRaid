#open Raid
import time
import os
import pygetwindow
from quitAll import quitAll

def openRaid():
    quitAll()
    os.startfile("C:\Program Files\RSL_Helper_X64\RSLHelper.exe")

    #if rsl helper isnt wokring
##    os.startfile(r"C:\Users\logan\AppData\Local\Plarium\PlariumPlay\PlariumPlay.exe")
##    time.sleep(2)
##    while pyautogui.locateOnScreen(r"assets\PPlay.png",confidence=0.8) !=None:
##        PPlayx,PPlayy=pyautogui.locateCenterOnScreen(r"assets\PPlay.png",confidence=0.8)
##        pyautogui.click(PPlayx,PPlayy)
##        with open("log.txt", mode='a') as file:
##        file.write("\n playing PP")
##        time.sleep(2)

    with open("log.txt", mode='a') as file:
            file.write("\n files opening")
    os.system("taskkill /pid PlariumPlay.exe")
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