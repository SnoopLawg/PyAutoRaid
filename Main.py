#Run all of the raid functions. 

from CBauto import AutoCB
from AutoRewards import AutoRewards
from BlackOutMonitor import BlackOutMonitor
from ClassicArena import ClassicArena
from OpenRaid import openRaid
from quitAll import quitAll
from NightmareAttemptText import NightmareAttemptText
from CheckFilesExist import CheckFilesExist,CheckOS
import sys
import pyautogui


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

quitAll()
BlackOutMonitor()
sys.exit()
