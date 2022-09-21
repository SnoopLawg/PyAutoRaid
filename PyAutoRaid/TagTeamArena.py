#Same as classic arena, but don't loop through with gems cuz expensiveee
import pyautogui
import cv2
import tkinter as ttk
import time
from LoopFindImage import LoopFindImage


def TagTeamArena():
    while pyautogui.locateOnScreen(r"assets\exitAdd.png",confidence=0.8) !=None:
            adx,ady=pyautogui.locateCenterOnScreen(r"assets\exitAdd.png",confidence=0.8)
            pyautogui.click(adx,ady)
            with open("log.txt", mode='a') as file:
                file.write("\n ad closed")
            time.sleep(2)
    while pyautogui.locateOnScreen(r"assets\battleBTN.png",confidence=0.8) !=None:
        battlex,battley=pyautogui.locateCenterOnScreen(r"assets\battleBTN.png",confidence=0.9)
        pyautogui.click(battlex,battley)
        with open("log.txt", mode='a') as file:
            file.write("\n battle button pressed")
        time.sleep(2)
    while pyautogui.locateOnScreen(r"assets\arenaTab.png",confidence=0.8) !=None:
        battlex,battley=pyautogui.locateCenterOnScreen(r"assets\arenaTab.png",confidence=0.9)
        pyautogui.click(battlex,battley)
        with open("log.txt", mode='a') as file:
            file.write("\n arena tab clicked")
        time.sleep(2)
    while pyautogui.locateOnScreen(r"assets\TagTeamArena.png",confidence=0.8) !=None:
        battlex,battley=pyautogui.locateCenterOnScreen(r"assets\TagTeamArena.png",confidence=0.9)
        pyautogui.click(battlex,battley)
        with open("log.txt", mode='a') as file:
            file.write("\n classic arena tab clicked")
        time.sleep(2)
    if pyautogui.locateOnScreen(r"assets\tagTeamBazaar.png",confidence=0.8) !=None:
            goBackx,goBacky=pyautogui.locateCenterOnScreen(r"assets\tagTeamBazaar.png",confidence=0.8)
            pyautogui.click(goBackx,goBacky)
            print("tag team bazaar opened")
            time.sleep(1)
    if pyautogui.locateOnScreen(r"assets\tagTeamknight.png",confidence=0.8) !=None:
            goBackx,goBacky=pyautogui.locateCenterOnScreen(r"assets\tagTeamknight.png",confidence=0.8)
            pyautogui.click(goBackx,goBacky)
            print("tag team knight clicked")
            time.sleep(1)
            pyautogui.click(1071,691)
            time.sleep(1)
            pyautogui.click(592,355)
    while pyautogui.locateOnScreen(r"assets\exitAdd.png",confidence=0.8) !=None:
            adx,ady=pyautogui.locateCenterOnScreen(r"assets\exitAdd.png",confidence=0.8)
            pyautogui.click(adx,ady)
            with open("log.txt", mode='a') as file:
                file.write("\n ad closed")
            time.sleep(2)
            pyautogui.click(592,355)
    
