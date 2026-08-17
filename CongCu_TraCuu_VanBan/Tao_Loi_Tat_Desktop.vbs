' Chay 1 LAN de tao loi tat ngoai Desktop, tro toi cong cu Tra cuu Van ban.
Dim fso, scriptDir, WshShell, desktopPath, shortcut
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
Set WshShell = CreateObject("WScript.Shell")
desktopPath = WshShell.SpecialFolders("Desktop")

Set shortcut = WshShell.CreateShortcut(desktopPath & "\Tra cuu Van ban (RAG).lnk")
shortcut.TargetPath = scriptDir & "\start_app_nen.vbs"
shortcut.WorkingDirectory = scriptDir
shortcut.WindowStyle = 1
shortcut.IconLocation = "%SystemRoot%\System32\shell32.dll,23"
shortcut.Description = "Cong cu tra cuu van ban - Hybrid Search + Knowledge Graph (Buoi 14)"
shortcut.Save

MsgBox "Da tao loi tat tren Desktop: 'Tra cuu Van ban (RAG)'." & vbCrLf & vbCrLf & _
       "Tu lan sau, bam doi vao bieu tuong do de mo cong cu (chay nen, tu mo trinh duyet).", _
       64, "Hoan tat"
