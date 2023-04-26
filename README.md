# PyAutoRaid
![raid-header](https://user-images.githubusercontent.com/30202466/181846024-930b7120-0af6-4280-b727-87bdd4ade7b8.jpeg)

[![Step-by-Step Video Download Guide](https://img.youtube.com/vi/YOUTUBE_VIDEO_ID_HERE/0.jpg)](https://www.veed.io/view/debfc16b-bd96-4cad-b453-3d308da56cb4?panel=share)

### How to Use
1. Download PyAutoRaid.exe
[DOWNLOADE HERE](https://github.com/SnoopLawg/PyAutoRaid/releases/download/v1.5-beta/Main.exe)<br>
(You can now run it by clicking it)
This installs the folders needed (Modules and Assets). 
##DO NOT REMOVE THE .exe from this folder.
(Make a shortcut instead on the desktop.)

###### optional:<br>
  Make the app run incrementally:

2. Open "Windows Task Scheduler"
3. Click "Create Task" on the top right
4. Name it whatever you want (doesnt matter)
5. Click "Run with Hightest Privileges"
6. Click "Triggers", then "New".., and then select whatever you want. (however often you want it to run. I run it "Daily" , and I set the start to be todays date and the top of the next hour. I then click the "Repeat task every hour""
7. Click OK
8. Click "Actions", then "New...", "Browse...", and then find the exe file wherever you placed it.
9. Click OK
10. This should now run the app however often you set it in Windows Task Scheduler. You can test to see if it works by clicking on your task under the Task Scheduler Library Folder on the top left, and clicking Run on the far right side.

When running the program for the first time be sure to make your changes then submit on the gui.

### Technical
I am trying to automate Raid: Shadow Legends  without accessing game data but using pyautogui and finding images on the game's screen. I wish to do it with gamedata but I do not know how, and I know autoclickers are allowed in RSL so this is my novice attempt at it.
- [x] CheckIfFileExists()<br>
      -Checks if you have the correct files
- [x] OpenRaid()<br>
      -Starts and awaits raid to open
- [x] AutoRewards()<br>
      -Collects Gem Mine, Daily quests, Advanced Quests, Inbox, Upgrades champions in autoupgrade thing, and buys mystery and ancient shards from market.
- [x] AutoCB()<br>
      -My FAVORITE (and reason I made this app). Attacks clan boss depending on what you set in your GUI. If met the number of battles (Ex. 2/2 UNM fights) it will move on to the next difficulty. If you completed all fights you need (you put in the gui) it will default to UNM fighting.
- [x] ClassicArena()<br>
      -Battles 10 times or until out of coins. Will also buy Drexthar Bloodtwin if not yet purchased
- [x] quitAll()<br>
      -Quits out of everything including Raid, Plarium and this app.
- [x] BlackOutMonitor()<br>
      -Blacks out your monitors without turning off your computer. (I use this so I can run this like every hour and not have my monitors on always)
- [x] TagTeamArena()<br>
      -Battles 10 times or until out of coins
- [ ] AutoUpgrader<br>
      -Cannot control mouseclicks when I run RSLHELPER by farbstoff... so I would have to get gamedata. (NEED HELP!!)
- [x] Gui<br>
      -Gui popup to manage what you want to run
- [x] Exe file for all of this<br>
      -PyAutoRaid.exe created


