[Setup]
AppName=ArgusScanner
AppVersion=0.1.0
DefaultDirName={autopf}\ArgusScanner
DefaultGroupName=ArgusScanner
OutputDir=dist
OutputBaseFilename=ArgusScanner-Setup
UninstallDisplayIcon={app}\ArgusScanner.exe

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en escritorio"; GroupDescription: "Accesos directos:"
Name: "autorun"; Description: "Iniciar con Windows"; GroupDescription: "Opcional:"

[Files]
Source: "dist\ArgusScanner.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\ArgusScanner"; Filename: "{app}\ArgusScanner.exe"
Name: "{autodesktop}\ArgusScanner"; Filename: "{app}\ArgusScanner.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "ArgusScanner"; ValueData: """{app}\ArgusScanner.exe"""; Tasks: autorun
