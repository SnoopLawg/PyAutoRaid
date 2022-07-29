#Fight 10 classic arena battles
import pyautogui
import time
from LoopFindImage import LoopFindImage

def ClassicArena():
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
    while pyautogui.locateOnScreen(r"assets\classicArena.png",confidence=0.8) !=None:
        battlex,battley=pyautogui.locateCenterOnScreen(r"assets\classicArena.png",confidence=0.9)
        pyautogui.click(battlex,battley)
        with open("log.txt", mode='a') as file:
            file.write("\n classic arena tab clicked")
        time.sleep(2)
######################################################Need to not make this forever loop happen
    done=0
    for i in range(0,2):
            #Top battle
            if pyautogui.locateOnScreen(r"assets\arenaBattle.png",region=(1215,423,167,58),confidence=0.8) !=None:
                pyautogui.click(1304,457)
                time.sleep(1)
                while pyautogui.locateOnScreen(r"assets\arenaConfirm.png",confidence=0.8) !=None:
                    battlex,battley=pyautogui.locateCenterOnScreen(r"assets\arenaConfirm.png",confidence=0.9)
                    pyautogui.click(battlex,battley)
                    print("confirm tokens")
                    time.sleep(2)
                    pyautogui.click(1304,457)
                LoopFindImage(r"assets\arenaStart.png","\n arena battle started")
                print("First Battle")
                while pyautogui.locateOnScreen(r"assets\tapToContinue.png",confidence=0.8) ==None:
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
                        pyautogui.click(goBackx,goBacky)
                        print("breaking first battle")
                        done=1
                        continue
            time.sleep(1)
            pyautogui.doubleClick(969,788,interval=1)
            #Second battle
            if pyautogui.locateOnScreen(r"assets\arenaBattle.png",region=(1212,508,170,59),confidence=0.8) !=None:
                pyautogui.click(1304,540)
                time.sleep(1)
                while pyautogui.locateOnScreen(r"assets\arenaConfirm.png",confidence=0.8) !=None:
                    battlex,battley=pyautogui.locateCenterOnScreen(r"assets\arenaConfirm.png",confidence=0.9)
                    pyautogui.click(battlex,battley)
                    print("confirm tokens")
                    time.sleep(2)
                    pyautogui.click(1304,540)
                LoopFindImage(r"assets\arenaStart.png","\n arena battle started")
                print("Second Battle")
                while pyautogui.locateOnScreen(r"assets\tapToContinue.png",confidence=0.8) ==None:
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
                        pyautogui.click(goBackx,goBacky)
                        print("breaking second battle")
                        done=2
                        continue
            time.sleep(1)
            pyautogui.doubleClick(969,788,interval=1)
            #Third battle
            if pyautogui.locateOnScreen(r"assets\arenaBattle.png",region=(1217,596,164,58),confidence=0.8) !=None:
                pyautogui.click(1303,625)
                time.sleep(1)
                while pyautogui.locateOnScreen(r"assets\arenaConfirm.png",confidence=0.8) !=None:
                    battlex,battley=pyautogui.locateCenterOnScreen(r"assets\arenaConfirm.png",confidence=0.9)
                    pyautogui.click(battlex,battley)
                    print("confirm tokens")
                    time.sleep(2)
                    pyautogui.click(1303,625)
                LoopFindImage(r"assets\arenaStart.png","\n arena battle started")
                print("Third Battle")
                while pyautogui.locateOnScreen(r"assets\tapToContinue.png",confidence=0.8) ==None:
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
                        pyautogui.click(goBackx,goBacky)
                        print("breaking third battle")
                        done=3
                        continue
            time.sleep(1)
            pyautogui.doubleClick(969,788,interval=1)
            time.sleep(1)
            if pyautogui.locateOnScreen(r"assets\arenaBattle.png",region=(1212,679,170,62),confidence=0.9) !=None:
            #Fourth battle
                pyautogui.click(1304,711)
                time.sleep(1)
                while pyautogui.locateOnScreen(r"assets\arenaConfirm.png",confidence=0.8) !=None:
                    battlex,battley=pyautogui.locateCenterOnScreen(r"assets\arenaConfirm.png",confidence=0.9)
                    pyautogui.click(battlex,battley)
                    print("confirm tokens")
                    time.sleep(2)
                    pyautogui.click(1304,711)
                LoopFindImage(r"assets\arenaStart.png","\n arena battle started")
                print("Fourth Battle")
                while pyautogui.locateOnScreen(r"assets\tapToContinue.png",confidence=0.8) ==None:
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
                        pyautogui.click(goBackx,goBacky)
                        print("breaking fourth battle")
                        done=4
                        continue
            time.sleep(1)
            pyautogui.doubleClick(969,788,interval=1)
            time.sleep(1)
            if pyautogui.locateOnScreen(r"assets\arenaBattle.png",region=(1208,761,177,68),confidence=0.8) !=None:
            #Fifth battle
                pyautogui.click(1304,798)
                time.sleep(1)
                while pyautogui.locateOnScreen(r"assets\arenaConfirm.png",confidence=0.8) !=None:
                    battlex,battley=pyautogui.locateCenterOnScreen(r"assets\arenaConfirm.png",confidence=0.9)
                    pyautogui.click(battlex,battley)
                    print("confirm tokens")
                    time.sleep(2)
                    pyautogui.click(1304,798)
                LoopFindImage(r"assets\arenaStart.png","\n arena battle started")
                print("Fifth Battle")
                while pyautogui.locateOnScreen(r"assets\tapToContinue.png",confidence=0.8) ==None:
                    if done==5:
                        break
                    print("fifth time looking for continue")
                    time.sleep(1)
                    while pyautogui.locateOnScreen(r"assets\tapToContinue.png",confidence=0.8) !=None:
                        time.sleep(1)
                        goBackx,goBacky=pyautogui.locateCenterOnScreen(r"assets\tapToContinue.png",confidence=0.8)
                        pyautogui.click(goBackx,goBacky)
                        print("finishing arena battle")
                        time.sleep(1)
                        pyautogui.click(goBackx,goBacky)
                        print("breaking fifth battle")
                        done=5
                        continue
            time.sleep(1)
            pyautogui.doubleClick(969,788,interval=1)
        
            while pyautogui.locateOnScreen(r"assets\arenaRefresh.png",confidence=0.8) !=None:
                goBackx,goBacky=pyautogui.locateCenterOnScreen(r"assets\arenaRefresh.png",confidence=0.8)
                pyautogui.click(goBackx,goBacky)
                print("arena refreshed")
                time.sleep(1)
                done=6
    #Out of the loop back out now
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
    
if __name__=='__main__':
    ClassicArena()