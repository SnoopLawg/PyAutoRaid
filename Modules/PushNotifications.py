import http.client, urllib


def push(state, completed="", Total_time=""):
    conn = http.client.HTTPSConnection("api.pushover.net:443")
    try:
        Total_time_minutes = round(int(Total_time) / 60, 1)
    except:
        Total_time_minutes = 0
    if state:
        message = f"{state} Running PAR"
        if completed != "":
            completed_str = "\n".join(completed)
            message = f"{state} Running PAR, {completed_str}"
            if Total_time_minutes != 0:
                message = f"{state} Running PAR, {completed_str}, It took {Total_time_minutes} Minutes to complete"
    try:
        import configparser

        # Read the token value from the configuration file
        config = configparser.ConfigParser()
        config.read("config.ini")
        token = config["Settings"]["Token"]
        user = config["Settings"]["user"]
        conn.request(
            "POST",
            "/1/messages.json",
            urllib.parse.urlencode(
                {
                    "token": token,
                    "user": user,
                    "message": message,
                }
            ),
            {"Content-type": "application/x-www-form-urlencoded"},
        )
        conn.getresponse()
    except:
        print("Push notifications not set up")


if __name__ == "__main__":
    push()
