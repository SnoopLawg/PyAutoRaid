from tkinter import *
from ttkthemes import ThemedTk
from gui.gui import GUI
import logging
import sys
from core.error_handler import log_error_with_context

# Configure logging
logging.basicConfig(
    filename='PyAutoRaid.log',
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filemode='w',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

def main():
    """Main application entry point with error handling."""
    try:
        root = ThemedTk(theme="equilux")
        root.geometry("500x560+10+240")

        my_gui = GUI(root)
        
        def on_closing():
            try:
                if hasattr(my_gui, 'timer') and my_gui.timer.is_alive():
                    my_gui.timer.cancel()
                    logger.info("Timer cancelled.")
                if hasattr(my_gui, 'daily_thread') and my_gui.daily_thread.is_alive():
                    my_gui.daily_thread.join(timeout=1)
                    logger.info("Daily thread joined.")
                root.destroy()
                logger.info("Application closed.")
            except Exception as e:
                log_error_with_context(e, "application closing")
                try:
                    root.destroy()
                except:
                    pass
        
        root.protocol("WM_DELETE_WINDOW", on_closing)  # To ensure clean exit
        
        logger.info("Application started successfully.")
        root.mainloop()
        
    except Exception as e:
        log_error_with_context(e, "main application startup")
        sys.exit(1)

if __name__ == "__main__":
    main() 