######################################################Need to not make this forever loop happen
    done=0
    for i in range(0,2):
            #Top battle
            if pyautogui.locateOnScreen(r"assets\tagArenaBattle.png",region=(1199,415,193,100),confidence=0.8) !=None:
                pyautogui.click(1304,457)
                time.sleep(1)
                while pyautogui.locateOnScreen(r"assets\arenaConfirm.png",confidence=0.8) !=None:
                    battlex,battley=pyautogui.locateCenterOnScreen(r"assets\arenaConfirm.png",confidence=0.9)
                    pyautogui.click(battlex,battley)
                    print("confirm tokens")
                    time.sleep(2)
                    pyautogui.click(1304,457)
                    time.sleep(1)
                if pyautogui.locateOnScreen(r"assets\TagArenaNeedGems.png",confidence=0.8) !=None:
                    break
                LoopFindImage(r"assets\arenaStart.png","\n arena battle started")
                print("First Battle")
                while pyautogui.locateOnScreen(r"assets\tapToContinue.png",confidence=0.8) ==None:
                    if done>=2:
                        done=5
                    if done==1:
                        break
                    print("First time looking for continue")
                    time.sleep(1)
                    while pyautogui.locateOnScreen(r"assets\tapToContinue.png",confidence=0.8) !=None:
                        time.sleep(1)
                        goBackx,goBacky=pyautogui.locateCenterOnScreen(r"assets\tapToContinue.png",confidence=0.8)
                        pyautogui.click(goBackx,goBacky)
                        print("finishing arena battle")
                        time.sleep(1)
                        pyautogui.click(970,739)
                        print("breaking first battle")
                        done=1
                        continue
            time.sleep(1)
            pyautogui.doubleClick(953,793,interval=1)
            pyautogui.doubleClick(964,746,interval=1)
            #Second battle
            if done >=4:
                pyautogui.drag(0,-600,duration=2)
                time.sleep(5)
            if pyautogui.locateOnScreen(r"assets\tagArenaBattle.png",region=(1201,510,193,98),confidence=0.8) !=None:
                pyautogui.click(1304,540)
                time.sleep(2)
                while pyautogui.locateOnScreen(r"assets\arenaConfirm.png",confidence=0.8) !=None:
                    battlex,battley=pyautogui.locateCenterOnScreen(r"assets\arenaConfirm.png",confidence=0.9)
                    pyautogui.click(battlex,battley)
                    print("confirm tokens")
                    time.sleep(2)
                    pyautogui.click(1304,540)
                    time.sleep(1)
                if pyautogui.locateOnScreen(r"assets\TagArenaNeedGems.png",confidence=0.8) !=None:
                    exit()
                LoopFindImage(r"assets\arenaStart.png","\n arena battle started")
                print("Second Battle")
                while pyautogui.locateOnScreen(r"assets\tapToContinue.png",confidence=0.8) ==None:
                    if done>=3:
                        done=6
                    if done==2:
                        break
                    print("Second time looking for continue")
                    time.sleep(1)
                    while pyautogui.locateOnScreen(r"assets\tapToContinue.png",confidence=0.8) !=None:
                        time.sleep(1)
                        goBackx,goBacky=pyautogui.locateCenterOnScreen(r"assets\tapToContinue.png",confidence=0.8)
                        pyautogui.click(goBackx,goBacky)
                        print("finishing arena battle")
                        time.sleep(1)
                        pyautogui.click(970,739)
                        print("breaking second battle")
                        done=2
                        continue
            time.sleep(1)
            pyautogui.doubleClick(953,793,interval=1)
            pyautogui.doubleClick(964,746,interval=1)
            if done >=4:
                pyautogui.drag(0,-600,duration=2)
                time.sleep(5)
            #Third battle
            if pyautogui.locateOnScreen(r"assets\tagArenaBattle.png",region=(1198,606,198,100),confidence=0.8) !=None:
                pyautogui.click(1303,625)
                time.sleep(1)
                while pyautogui.locateOnScreen(r"assets\arenaConfirm.png",confidence=0.8) !=None:
                    battlex,battley=pyautogui.locateCenterOnScreen(r"assets\arenaConfirm.png",confidence=0.9)
                    pyautogui.click(battlex,battley)
                    print("confirm tokens")
                    time.sleep(2)
                    pyautogui.click(1303,625)
                    time.sleep(1)
                if pyautogui.locateOnScreen(r"assets\TagArenaNeedGems.png",confidence=0.8) !=None:
                    break
                LoopFindImage(r"assets\arenaStart.png","\n arena battle started")
                print("Third Battle")
                while pyautogui.locateOnScreen(r"assets\tapToContinue.png",confidence=0.8) ==None:
                    if done>=4:
                        done=7
                    if done==3:
                        break
                    print("Third time looking for continue")
                    time.sleep(1)
                    while pyautogui.locateOnScreen(r"assets\tapToContinue.png",confidence=0.8) !=None:
                        time.sleep(1)
                        goBackx,goBacky=pyautogui.locateCenterOnScreen(r"assets\tapToContinue.png",confidence=0.8)
                        pyautogui.click(goBackx,goBacky)
                        print("finishing arena battle")
                        time.sleep(1)
                        pyautogui.click(970,739)
                        print("breaking third battle")
                        done=3
                        continue
            time.sleep(1)
            pyautogui.doubleClick(953,793,interval=1)
            pyautogui.doubleClick(964,746,interval=1)
            time.sleep(1)
            if done >=4:
                pyautogui.drag(0,-600,duration=2)
                time.sleep(5)
            if pyautogui.locateOnScreen(r"assets\tagArenaBattle.png",region=(1200,702,194,96) ,confidence=0.9) !=None:
            #Fourth battle
                pyautogui.click(1304,738)
                time.sleep(1)
                while pyautogui.locateOnScreen(r"assets\arenaConfirm.png",confidence=0.8) !=None:
                    battlex,battley=pyautogui.locateCenterOnScreen(r"assets\arenaConfirm.png",confidence=0.9)
                    pyautogui.click(battlex,battley)
                    print("confirm tokens")
                    time.sleep(2)
                    pyautogui.click(1304,711)
                    time.sleep(1)
                if pyautogui.locateOnScreen(r"assets\TagArenaNeedGems.png",confidence=0.8) !=None:
                    break
                LoopFindImage(r"assets\arenaStart.png","\n arena battle started")
                print("Fourth Battle")
                while pyautogui.locateOnScreen(r"assets\tapToContinue.png",confidence=0.8) ==None:
                    if done>=5:
                        done=8
                    if done==4:
                        break
                    print("Fourth time looking for continue")
                    time.sleep(1)
                    while pyautogui.locateOnScreen(r"assets\tapToContinue.png",confidence=0.8) !=None:
                        time.sleep(1)
                        goBackx,goBacky=pyautogui.locateCenterOnScreen(r"assets\tapToContinue.png",confidence=0.8)
                        pyautogui.click(goBackx,goBacky)
                        print("finishing arena battle")
                        time.sleep(1)
                        pyautogui.click(970,739)
                        print("breaking fourth battle")
                        done=4
                        continue
            time.sleep(1)
            pyautogui.doubleClick(953,793,interval=1)
            pyautogui.doubleClick(964,746,interval=1)
            time.sleep(1)
            if done >=4:
                pyautogui.drag(0,-600,duration=2)
                time.sleep(5)
        
            while pyautogui.locateOnScreen(r"assets\arenaRefresh.png",confidence=0.8) !=None:
                goBackx,goBacky=pyautogui.locateCenterOnScreen(r"assets\arenaRefresh.png",confidence=0.8)
                pyautogui.click(goBackx,goBacky)
                print("arena refreshed")
                time.sleep(1)
                done=15
