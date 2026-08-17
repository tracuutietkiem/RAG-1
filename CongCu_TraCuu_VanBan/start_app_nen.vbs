' Chay Tro ly Tra cuu Van ban o che do NEN (khong hien cua so den)
' Log loi/tien trinh nam trong thu muc logs\
Dim fso, scriptDir, shell
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = scriptDir
shell.Run """" & scriptDir & "\start_app.bat""", 0, False
