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
import sys
import pyautogui

def main():
    CheckFilesExist()
    CheckOS()
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
    try:    
        AutoRewards()
    except TypeError:
        AutoRewards()
    try:        
        AutoCB()
    except TypeError:
        AutoCB()
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
    try:
        main()
    except PermissionError:
        pass