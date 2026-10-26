Option Explicit
Dim shell, fs, root, python, command, config, stream, code, argument
Set shell = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
root = fs.GetParentFolderName(WScript.ScriptFullName)
python = shell.Environment("PROCESS")("ABQJOBPILOT_PYTHON")
config = fs.BuildPath(root, "python-path.txt")
If python = "" And fs.FileExists(config) Then
  Set stream = fs.OpenTextFile(config, 1, False)
  If stream.AtEndOfStream Then
    stream.Close
    MsgBox "python-path.txt is empty. Configure one absolute python.exe path. No service was started.", 16, "AbqJobPilot"
    WScript.Quit 2
  End If
  python = Trim(stream.ReadLine)
  stream.Close
  If python = "" Then
    MsgBox "python-path.txt contains an empty path. Configure one absolute python.exe path. No service was started.", 16, "AbqJobPilot"
    WScript.Quit 2
  End If
End If
If python = "" Then
  python = fs.BuildPath(root, ".venv\Scripts\python.exe")
  If Not fs.FileExists(python) Then python = "D:\XianLab\envs\LangChainEnv\Scripts\python.exe"
End If
If InStr(python, Chr(34)) > 0 Or InStr(python, vbCr) > 0 Or InStr(python, vbLf) > 0 Then
  MsgBox "Invalid Python path. Use one absolute python.exe path without quotes.", 16, "AbqJobPilot"
  WScript.Quit 2
End If
If LCase(fs.GetFileName(python)) <> "python.exe" Or fs.GetAbsolutePathName(python) <> python Then
  MsgBox "Set ABQJOBPILOT_PYTHON or python-path.txt to an absolute python.exe path.", 16, "AbqJobPilot"
  WScript.Quit 2
End If
If Not fs.FileExists(python) Then
  MsgBox "Python unavailable. Configure ABQJOBPILOT_PYTHON, python-path.txt, or an application .venv. Requires 64-bit CPython 3.12 with Tk. No service was started.", 16, "AbqJobPilot"
  WScript.Quit 2
End If
shell.CurrentDirectory = root
argument = ""
If WScript.Arguments.Count = 1 Then
  If WScript.Arguments(0) = "--check" Then argument = " --check"
End If
command = Chr(34) & python & Chr(34) & " -I -B " & Chr(34) & fs.BuildPath(root, "launch_gui.py") & Chr(34) & argument
On Error Resume Next
code = shell.Run(command, 0, True)
If Err.Number <> 0 Then
  MsgBox "Could not launch Python. Check the configured path and access permissions.", 16, "AbqJobPilot"
  WScript.Quit 2
End If
On Error GoTo 0
If code <> 0 Then MsgBox "AbqJobPilot did not start (code " & code & "). Run the configured Python with launch_gui.py --check for diagnostics. No service is started by this launcher.", 16, "AbqJobPilot"
WScript.Quit code
