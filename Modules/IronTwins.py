import os
import time
import pyautogui
import logging

logging.basicConfig(
    filename='PyAutoRaid.log',
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filemode='w',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

class Command:
    def execute(self):
        pass

class IronTwinsCommand(Command):
    def __init__(self, app):
        self.app = app        

    def execute(self):
        try:
            logger.info("Starting Iron Twinstask.")

            # Define image paths
            battle_btn_image = os.path.join(self.app.asset_path, "battleBTN.png")
            dungeons_image = os.path.join(self.app.asset_path, "dungeons.png")
            iron_twins_image = os.path.join(self.app.asset_path, "ironTwinsDungeon.png")
            iron_twins_stage_15_image = os.path.join(self.app.asset_path, "ironTwinsStage15.png")
            multi_battle_image = os.path.join(self.app.asset_path, "factionWarsMultiBattle.png")
            start_stage_multi_battle_image = os.path.join(self.app.asset_path, "startMultiBattle.png")
            in_battle_image = os.path.join(self.app.asset_path, "inBattle.png")
            in_mutli_battle_image = os.path.join(self.app.asset_path, "turnOffMultiBattle.png")
            mutli_battle_complete_image = os.path.join(self.app.asset_path, "mutliBattleComplete.png")
            
            logger.info("Attempting to close any existing pop-ups.")
            self.app.delete_popup()

            # Navigate to battle screen
            self.click_image(battle_btn_image, "Battle button")

            # Navigate to Dungeons
            self.click_image(dungeons_image, "Dungeons button")

            # Open Iron Twins dungeon
            self.click_image(iron_twins_image, "Iron Twins dungeon button")

            # Select Stage 15
            while pyautogui.locateOnScreen(iron_twins_stage_15_image, confidence=0.8):
                buttons = list(pyautogui.locateAllOnScreen(iron_twins_stage_15_image, confidence=0.8))
                if buttons:
                    # Find the button with the largest y-coordinate
                    bottom_button = max(buttons, key=lambda b: b.top)
                    bottom_x, bottom_y = pyautogui.center(bottom_button)
                    
                    # Click the battle button
                    pyautogui.click(bottom_x, bottom_y)
                    logger.info(f"Clicked on the highest stage Battle button at coordinates: ({bottom_x}, {bottom_y}).")
                    time.sleep(1)

                    # Check if the battle button is still visible
                    if pyautogui.locateOnScreen(iron_twins_stage_15_image, confidence=0.8):
                        logger.warning("Battle button is still visible. Pressing escape to go back.")
                        pyautogui.press("esc")
                        time.sleep(1)
                    break
                else:
                    logger.warning("No Battle button found.")
                    break
            # Start Multi Battle
            while pyautogui.locateOnScreen(multi_battle_image, confidence=0.8):
                logger.info("Multi-battle option detected. Starting multi-battle.")
                x, y = pyautogui.locateCenterOnScreen(multi_battle_image, confidence=0.8)
                pyautogui.click(x, y)
                time.sleep(1)
                x, y = pyautogui.locateCenterOnScreen(start_stage_multi_battle_image, confidence=0.8)
                pyautogui.click(x, y)                
                time.sleep(1)

            
             # Wait for battle to complete
            while pyautogui.locateOnScreen(in_battle_image, confidence=0.8) or pyautogui.locateOnScreen(in_mutli_battle_image, confidence=0.8):
                logger.info("Waiting for the battle results.")
                time.sleep(10)
                
            while pyautogui.locateOnScreen(mutli_battle_complete_image, confidence=0.8):
                self.app.back_to_bastion()

            
            
            self.app.back_to_bastion()
            logger.info("Iron Twins task completed successfully.")
        except Exception as e:
            logger.error(f"Error in IronTwinsCommand: {e}", exc_info=True)
            self.app.back_to_bastion()

    def click_image(self, image_path, description):
        """Helper to click an image on screen."""
        while pyautogui.locateOnScreen(image_path, confidence=0.8):
            x, y = pyautogui.locateCenterOnScreen(image_path, confidence=0.8)
            pyautogui.click(x, y)
            logger.info(f"Clicked on {description} at coordinates ({x}, {y}).")
            time.sleep(2)