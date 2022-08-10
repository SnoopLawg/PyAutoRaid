#Run all of the raid functions. 

from CBauto import AutoCB
from AutoRewards import AutoRewards
from BlackOutMonitor import BlackOutMonitor
from ClassicArena import ClassicArena
from OpenRaid import openRaid
from quitAll import quitAll
from NightmareAttemptText import NightmareAttemptText
from CheckFilesExist import CheckFilesExist,CheckOS
from TagTeamArena import TagTeamArena
from TimeBetween import is_time_between
import sys
import pyautogui
import multiprocessing
import time

def main():
    CheckFilesExist()
    CheckOS()
    is_time_between()
    try:    
        openRaid()
    except TypeError:
        openRaid()
    except IndexError:
        openRaid()
    try:
        NightmareAttemptText()
    except TypeError:
        NightmareAttemptText()
    #try:    
    AutoRewards()
    # except TypeError:
    #     AutoRewards()
    try:        
        #between 4am to 10pm
        if is_time_between()==False:
            #NM
            AutoCB(1080,724)
        #between 10pm to 4am
        if is_time_between()==True:
            #Brutal
            AutoCB(1080,647)
    except TypeError:
        #between 4am to 10pm
        if is_time_between()==False:
            #NM
            AutoCB(1080,724)
        #between 10pm to 4am
        if is_time_between()==True:
            #Brutal
            AutoCB(1080,647)
    try:        
        ClassicArena()
    except TypeError:
        ClassicArena()
    try:        
        TagTeamArena()
    except TypeError:
        TagTeamArena()  

    quitAll()
    BlackOutMonitor()
    sys.exit()

if __name__=='__main__':
    p = multiprocessing.Process(target=main, name="main")
    p.start()

    # Wait 20 min for foo
    time.sleep(1200)

    # Terminate foo
    p.terminate()

    # Cleanup
    p.join()
    
    
    
    # try:
    #     main()
    # except PermissionError:
    #     pass