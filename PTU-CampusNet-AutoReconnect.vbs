' PTU 校园网自动重连 - 双击启动

Set WshShell = CreateObject("Wscript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

' 尝试找到可用的 python，优先 pythonw（无黑窗）
pythonPath = ""
For Each exe In Array("pythonw", "python")
    If pythonPath = "" Then
        On Error Resume Next
        Err.Clear
        WshShell.Exec exe & " --version"
        If Err.Number = 0 Then pythonPath = exe
        On Error Goto 0
    End If
Next

If pythonPath = "" Then pythonPath = "pythonw"

WshShell.CurrentDirectory = scriptDir
WshShell.Run """" & pythonPath & """ """ & scriptDir & "\ui.py""", 0, False
