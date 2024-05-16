import pyautogui, platform, tkinter, logging, os, sys,subprocess,time,random,configparser,psutil,pygetwindow
from screeninfo import Monitor, get_monitors
from tkinter import messagebox
from tkinter import ttk
from tkinter import *
from ttkthemes import ThemedTk
import threading
class Daily:
    def __init__(self,):
        self.running = True
        logging.basicConfig(filename='Logging.log', format='%(levelname)s:%(message)s', encoding='utf-8', level=logging.DEBUG)
        # Clear the existing log file
        with open('Logging.log', 'w'):
            pass
        self.steps = {}
        self.OS = self.Check_os()  # Call the method here
        self.raidLoc = self.find_raid_path()
        self.asset_path=self.get_asset_path()
        self.folders_for_exe()
        windows=pygetwindow.getWindowsWithTitle("Raid: Shadow Legends")
        numwindows=len(pygetwindow.getWindowsWithTitle("Raid: Shadow Legends"))
        # for win in windows:
        #     if win.isMinimized:  # Check if the window is minimized
        #         win.restore()    # Restore it before activating
        #     win.activate() 
        if len(pygetwindow.getWindowsWithTitle("Raid: Shadow Legends")) < 1:
            self.open_raid()
        else:
            self.initiate_raid(False)
        os.system("taskkill /f /im PlariumPlay.exe")
        self.classic_battles = 0
        self.AS_bought=0
        self.MS_bought=0
        self.width=0
        self.height=0
        self.GR_upgrades=0
        self.quests_completed=0
        self.config = configparser.ConfigParser()
        # self.config_file()
        # self.ToDo=dict(self.config.items("QuestsToDo"))
        self.height=0
        # self.settings_config=dict(self.config.items("Settings"))
        self.manual_run_triggered=False
        

    def stop(self,):
        self.running = False
        os.system("taskkill /f /im DailyQuests.exe")
        os.system("taskkill /f /im PyAutoRaid.exe")
        os.system("taskkill /f /im python.exe")
        os.system("taskkill /f /im DailyQuests.py")
        os.system("taskkill /f /im PlariumPlay.exe")

    def trigger_manual_run(self,TF):
        self.manual_run_triggered = TF

    def run(self):
        while self.running:
            # Re-read the config file to update the settings
            self.config.read('DQconfig.ini')
            self.ToDo = dict(self.config.items("QuestsToDo"))
            self.settings_config = dict(self.config.items("Settings"))

            if self.settings_config.get("automated_mode".lower().replace(' ', '_'), 'False') == 'True':
                try:
                    for key in self.ToDo:
                        if self.ToDo[key].lower() == 'true':  # Make sure to compare with 'true'
                            method_to_call = getattr(self, key, None)
                            if method_to_call:
                                method_to_call()
                            else:
                                print(f"Method for {key} not found.")
                    self.close_gui()
                    os.system("taskkill /f /im Raid.exe")
                    # sys.exit()
                    break
                except:
                    self.close_gui()
                    os.system("taskkill /f /im Raid.exe")
                    break
                    # sys.exit()
            else:
                if self.manual_run_triggered:
                    for key in self.ToDo:
                        if self.ToDo[key].lower() == 'true':  # Make sure to compare with 'true'
                            method_to_call = getattr(self, key, None)
                            if method_to_call:
                                method_to_call()
                            else:
                                print(f"Method for {key} not found.")
                    self.trigger_manual_run(False)
            time.sleep(1)  # Sleep to prevent busy waiting
            
    def close_gui(self):
        if self.master:
            self.master.after(0, self.master.destroy)

    def folders_for_exe(self):
        if getattr(sys, 'frozen', False):
            # The application is frozen
            self.asset_path = os.path.join(sys._MEIPASS, 'assets')
            self.steps["Exe_path"]="True"
            return True
        else:
            self.steps["Exe_path"]="False"
            return False

    def Check_os(self):
        operating_system = platform.system()
        if operating_system == "Windows":
            self.steps["OS"]="True"
            return operating_system
        else:
            tkinter.messagebox.showerror(
                "Error",
                "Unrecognized operating system (WINDOWS ONLY)",
            )
            logging.error("Identified this computer as something other than Windows operating system. This program only works with Windows.")
            sys.exit(1)

    def find_raid_path(self):
        appdata_local = os.path.join(os.environ['LOCALAPPDATA'])
        raid_feature = "Raid.exe"
        for root, dirs, files in os.walk(appdata_local):
            if raid_feature in dirs or raid_feature in files:
                raidloc = os.path.join(root, raid_feature)
                logging.debug(f"Found Raid.exe installed at {raidloc}")
                self.steps["Raid_path"]="True"
                return raidloc
        self.steps["Raid_path"]="False"
        logging.error("Raid.exe was not found.")
        sys.exit(1)
    
    def get_asset_path(self):
        # Start with the directory of the current script
        current_dir = os.path.dirname(os.path.abspath(__file__))
        while True:
            # Construct the path to the assets folder
            self.asset_path = os.path.join(current_dir, 'assets')

            # Check if the assets path exists
            if os.path.exists(self.asset_path):
                self.steps["Asset_path"]="True"
                return self.asset_path

            # Move up one directory level
            new_dir = os.path.dirname(current_dir)
            if new_dir == current_dir:
                # We are at the root directory and didn't find the assets folder
                return None
            assets_second_path=os.path.join(new_dir, 'assets')
            if os.path.exists(assets_second_path):
                self.steps["Asset_path"]="True"
                return assets_second_path
            self.steps["Asset_path"]="False"
            if self.folders_for_exe() ==False:
                logging.error("Could not find the assets folder. This folder contains all of the images needed for this program to use. It must be in the same folder as this program.")
                sys.exit(1)

    def config_file(self):
        pass

    def open_raid(self):
        subprocess.Popen(
            [
                os.path.join(os.getenv("LOCALAPPDATA"), "PlariumPlay\PlariumPlay.exe"),
                "--args",
                "-gameid=101",
                "-tray-start",
            ]
        )
        self.wait_for_game_window(title="Raid: Shadow Legends", timeout=100)  # Example title and timeout

    def wait_for_game_window(self, title, timeout):
        start_time = time.time()
        while time.time() - start_time < timeout:
            print("opening raid")
            if pyautogui.getWindowsWithTitle(title):
                logging.debug("Game window found, game should be loading in now.")
                self.steps["Open_raid"]="True"
                self.initiate_raid(True)
                return
            time.sleep(5)  # Wait for 5 seconds before checking again
        self.steps["Open_raid"]="False"
        logging.error("Raid took too long to open, game window not found.")
        sys.exit(1)
    
    def delete_popup(self):
        while (
            pyautogui.locateOnScreen(
                self.asset_path + "\\exitAdd.png",
                confidence=0.8,
            )
            != None
        ):
            adx, ady = pyautogui.locateCenterOnScreen(
                self.asset_path + "\\exitAdd.png",
                confidence=0.8,
            )
            pyautogui.click(adx, ady)
            time.sleep(1)

    
    def back_to_bastion(self):
        while (
            pyautogui.locateOnScreen(
                self.asset_path + "\\goBack.png",
                confidence=0.8,
            )
            != None
        ):
            bastionx, bastiony = pyautogui.locateCenterOnScreen(
                self.asset_path + "\\goBack.png",
                confidence=0.8,
            )
            pyautogui.click(bastionx, bastiony)
            time.sleep(2)

    def get_screen_info(self):
        for m in get_monitors():
            self.width = m.width
            self.height = m.height
            main = m.is_primary
            if self.width != 1920 or self.height != 1080:
                tkinter.messagebox.showerror(
                        "Warning",
                        "Your Screen pixel is not 1920 by 1080. This may cause issues",
                    )
            if main == True:
                center_width = int((self.width / 2) - 450)
                center_height = int((self.height / 2) - 300)
                return (center_width, center_height)
            
    def window_sizing_centering(self):
        center = self.get_screen_info()
        try:
            win = pygetwindow.getWindowsWithTitle("Raid: Shadow Legends")[0]
            if win:
                # Minimize and then maximize the window
                win.minimize()
                win.restore()
            else:
                print("No window found with the title 'Raid: Shadow Legends'")
            win.size = (900, 600)
            win.moveTo(center[0], center[1])       
        except:
            time.sleep(20)
            win = pygetwindow.getWindowsWithTitle("Raid: Shadow Legends")[0]
            win.size = (900, 600)
            win.moveTo(center[0], center[1])

    def initiate_raid(self,not_open):
        self.window_sizing_centering()
        if not_open:
            while (
                pyautogui.locateOnScreen(
                    self.asset_path + "\\exitAdd.png",
                    confidence=0.8,
                )
                == None
            ):
                pass
        self.back_to_bastion()
        self.delete_popup()
        self.steps["Initiate_raid"]="True"
        # os.system("taskkill /f /im PlariumPlay.exe")

    def daily_summon_three(self):
            while (
                    pyautogui.locateOnScreen(
                        self.asset_path + "\\portal.png",
                        confidence=0.8,
                    )
                    != None
                ):
                    battlex, battley = pyautogui.locateCenterOnScreen(
                        self.asset_path + "\\portal.png",
                        confidence=0.9,
                    )
                    pyautogui.click(battlex, battley)
                    time.sleep(2)
            if (
                    pyautogui.locateOnScreen(
                        self.asset_path + "\\dailyAS.png",
                        confidence=0.8,
                    )
                    != None
                ):
                    battlex, battley = pyautogui.locateCenterOnScreen(
                        self.asset_path + "\\dailyAS.png",
                        confidence=0.9,
                    )
                    self.summoned_champs=0
                    pyautogui.click(battlex, battley)
                    time.sleep(2)
                    if (
                        pyautogui.locateOnScreen(
                            self.asset_path + "\\summonTen.png",
                            confidence=0.8,
                        )
                        != None
                    ):
                        battlex, battley = pyautogui.locateCenterOnScreen(
                            self.asset_path + "\\summonTen.png",
                            confidence=0.9,
                        )
                        pyautogui.click(battlex, battley)
                        self.summoned_champs+=1
                        print(10, "summoned")
                        time.sleep(10)
                        for i in range(0,9):
                            if (
                            pyautogui.locateOnScreen(
                                self.asset_path + "\\summonTenMore.png",
                                confidence=0.8,
                            )
                            != None
                        ):
                                battlex, battley = pyautogui.locateCenterOnScreen(
                                self.asset_path + "\\summonTenMore.png",
                                confidence=0.9,
                            )
                            pyautogui.click(battlex, battley)
                            self.summoned_champs+=1
                            time.sleep(10)
                            if i != 0:
                                print(i*10+10, "summoned")
                            else:
                                print(20, "summoned")
            self.steps["Daily_summon"]="Accessed"
            self.delete_popup()
            self.back_to_bastion()
            self.delete_popup()

    def daily_tavern_upgrade(self):
        if (
            pyautogui.locateOnScreen(
                self.asset_path + "\\tav.png",
                confidence=0.8,
            )
            != None
        ):
            battlex, battley = pyautogui.locateCenterOnScreen(
                self.asset_path + "\\tav.png",
                confidence=0.9,
            )
            pyautogui.click(battlex, battley)
            time.sleep(2)
        if (
            pyautogui.locateOnScreen(
                self.asset_path + "\\tavern_descending.png",
                confidence=0.8,
            )
            != None
        ):
            battlex, battley = pyautogui.locateCenterOnScreen(
                self.asset_path + "\\tavern_descending.png",
                confidence=0.9,
            )
            pyautogui.click(battlex, battley)
            time.sleep(2)
            for j in range(0,8):
                time.sleep(1)
                print(j+1," champ")
                pyautogui.click(1101,330)
                time.sleep(1)
                pyautogui.click(560,642)#390
                time.sleep(1)
                for i in range(0,2):
                    for x in range(560, 700, 60):
                        for y in range(570, 750, 90):
                            pyautogui.click(x, y)
                            time.sleep(1)
                            if (
                                pyautogui.locateOnScreen(
                                    self.asset_path + "\\sacrifice1.png",
                                    confidence=0.8,
                                )
                                != None
                            ):
                                battlex, battley = pyautogui.locateCenterOnScreen(
                                    self.asset_path + "\\sacrifice1.png",
                                    confidence=0.9,
                                )
                                pyautogui.click(battlex, battley)
                                time.sleep(2)
                                    
                        time.sleep(1)
                    time.sleep(3)
                    if (
                        pyautogui.locateOnScreen(
                            self.asset_path + "\\tavernUpgrade.png",
                            confidence=0.8,
                        )
                        != None
                    ):
                        battlex, battley = pyautogui.locateCenterOnScreen(
                            self.asset_path + "\\tavernUpgrade.png",
                            confidence=0.9,
                        )
                        pyautogui.click(battlex, battley)
                        time.sleep(2)
                        pyautogui.click(battlex, battley)
                        pyautogui.click(battlex, battley)
                        if i != 0:
                            print(i*6+6, "sifted")
                            
                        else:
                            print(6, "sifted")
                        time.sleep(3)
                    time.sleep(2)
                    if (
                        pyautogui.locateOnScreen(
                            self.asset_path + "\\sacrifice.png",
                            confidence=0.8,
                        )
                        != None
                    ):
                        battlex, battley = pyautogui.locateCenterOnScreen(
                            self.asset_path + "\\sacrifice.png",
                            confidence=0.9,
                        )
                        pyautogui.click(battlex, battley)
                        time.sleep(2)
                        
        self.steps["Tavern_upgrades"]="True"
        self.delete_popup()
        self.back_to_bastion()

daily=Daily()
daily.daily_summon_three()
daily.daily_tavern_upgrade()
import pyautogui

# pyautogui.displayMousePosition()