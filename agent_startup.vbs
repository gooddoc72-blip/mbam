' 마케팅연구소 웹 관제 에이전트 - 콘솔창 없이 백그라운드 실행
' (Windows 시작 시 자동 실행 / 설치 프로그램이 시작프로그램에 등록)
Set fso = CreateObject("Scripting.FileSystemObject")
appDir = fso.GetParentFolderName(WScript.ScriptFullName)
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = appDir
sh.Environment("PROCESS")("PYTHONPATH") = appDir
' 동봉 Python(설치형) 우선, 없으면 시스템 pythonw
pyw = appDir & "\runtime\python\pythonw.exe"
If Not fso.FileExists(pyw) Then
  If fso.FileExists(appDir & "\venv\Scripts\pythonw.exe") Then
    pyw = appDir & "\venv\Scripts\pythonw.exe"
  Else
    pyw = "pythonw.exe"
  End If
End If
' 0 = 창 숨김, False = 종료 대기 안 함
sh.Run """" & pyw & """ """ & appDir & "\agent.py""", 0, False
