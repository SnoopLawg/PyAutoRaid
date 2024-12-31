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

class FactionWarsCommand(Command):
    def __init__(self, app):
        self.app = app        

    def execute(self):
        try:
            logger.info("Starting Faction Wars task.")
            faction_positions_right = [
                {"name": "Dark Elf", "x": 560, "y": 650},
                {"name": "High Elf", "x": 680, "y": 415},
                {"name": "Sacred Order", "x": 760, "y": 520},
                {"name": "Barbarian", "x": 870, "y": 660},
                {"name": "Banner Lords", "x": 960, "y": 430},
                {"name": "Dwarves", "x": 1080, "y": 530},
                {"name": "Shadowkin", "x": 1250, "y": 650},
                {"name": "Sylvan Watchers", "x": 1350, "y": 510},
            ]
            faction_position_two = [
                {"name": "Lizardmen", "x": 670, "y": 530},
                {"name": "Knight Revenant", "x": 800, "y": 660},
                {"name": "Skinwalkers", "x": 800, "y": 400},
                {"name": "Undead Hordes", "x": 950, "y": 520},
                {"name": "Demonspawn", "x": 1060, "y": 420},
                {"name": "Ogryn Tribes", "x": 1180, "y": 650},
                {"name": "Orcs", "x": 1260, "y": 530},
            ]

            # Define image paths
            battle_btn_image = os.path.join(self.app.asset_path, "battleBTN.png")
            faction_wars_image = os.path.join(self.app.asset_path, "factionWars.png")
            stage_open_image = os.path.join(self.app.asset_path, "stageStart.png")
            faction_wars_multi_battle_image = os.path.join(self.app.asset_path, "factionWarsMultiBattle.png")
            start_stage_multi_battle_image = os.path.join(self.app.asset_path, "startMultiBattle.png")
            mutli_battle_complete_image = os.path.join(self.app.asset_path, "mutliBattleComplete.png")
            in_battle_image = os.path.join(self.app.asset_path, "inBattle.png")
            in_mutli_battle_image = os.path.join(self.app.asset_path, "turnOffMultiBattle.png")
            
            logger.info("Attempting to close any existing pop-ups.")
            self.app.delete_popup()

            # Go to battle screen
            while pyautogui.locateOnScreen(battle_btn_image, confidence=0.8):
                self.click_image(battle_btn_image, "Battle button")
            
            # Click on Faction Wars
            while pyautogui.locateOnScreen(faction_wars_image, confidence=0.8):
                self.click_image(faction_wars_image, "Faction Wars option")
                
            # Process factions on the right
            logger.info("Swiping all the way to the right.")
            pyautogui.moveTo(960, 540)
            pyautogui.dragRel(-600, 0, duration=0.5)
            time.sleep(1)
            
            for position in faction_positions_right:
                x, y, name = position["x"], position["y"], position["name"]
                logger.debug(f"Attempting to click on faction {name} at ({x}, {y}).")
                pyautogui.click(x, y)
                time.sleep(1)
                self.start_stage(
                    stage_open_image,
                    faction_wars_multi_battle_image,
                    start_stage_multi_battle_image,
                    in_battle_image,
                    in_mutli_battle_image,
                    mutli_battle_complete_image,
                )
            
            # Swipe all the way to the left and process remaining factions
            logger.info("Swiping all the way to the left.")
            pyautogui.moveTo(960, 540)
            pyautogui.dragRel(1600, 0, duration=0.5)
            time.sleep(1)

            for position in faction_position_two:
                x, y, name = position["x"], position["y"], position["name"]
                logger.debug(f"Attempting to click on faction {name} at ({x}, {y}).")
                pyautogui.click(x, y)
                time.sleep(1)
                self.start_stage(
                    stage_open_image,
                    faction_wars_multi_battle_image,
                    start_stage_multi_battle_image,
                    in_battle_image,
                    in_mutli_battle_image,
                    mutli_battle_complete_image,
                )
            
            self.app.back_to_bastion()
            logger.info("Faction Wars task completed successfully.")
        except Exception as e:
            logger.error(f"Error in FactionWarsCommand: {e}", exc_info=True)
            self.app.back_to_bastion()

    def click_image(self, image_path, description):
        """Helper to click an image on screen."""
        while pyautogui.locateOnScreen(image_path, confidence=0.8):
            x, y = pyautogui.locateCenterOnScreen(image_path, confidence=0.8)
            pyautogui.click(x, y)
            logger.info(f"Clicked on {description} at coordinates ({x}, {y}).")
            time.sleep(2)

    def start_stage(
        self,
        stage_open_image,
        faction_wars_multi_battle_image,
        start_stage_multi_battle_image,
        in_battle_image,
        in_mutli_battle_image,
        mutli_battle_complete_image,
    ):
        """Logic to start a stage."""
        while pyautogui.locateOnScreen(stage_open_image, confidence=0.8):
            logger.info("Stage start button detected. Preparing to select stage.")
            buttons = list(pyautogui.locateAllOnScreen(stage_open_image, confidence=0.8))
            if buttons:
                # Find the button with the largest y-coordinate
                bottom_button = max(buttons, key=lambda b: b.top)
                bottom_x, bottom_y = pyautogui.center(bottom_button)
                
                # Click the battle button
                pyautogui.click(bottom_x, bottom_y)
                logger.info(f"Clicked on the highest stage Battle button at coordinates: ({bottom_x}, {bottom_y}).")
                time.sleep(1)

                # Check if the battle button is still visible
                if pyautogui.locateOnScreen(stage_open_image, confidence=0.8):
                    logger.warning("Battle button is still visible. Pressing escape to go back.")
                    pyautogui.press("esc")
                    time.sleep(1)
                break
            else:
                logger.warning("No Battle button found.")
                break

        # Handle multi-battle
        while pyautogui.locateOnScreen(faction_wars_multi_battle_image, confidence=0.8):
            logger.info("Multi-battle option detected. Starting multi-battle.")
            x, y = pyautogui.locateCenterOnScreen(faction_wars_multi_battle_image, confidence=0.8)
            pyautogui.click(x, y)
            time.sleep(1)
            x, y = pyautogui.locateCenterOnScreen(start_stage_multi_battle_image, confidence=0.8)
            pyautogui.click(x, y)
            time.sleep(1)
            
        # Wait for battle to complete
        while pyautogui.locateOnScreen(in_battle_image, confidence=0.8) or pyautogui.locateOnScreen(in_mutli_battle_image, confidence=0.8):
            logger.info("Waiting for the battle results.")
            time.sleep(10)

        # Exit multi-battle and return to faction selection
        while pyautogui.locateOnScreen(mutli_battle_complete_image, confidence=0.8):
            pyautogui.press("esc")
            time.sleep(1)
            pyautogui.press("esc")
            time.sleep(1)
            pyautogui.press("esc")
            time.sleep(2)
            logger.info("Returning to faction selection.")