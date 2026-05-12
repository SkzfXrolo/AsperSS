Name "ArgusScanner"
OutFile "dist\ArgusScanner-NSIS.exe"
InstallDir "$PROGRAMFILES\ArgusScanner"

Section "Install"
  SetOutPath "$INSTDIR"
  File "dist\ArgusScanner.exe"
  CreateShortCut "$DESKTOP\ArgusScanner.lnk" "$INSTDIR\ArgusScanner.exe"
SectionEnd

Section "Uninstall"
  Delete "$INSTDIR\ArgusScanner.exe"
  Delete "$DESKTOP\ArgusScanner.lnk"
  RMDir "$INSTDIR"
SectionEnd
