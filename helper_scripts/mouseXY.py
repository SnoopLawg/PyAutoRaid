import pygetwindow as gw
import pyautogui
import time

print("Move your mouse to see the coordinates relative to the active window. Press Ctrl+C to stop.")

try:
    while True:
        # Get the active window
        active_window = gw.getActiveWindow()
        if active_window:
            # Get the top-left corner of the active window
            window_left = active_window.left
            window_top = active_window.top

            # Get the current mouse position
            x, y = pyautogui.position()

            # Calculate coordinates relative to the active window
            relative_x = x - window_left
            relative_y = y - window_top

            print(
                f"Mouse position (screen): x={x}, y={y} | "
                f"(relative): x={relative_x}, y={relative_y} | "
                f"Window: {active_window.title}",
                end="\r",
                flush=True,
            )
            time.sleep(0.1)
        else:
            print("No active window detected.", end="\r", flush=True)
except KeyboardInterrupt:
    print("\nExiting...")
