#quit all python processes
import time
import os

def quitAll():
    time.sleep(5)
    os.system("taskkill /f /im RSLHelper.exe")
    os.system("taskkill /f /im  Raid.exe")
    time.sleep(3)
    os.system("taskkill /pid PlariumPlay.exe")

if __name__=='__main__':
        quitAll()