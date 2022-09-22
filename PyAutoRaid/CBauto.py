# fight the CB, this one is NM
import pyautogui
import time
from datetime import datetime
from AutoRewards import AutoRewards
from BlackOutMonitor import BlackOutMonitor
from quitAll import quitAll
from OpenRaid import openRaid
import os
import sys
from TimeBetween import is_time_between
import pathlib

dir = str(pathlib.Path().absolute())
# between 4am to 10pm
if is_time_between() == False:
    # NM
    xCB = 1080
    yCB = 724
# between 10pm to 4am
if is_time_between() == True:
    # Brutal
    xCB = 1080
    yCB = 647


def AutoCB(xCB, yCB):
    time.sleep(1.5)
    with open("log.txt", mode="a") as file:
        file.write("\n deleting ads now")
    while pyautogui.locateOnScreen(dir + r"assets\exitAdd.png", confidence=0.8) != None:
        adx, ady = pyautogui.locateCenterOnScreen(
            dir + r"assets\exitAdd.png", confidence=0.8
        )
        pyautogui.click(adx, ady)
        with open("log.txt", mode="a") as file:
            file.write("\n ad closed")
        time.sleep(2)
    while (
        pyautogui.locateOnScreen(dir + r"assets\battleBTN.png", confidence=0.8) != None
    ):
        battlex, battley = pyautogui.locateCenterOnScreen(
            dir + r"assets\battleBTN.png", confidence=0.9
        )
        pyautogui.click(battlex, battley)
        with open("log.txt", mode="a") as file:
            file.write("\n battle button pressed")
        time.sleep(2)
    while pyautogui.locateOnScreen(dir + r"assets\CB.png", confidence=0.9) != None:
        CBx, CBy = pyautogui.locateCenterOnScreen(
            dir + r"assets\CB.png", confidence=0.9
        )
        pyautogui.click(CBx, CBy)
        with open("log.txt", mode="a") as file:
            file.write("\n cb tab clicked")
        time.sleep(3)
    while pyautogui.locateOnScreen(dir + r"assets\CB2.png", confidence=0.9) != None:
        CB2x, CB2y = pyautogui.locateCenterOnScreen(
            dir + r"assets\CB2.png", confidence=0.9
        )
        pyautogui.click(CB2x, CB2y)
        with open("log.txt", mode="a") as file:
            file.write("\n cb tab clicked")
        time.sleep(3)
    while (
        pyautogui.locateOnScreen(dir + r"assets\demonLord.png", confidence=0.9) != None
    ):
        demonLordx, demonLordy = pyautogui.locateCenterOnScreen(
            dir + r"assets\demonLord.png", confidence=0.8
        )
        pyautogui.click(demonLordx, demonLordy)
        with open("log.txt", mode="a") as file:
            file.write("\n demonlord clicked")
        time.sleep(2)
    while (
        pyautogui.locateOnScreen(dir + r"assets\demonLord2.png", confidence=0.9) != None
    ):
        demonLord2x, demonLord2y = pyautogui.locateCenterOnScreen(
            dir + r"assets\demonLord2.png", confidence=0.8
        )
        pyautogui.click(demonLord2x, demonLord2y)
        with open("log.txt", mode="a") as file:
            file.write("\n demonlord clicked")
        time.sleep(4)
    while (
        pyautogui.locateOnScreen(dir + r"assets\CBreward.png", confidence=0.8) != None
    ):
        CBrewardx, CBrewardy = pyautogui.locateCenterOnScreen(
            dir + r"assets\CBreward.png", confidence=0.8
        )
        time.sleep(2)
        pyautogui.click(CBrewardx, CBrewardy)
        with open("log.txt", mode="a") as file:
            file.write("\n rewards checked")
        time.sleep(2)
        while (
            pyautogui.locateOnScreen(
                dir + r"assets\nightmareClaimed.png", confidence=0.8
            )
            != None
        ):
            nightmareClaimedx, nightmareClaimedy = pyautogui.locateCenterOnScreen(
                dir + r"assets\CBclaim.png", confidence=0.5
            )
            pyautogui.click(nightmareClaimedx, nightmareClaimedy)
            time.sleep(1)
            pyautogui.click()
            with open("log.txt", mode="a") as file:
                file.write("\n claim rewards checked")
            # the second click needs to recognize the continue
            time.sleep(1)
            pyautogui.click()
    while pyautogui.locateOnScreen(dir + r"assets\CBclaim.png", confidence=0.8) != None:
        CBclaimx, CBclaimy = pyautogui.locateCenterOnScreen(
            dir + r"assets\CBclaim.png", confidence=0.5
        )
        pyautogui.click(CBclaimx, CBclaimy)
        time.sleep(1)
        pyautogui.click()
        with open("log.txt", mode="a") as file:
            file.write("\n claim rewards checked")
    time.sleep(2)
    while pyautogui.locateOnScreen(dir + r"assets\CBhard.png", confidence=0.8) != None:
        pyautogui.click(xCB, yCB)
        with open("log.txt", mode="a") as file:
            file.write("\n clicked random location, nightmare")
        while (
            pyautogui.locateOnScreen(dir + r"assets\CBbattle.png", confidence=0.8)
            != None
        ):
            CBbattlex, CBbattley = pyautogui.locateCenterOnScreen(
                dir + r"assets\CBbattle.png", confidence=0.8
            )
            time.sleep(2)
            pyautogui.click(CBbattlex, CBbattley)
            with open("log.txt", mode="a") as file:
                file.write("\n about to battle clan boss")
            time.sleep(1)
            if (
                pyautogui.locateOnScreen(dir + r"assets\CBnokey.png", confidence=0.8)
                != None
            ):
                with open("log.txt", mode="a") as file:
                    file.write("\n no keys left")
                break
        time.sleep(1)
    while pyautogui.locateOnScreen(dir + r"assets\CBstart.png", confidence=0.8) != None:
        CBstartx, CBstarty = pyautogui.locateCenterOnScreen(
            dir + r"assets\CBstart.png", confidence=0.8
        )
        time.sleep(2)
        pyautogui.click(CBstartx, CBstarty)
        with open("log.txt", mode="a") as file:
            file.write("\n\n battling clan boss")
        now = datetime.now()
        dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
        with open("log.txt", mode="a") as file:
            file.write(dt_string)
        with open("log.txt", mode="a") as file:
            file.write("\n Date and time of CB battle ")
            file.write(dt_string)
        time.sleep(1)
        while (
            pyautogui.locateOnScreen(dir + r"assets\CBcontinue.png", confidence=0.8)
            != None
        ):
            CBcontinuex, CBcontinuey = pyautogui.locateCenterOnScreen(
                dir + r"assets\CBcontinue.png", confidence=0.8
            )
            time.sleep(2)
            pyautogui.click(CBcontinuex, CBcontinuey)
            time.sleep(200)

        while (
            pyautogui.locateOnScreen(dir + r"assets\gotoBastion.png", confidence=0.8)
            == None
        ):
            while (
                pyautogui.locateOnScreen(dir + r"assets\CBcrashed.png", confidence=0.8)
                != None
            ):
                quitAll()
                with open("log.txt", mode="a") as file:
                    file.write("\n RESTARTING DUE TO CRASH")
                time.sleep(2)
                with open("log.txt", mode="a") as file:
                    file.write("\n Closing for restart")
                time.sleep(2)
                openRaid()
                AutoRewards()
                os.system("taskkill /pid RSLHelper.exe")
                AutoCB()
                quitAll()
                BlackOutMonitor()
                sys.exit()
            while (
                pyautogui.locateOnScreen(dir + r"assets\CBcrashed2.png", confidence=0.8)
                != None
            ):
                quitAll()
                with open("log.txt", mode="a") as file:
                    file.write("\n RESTARTING DUE TO CRASH")
                time.sleep(2)
                with open("log.txt", mode="a") as file:
                    file.write("\n Closing for restart")
                time.sleep(2)
                openRaid()
                AutoRewards()
                os.system("taskkill /pid RSLHelper.exe")
                AutoCB()
                quitAll()
                BlackOutMonitor()
                sys.exit()
            while (
                pyautogui.locateOnScreen(
                    dir + r"assets\gotoBastion.png", confidence=0.8
                )
                != None
            ):
                gotoBastionx, gotoBastiony = pyautogui.locateCenterOnScreen(
                    dir + r"assets\gotoBastion.png", confidence=0.8
                )
                with open("log.txt", mode="a") as file:
                    file.write("\n finished CB battle")
                pyautogui.click(gotoBastionx, gotoBastiony)
                break
    print("test1")
    while pyautogui.locateOnScreen(dir + r"assets\exitAdd.png", confidence=0.8) != None:
        adx, ady = pyautogui.locateCenterOnScreen(
            dir + r"assets\exitAdd.png", confidence=0.8
        )
        pyautogui.click(adx, ady)
        with open("log.txt", mode="a") as file:
            file.write("\n ad closed")
        time.sleep(2)
    print("test2")
    while pyautogui.locateOnScreen(dir + r"assets\goBack.png", confidence=0.8) != None:
        goBackx, goBacky = pyautogui.locateCenterOnScreen(
            dir + r"assets\goBack.png", confidence=0.8
        )
        pyautogui.click(goBackx, goBacky)
        with open("log.txt", mode="a") as file:
            file.write("\n Back to bastion")
        time.sleep(1)
    while pyautogui.locateOnScreen(dir + r"assets\exitAdd.png", confidence=0.8) != None:
        adx, ady = pyautogui.locateCenterOnScreen(
            dir + r"assets\exitAdd.png", confidence=0.8
        )
        pyautogui.click(adx, ady)
        with open("log.txt", mode="a") as file:
            file.write("\n ad closed")
    print("test3")


if __name__ == "__main__":
    # between 4am to 10pm
    if is_time_between() == False:
        # NM
        AutoCB(1080, 724)
    # between 10pm to 4am
    if is_time_between() == True:
        # Brutal
        AutoCB(1080, 647)
