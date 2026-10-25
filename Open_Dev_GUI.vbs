Option Explicit
Dim shell, fs, root, python, command
Set shell = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
root = fs.GetParentFolderName(WScript.ScriptFullName)
python = "D:\XianLab\envs\LangChainEnv\Scripts\pythonw.exe"
If Not fs.FileExists(python) Then
  MsgBox "Registered LangChainEnv interpreter unavailable. No service was started.", 16, "AbqJobPilot Dev"
  WScript.Quit 2
End If
shell.CurrentDirectory = root
command = Chr(34) & python & Chr(34) & " -B " & Chr(34) & fs.BuildPath(root, "run_gui.py") & Chr(34)
shell.Run command, 0, False
