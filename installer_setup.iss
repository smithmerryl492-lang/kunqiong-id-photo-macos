; 鲲穹AI证件照 - Inno Setup 安装脚本
; 版本: 1.0.0

#define MyAppName "鲲穹AI证件照"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "六角星科技"
#define MyAppExeName "鲲穹AI证件照.exe"
#define MyAppURL "https://www.example.com"

[Setup]
; 应用程序基本信息
AppId={{A1B2C3D4-E5F6-4A5B-8C9D-0E1F2A3B4C5D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
; 默认安装目录
DefaultDirName={autopf}\{#MyAppName}
; 开始菜单文件夹
DefaultGroupName={#MyAppName}
; 允许用户选择不创建开始菜单文件夹
AllowNoIcons=yes
; 许可协议文件 (可选)
;LicenseFile=LICENSE.txt
; 安装前显示的信息文件 (可选)
;InfoBeforeFile=README.txt
; 输出设置
OutputDir=installer_output
OutputBaseFilename=鲲穹AI证件照_Setup_v{#MyAppVersion}
; 安装程序图标
SetupIconFile=logo.ico
; 压缩设置
Compression=lzma2/ultra64
SolidCompression=yes
; Windows 版本要求
MinVersion=10.0
; 架构
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
; 权限要求
PrivilegesRequired=lowest
; 卸载显示图标
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "chinesesimplified"; MessagesFile: "ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "创建快速启动栏图标"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; 主程序
Source: "dist\鲲穹AI证件照\鲲穹AI证件照.exe"; DestDir: "{app}"; Flags: ignoreversion
; _internal 文件夹及其所有内容
Source: "dist\鲲穹AI证件照\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
; 如果有其他文件，可以在这里添加
;Source: "README.txt"; DestDir: "{app}"; Flags: ignoreversion
;Source: "LICENSE.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; 开始菜单程序组
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"
; 桌面图标
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
; 快速启动栏图标
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

[Run]
; 安装完成后运行程序
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; 卸载时删除可能创建的用户数据文件夹 (可选)
Type: filesandordirs; Name: "{app}"

[Code]
// 检查是否已安装旧版本
function InitializeSetup(): Boolean;
var
  OldVersion: String;
  UninstallPath: String;
  ResultCode: Integer;
begin
  Result := True;
  
  // 检查是否已安装
  if RegQueryStringValue(HKLM, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{A1B2C3D4-E5F6-4A5B-8C9D-0E1F2A3B4C5D}_is1', 'UninstallString', UninstallPath) or
     RegQueryStringValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{A1B2C3D4-E5F6-4A5B-8C9D-0E1F2A3B4C5D}_is1', 'UninstallString', UninstallPath) then
  begin
    if MsgBox('检测到已安装旧版本，是否先卸载旧版本？', mbConfirmation, MB_YESNO) = IDYES then
    begin
      // 执行卸载
      Exec(RemoveQuotes(UninstallPath), '/SILENT', '', SW_SHOW, ewWaitUntilTerminated, ResultCode);
    end;
  end;
end;

// 安装完成后的消息
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // 可以在这里添加一些安装后的处理
  end;
end;
