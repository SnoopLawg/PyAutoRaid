import os
import time
import pyautogui

class Command:
    def execute(self):
        pass

class DoomTowerCommand(Command):
    def __init__(self, app, logger):
        self.app = app        
        self.logger = logger

    def execute(self):
        try:
            self.logger.info("Starting Doom Tower task.")

            # Define image paths
            battle_btn_image = os.path.join(self.app.asset_path, "battleBTN.png")
            doom_tower_image = os.path.join(self.app.asset_path, "doomTower.png")
            doom_tower_next_stage = os.path.join(self.app.asset_path, "doomTowerNextStage.png")
            doom_tower_start_battle = os.path.join(self.app.asset_path, "doomTowerStartBattle.png")
            doom_tower_stages_screen = os.path.join(self.app.asset_path, "doomTowerScreen.png")
            in_battle_image = os.path.join(self.app.asset_path, "inBattle.png")
            in_mutli_battle_image = os.path.join(self.app.asset_path, "turnOffMultiBattle.png")
            mutli_battle_complete_image = os.path.join(self.app.asset_path, "mutliBattleComplete.png")
            
            self.logger.info("Attempting to close any existing pop-ups.")
            self.app.delete_popup()

            # Navigate to battle screen
            time.sleep(2)
            self.click_image(battle_btn_image, "Battle button")

            # Navigate to Doom Tower
            pyautogui.moveTo(960, 540)
            pyautogui.dragRel(-600, 0, duration=0.5)
            time.sleep(2)
            self.click_image(doom_tower_image, "Doom Tower button")
            time.sleep(2)

            # Loop through this to complete Auto Climb and then Tower - Or replay failed stages
            while pyautogui.locateOnScreen(doom_tower_next_stage, confidence=0.8):
                self.click_image(doom_tower_next_stage, "Doom Tower Next Stage")
                
                # If Wave stage Start Multi Battle
                x, y = pyautogui.locateCenterOnScreen(doom_tower_start_battle, confidence=0.8)
                pyautogui.click(x, y)
                self.logger.info(f"Clicked on Doom Tower Start Battle at coordinates ({x}, {y}).")
                time.sleep(2)
                
                if pyautogui.locateOnScreen(doom_tower_start_battle, confidence=0.8):
                    self.logger.info("Must not have enough keys. Doom Tower Comlete")
                    pyautogui.press("esc")
                    time.sleep(1)
                    pyautogui.press("esc")
                    time.sleep(1)
                    
                
                # Wait for battle to complete
                while pyautogui.locateOnScreen(in_battle_image, confidence=0.8) or pyautogui.locateOnScreen(in_mutli_battle_image, confidence=0.8):
                    self.logger.info("Waiting for the battle results.")
                    time.sleep(10)
                while pyautogui.locateOnScreen(mutli_battle_complete_image, confidence=0.8):
                    # Back to doom tower to check if the boss is ready or failed run
                    pyautogui.press("esc")
                    time.sleep(1)
                    pyautogui.press("esc")
                    time.sleep(1)

            # If Boss Stage Click Boss Right Hand Side
            if pyautogui.locateOnScreen(doom_tower_stages_screen, confidence=0.8):
                pyautogui.click(540, 1270)
                time.sleep(2)

            # Click on boss that is stage 120
            if pyautogui.locateOnScreen(doom_tower_stages_screen, confidence=0.8):
                pyautogui.click(950, 500)
                time.sleep(2)
                
            self.click_image(doom_tower_start_battle, "Doom Tower Start Battle")
            time.sleep(5)
            # Wait for battle to complete
            while pyautogui.locateOnScreen(in_battle_image, confidence=0.8):
                self.logger.info("Waiting for the battle results.")
                time.sleep(10)            
            
            self.app.back_to_bastion()
            self.logger.info("Faction Wars task completed successfully.")
        except Exception as e:
            self.logger.error(f"Error in IronTwinsCommand: {e}", exc_info=True)
            self.app.back_to_bastion()

    def click_image(self, imagePath, description):
        """Helper to click an image on screen."""
        while pyautogui.locateOnScreen(imagePath, confidence=0.8):
            x, y = pyautogui.locateCenterOnScreen(imagePath, confidence=0.8)
            pyautogui.click(x, y)
            self.logger.info(f"Clicked on {description} at coordinates ({x}, {y}).")
            time.sleep(2)
