import tkinter
from tkinter import scrolledtext
from tkinter import ttk
import logging
import threading
import os
import configparser
from core.daily import Daily
from core.error_handler import log_error_with_context, validate_config_file, ConfigurationError

logger = logging.getLogger(__name__)

class GUI:
    def __init__(self, master):
        try:
            self.master = master
            self.config = configparser.ConfigParser()
            
            # Validate config file before reading
            if not validate_config_file('PARconfig.ini'):
                logger.warning("PARconfig.ini not found or invalid, using defaults")
                self.create_default_config()
            else:
                self.config.read('PARconfig.ini')
            
            # Create the Daily instance after config is loaded
            self.app = Daily(master)
            
            # Initialize GUI elements
            self.setup_gui()
            
            # Start threads after GUI is set up
            self.timer_thread()
            self.daily_thread = threading.Thread(target=self.app.run)
            self.daily_thread.start()
            self.daily_thread.name = "PAR"
            
            logger.info("GUI initialized successfully.")
        except Exception as e:
            log_error_with_context(e, "GUI initialization")
            raise

    def create_default_config(self):
        """Create a default configuration if none exists."""
        try:
            self.config['Settings'] = {
                'automated_mode': 'False',
                'rewards': 'True',
                'daily_ten_classic_arena': 'True',
                'clanboss': 'True',
                'faction_wars': 'True',
                'iron_twins': 'True',
                'doom_tower': 'True'
            }
            
            with open('PARconfig.ini', 'w') as configfile:
                self.config.write(configfile)
            
            logger.info("Created default configuration file")
        except Exception as e:
            log_error_with_context(e, "creating default config")

    def setup_gui(self):
        try:
            self.master.title("PyAutoRaid Task Selector")
            
            # Safely get config items with defaults
            try:
                tasks_config = dict(self.config.items("Settings"))
                settings_config = dict(self.config.items("Settings"))
            except configparser.NoSectionError:
                logger.warning("Settings section not found in config, using defaults")
                tasks_config = {}
                settings_config = {}

            # Creating a ttk Frame which will contain all other widgets
            main_frame = ttk.Frame(self.master)
            main_frame.pack(fill=tkinter.BOTH, expand=True)
            config_keys = ['rewards', 'daily_ten_classic_arena', 'clanboss', 'faction_wars', 'iron_twins', 'doom_tower']
            
            # Automated Mode Checkbox
            self.automated_mode = tkinter.IntVar()
            if settings_config.get("automated_mode") == 'True':
                self.automated_mode.set(1)
            self.chk_automated_mode = ttk.Checkbutton(main_frame, text="Automated Mode", variable=self.automated_mode)
            self.chk_automated_mode.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="W")

            # Separator
            self.separator = ttk.Separator(main_frame, orient='horizontal')
            self.separator.grid(row=1, column=0, padx=10, pady=5, sticky="EW")

            def checkbox_callback(var_name, index, mode, config_key, var):
                try:
                    updated_value = str(bool(var.get()))
                    if 'Settings' not in self.config:
                        self.config['Settings'] = {}
                    self.config['Settings'][config_key] = updated_value
                    with open('PARconfig.ini', 'w') as configfile:
                        self.config.write(configfile)
                    logger.info(f"Checkbox {config_key} updated to {updated_value}")
                except Exception as e:
                    log_error_with_context(e, "checkbox callback", config_key=config_key)

            # Other Checkboxes
            self.checkbox_texts = [
                "Collect Rewards", "Ten Classic Arena Battles", "Clan Boss", "Faction Wars", "Iron Twins", "Doom Tower"
            ]
            self.checkboxes = []
            self.vars = []

            for i, text in enumerate(config_keys, start=2):
                try:
                    guiname = self.checkbox_texts[i - 2]
                    var = tkinter.IntVar()
                    config_key = config_keys[i - 2]
                    if tasks_config.get(config_key, 'False') == 'True':
                        var.set(1)
                    var.trace_add('write', lambda var_name, index, mode, var=var, config_key=config_key: checkbox_callback(var_name, index, mode, config_key, var))
                    chk = ttk.Checkbutton(main_frame, text=guiname, variable=var)
                    chk.grid(row=i, column=0, padx=10, pady=(0, 5), sticky="W")
                    self.checkboxes.append(chk)
                    self.vars.append(var)
                except Exception as e:
                    log_error_with_context(e, "creating checkbox", checkbox_index=i, config_key=config_keys[i-2])

            # Buttons
            try:
                self.btn_manual_run = ttk.Button(main_frame, text="Manual Run", command=self.manual_run)
                self.btn_manual_run.grid(row=len(self.checkbox_texts) + 3, column=0, padx=10, pady=(5, 5), sticky="W")

                self.btn_quit_all = ttk.Button(main_frame, text="Quit All", command=self.quit_all)
                self.btn_quit_all.grid(row=len(self.checkbox_texts) + 3, column=1, padx=10, pady=(5, 5), sticky="E")
            except Exception as e:
                log_error_with_context(e, "creating buttons")

            # Separator above the log box
            self.separator2 = ttk.Separator(main_frame, orient='horizontal')
            self.separator2.grid(row=len(self.checkbox_texts) + 4, column=0, columnspan=2, padx=10, pady=5, sticky="EW")

            # Log Text Box
            try:
                self.log_text = scrolledtext.ScrolledText(main_frame, wrap=tkinter.WORD, height=10, state="disabled")
                self.log_text.grid(row=len(self.checkbox_texts) + 5, column=0, columnspan=2, padx=10, pady=(5, 10), sticky="EW")

                # Redirect logs to the text box
                self.redirect_logs()
            except Exception as e:
                log_error_with_context(e, "setting up log text box")
                
        except Exception as e:
            log_error_with_context(e, "GUI setup")
            raise
            
        except Exception as e:
            logger.error(f"Error setting up GUI: {e}")
            raise

    def manual_run(self):
        """Handle manual run button click"""
        try:
            logger.info("Manual run button clicked.")
            if hasattr(self, 'app') and self.app:
                self.app.trigger_manual_run(True)
        except Exception as e:
            log_error_with_context(e, "manual run")

    def quit_all(self, timer=False):
        """Safely quit all processes"""
        try:
            logger.info("Quitting all processes.")
            if timer:
                os.system("taskkill /f /im Raid.exe")
            os.system("taskkill /f /im DailyQuests.exe")
            os.system("taskkill /f /im PyAutoRaid.exe")
            os.system("taskkill /f /im python.exe")
            os.system("taskkill /f /im DailyQuests.py")
            os.system("taskkill /f /im PlariumPlay.exe")
        except Exception as e:
            log_error_with_context(e, "quit all")

    def timer_thread(self):
        """Start timer thread for auto-quit functionality"""
        try:
            timeout = 1800
            # Create a timer that will call quit_all() after the timeout
            self.timer = threading.Timer(timeout, lambda: self.quit_all(timer=True))
            self.timer.name = "timer_thread"
            self.timer.daemon = True
            # Start the timer
            self.timer.start()
            logger.info("Timer thread started.")
        except Exception as e:
            log_error_with_context(e, "timer thread")
            
    def redirect_logs(self):
        """Redirect log output to the text box."""
        class TextHandler(logging.Handler):
            def __init__(self, widget):
                super().__init__()
                self.widget = widget

            def emit(self, record):
                try:
                    msg = self.format(record)
                    self.widget.config(state="normal")
                    self.widget.insert(tkinter.END, msg + "\n")
                    self.widget.config(state="disabled")
                    self.widget.see(tkinter.END)
                except Exception as e:
                    log_error_with_context(e, "TextHandler emit")

        try:
            handler = TextHandler(self.log_text)
            handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
            logger.addHandler(handler)
        except Exception as e:
            log_error_with_context(e, "setting up log redirection") 