##            if done!=15:
##                if pyautogui.locateOnScreen(r"assets\arenaRefreshGems.png",confidence=0.8) !=None:
##                    goBackx,goBacky=pyautogui.locateCenterOnScreen(r"assets\arenaRefreshGems.png",confidence=0.8)
##                    pyautogui.click(goBackx,goBacky)
##                    print("arena refreshed with gems")
##                    time.sleep(1)
##                    done=6
    #Out of the loop back out now
    if pyautogui.locateOnScreen(r"assets\tagTeamBazaar.png",confidence=0.8) !=None:
            goBackx,goBacky=pyautogui.locateCenterOnScreen(r"assets\tagTeamBazaar.png",confidence=0.8)
            pyautogui.click(goBackx,goBacky)
            print("tag team bazaar opened")
            time.sleep(1)
    if pyautogui.locateOnScreen(r"assets\tagTeamknight.png",confidence=0.8) !=None:
            goBackx,goBacky=pyautogui.locateCenterOnScreen(r"assets\tagTeamknight.png",confidence=0.8)
            pyautogui.click(goBackx,goBacky)
            print("tag team knight clicked")
            time.sleep(1)
            pyautogui.click(1071,691)
            time.sleep(1)
    while pyautogui.locateOnScreen(r"assets\exitAdd.png",confidence=0.8) !=None:
            adx,ady=pyautogui.locateCenterOnScreen(r"assets\exitAdd.png",confidence=0.8)
            pyautogui.click(adx,ady)
            with open("log.txt", mode='a') as file:
                file.write("\n ad closed")
            time.sleep(2)
    while pyautogui.locateOnScreen(r"assets\goBack.png",confidence=0.8) !=None:
            goBackx,goBacky=pyautogui.locateCenterOnScreen(r"assets\goBack.png",confidence=0.8)
            pyautogui.click(goBackx,goBacky)
            with open("log.txt", mode='a') as file:
                file.write("\n Back to bastion")
            time.sleep(1)
    while pyautogui.locateOnScreen(r"assets\exitAdd.png",confidence=0.8) !=None:
            adx,ady=pyautogui.locateCenterOnScreen(r"assets\exitAdd.png",confidence=0.8)
            pyautogui.click(adx,ady)
            with open("log.txt", mode='a') as file:
                file.write("\n ad closed")
            time.sleep(2)

if __name__== '__main__':           
    TagTeamArena()


