; =============================================================================
; 课程回放下载器 · Windows 安装包（Inno Setup 6）
;
; 正常打包：python tools\build_installer.py
;   它会生成一个只含 #define 的包装脚本（tmp\installer\build.iss）再 #include
;   本文件，因此路径永远是绝对路径，不写死盘符，clone 下来就能重打。
;
; 手工编译：先把程序文件放进 tmp\installer-stage（含 python\python.exe），
;   然后 ISCC.exe installer\app.iss
;   或者用 /D 覆盖下面任一默认值，例如 /DOutputDir=D:\out
;
; 注意：本文件是 UTF-8 **带 BOM**，中文串靠它才不会变成乱码，别存成无 BOM。
; =============================================================================

#ifndef MyAppName
  #define MyAppName "课程回放下载器"
#endif
#ifndef MyAppPublisher
  #define MyAppPublisher "yangt16"
#endif
#ifndef MyAppURL
  #define MyAppURL "https://github.com/yangt16/BJTU-tronclass-downloader"
#endif
#ifndef MyAppVersion
  #define MyAppVersion "4.3"
#endif
#ifndef MyAppFullVersion
  #define MyAppFullVersion "4.3.0.0"
#endif
#ifndef StageDir
  #define StageDir "..\tmp\installer-stage"
#endif
#ifndef OutputDir
  #define OutputDir "..\release"
#endif
#ifndef SetupIcon
  #define SetupIcon "app.ico"
#endif

[Setup]
AppId={{8C3A6F2E-5D1B-4B7A-9F60-7C2D4E1A9B33}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\TronClassDownloader
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={#OutputDir}
OutputBaseFilename=课程回放下载器-安装包
SetupIconFile={#SetupIcon}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\1-开始下载.cmd
ArchitecturesAllowed=x64compatible
ShowLanguageDialog=no
VersionInfoDescription={#MyAppName} 安装程序
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppFullVersion}
VersionInfoCompany=yangt16

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务:"

[Files]
Source: "{#StageDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\1-开始下载.cmd"; WorkingDir: "{app}"; IconFilename: "{sys}\cmd.exe"
Name: "{group}\按课程设置规则"; Filename: "{app}\2-清单规则.cmd"; WorkingDir: "{app}"; IconFilename: "{sys}\cmd.exe"
Name: "{group}\检查更新"; Filename: "{app}\3-更新版本.cmd"; WorkingDir: "{app}"; IconFilename: "{sys}\cmd.exe"
Name: "{group}\书签安装说明"; Filename: "{app}\dist\install.html"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\1-开始下载.cmd"; WorkingDir: "{app}"; IconFilename: "{sys}\cmd.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\dist\install.html"; Description: "查看书签安装说明（抓清单用）"; Flags: shellexec postinstall skipifsilent unchecked

[UninstallDelete]
Type: filesandordirs; Name: "{app}\tmp"
