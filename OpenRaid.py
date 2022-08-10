#open Raid
import operator
import time
import sys
import os
import pygetwindow
from quitAll import quitAll
import pyautogui
from CheckFilesExist import CheckFilesExist, CheckOS

def openRaid():
    quitAll()
    time.sleep(5)
    operating=CheckOS()
    if operating == 'Darwin':
        os.startfile(r"C:\Users\logan\AppData\Local\PlariumPlay\PlariumPlay.exe")
        time.sleep(8)
        while pyautogui.locateOnScreen(r"assets\PPlay.png",confidence=0.8) !=None:
            PPlayx,PPlayy=pyautogui.locateCenterOnScreen(r"assets\PPlay.png",confidence=0.8)
            pyautogui.click(PPlayx,PPlayy)
            with open("log.txt", mode='a') as file:
                file.write("\n playing PP")
            time.sleep(2)
    elif operating == 'Windows':
        #os.startfile("C:\Program Files\RSL_Helper_X64\RSLHelper.exe")
        os.startfile(r"C:\Users\logan\AppData\Local\PlariumPlay\PlariumPlay.exe")
        #skips after while
        time.sleep(25)
        if pyautogui.locateOnScreen(r"assets\PPMyLibrary.png",confidence=0.8) !=None:
            PPlayx,PPlayy=pyautogui.locateCenterOnScreen(r"assets\PPMyLibrary.png",confidence=0.8)
            pyautogui.click(PPlayx,PPlayy)
            with open("log.txt", mode='a') as file:
                file.write("\n clicking library")
            time.sleep(5)
            if pyautogui.locateOnScreen(r"assets\PPlay.png",confidence=0.8) !=None:
                PPlayx,PPlayy=pyautogui.locateCenterOnScreen(r"assets\PPlay.png",confidence=0.8)
                pyautogui.click(PPlayx,PPlayy)
                with open("log.txt", mode='a') as file:
                    file.write("\n playing PP")
    with open("log.txt", mode='a') as file:
            file.write("\n files opening")
    time_out=0
    while pyautogui.locateOnScreen(r"assets\exitAdd.png",confidence=0.8) ==None:
        time.sleep(.5)
        time_out+=1
        if time_out>=200:
            print('raid never opened lol')
            quitAll()
            sys.exit()
        while pyautogui.locateOnScreen(r"assets\exitAdd.png",confidence=0.8) !=None:
            try:
                win = pygetwindow.getWindowsWithTitle('Raid: Shadow Legends')[0]
                win.size = (900, 600)
                win.moveTo(510,240)
                break
            except IndexError:
                time.sleep(20)
                win = pygetwindow.getWindowsWithTitle('Raid: Shadow Legends')[0]
                win.size = (900, 600)
                win.moveTo(510,240)
                break
    os.system("taskkill /f /im PlariumPlay.exe")

if __name__=='__main__':
    openRaid()