[Setup]
AppName=PARinstaller
AppVersion=1.0
DefaultDirName={autopf}\PyAutoRaid
DefaultGroupName=PyAutoRaid
OutputDir=.
OutputBaseFilename=PARinstaller
Compression=lzma2
SolidCompression=yes

[Files]
Source: "dist\PyAutoRaid.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\DailyQuests.exe"; DestDir: "{app}"; Flags: ignoreversion

[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon for PyAutoRaid"; GroupDescription: "Additional icons:"; Flags: unchecked
Name: "desktopicon2"; Description: "Create a desktop icon for DailyQuests"; GroupDescription: "Additional icons:"; Flags: unchecked

[Icons]
Name: "{group}\PyAutoRaid"; Filename: "{app}\PyAutoRaid.exe"
Name: "{group}\DailyQuests"; Filename: "{app}\DailyQuests.exe"
Name: "{commondesktop}\PyAutoRaid"; Filename: "{app}\PyAutoRaid.exe"; Tasks: desktopicon
Name: "{commondesktop}\DailyQuests"; Filename: "{app}\DailyQuests.exe"; Tasks: desktopicon2
