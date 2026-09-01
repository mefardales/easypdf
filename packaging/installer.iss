; ---------------------------------------------------------------------------
; easypdf.surf installer for Windows (Inno Setup 6)
;
;   1) pyinstaller packaging/easypdf.spec --noconfirm     -> dist/EasyPDF/
;   2) iscc packaging/installer.iss                       -> dist/installer/
;
; It installs without administrator rights if the user prefers.
; ---------------------------------------------------------------------------

#define MyAppName "easypdf.surf"
; Files and folders are still called EasyPDF (an executable named
; easypdf.surf.exe would look like it had an odd extension).
#define MyAppFolder "EasyPDF"
#define MyAppVersion "1.6.2"
#define MyAppPublisher "easypdf.surf"
#define MyAppURL "https://github.com/mefardales/easypdf"
#define MyAppExeName "EasyPDF.exe"
#define SourceDir "..\dist\EasyPDF"

[Setup]
; Do not change this AppId: it is what lets a new version install over an old one.
AppId={{7C4E9A61-4C1B-4C55-9E77-2E4B3D1F8A02}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
VersionInfoVersion={#MyAppVersion}
DefaultDirName={autopf}\{#MyAppFolder}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=..\LICENSE
OutputDir=..\dist\installer
OutputBaseFilename=EasyPDF-{#MyAppVersion}-Setup
SetupIconFile=..\assets\easypdf.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName} {#MyAppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
; Allows installing for every user (admin) or only for the current one.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline
ChangesAssociations=yes
MinVersion=10.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[CustomMessages]
english.AssociatePdf=Open .pdf files with easypdf.surf
english.FileAssociations=File associations:
english.PdfDocument=PDF document
spanish.AssociatePdf=Abrir los archivos .pdf con easypdf.surf
spanish.FileAssociations=Asociaciones de archivo:
spanish.PdfDocument=Documento PDF

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "associate"; Description: "{cm:AssociatePdf}"; GroupDescription: "{cm:FileAssociations}"; Flags: unchecked

[Files]
Source: "{#SourceDir}\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\*"; DestDir: "{app}"; Excludes: "{#MyAppExeName}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; DestName: "README.md"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; Our own document identifier: always registered, so the application shows up
; under "Open with" even when it is not the default.
Root: HKA; Subkey: "Software\Classes\EasyPDF.Document"; ValueType: string; ValueName: ""; ValueData: "{cm:PdfDocument}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\EasyPDF.Document\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName},0"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\EasyPDF.Document\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}\SupportedTypes"; ValueType: string; ValueName: ".pdf"; ValueData: ""; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\.pdf\OpenWithProgids"; ValueType: string; ValueName: "EasyPDF.Document"; ValueData: ""; Flags: uninsdeletevalue
; Only if the user ticks the box: it becomes the default program.
Root: HKA; Subkey: "Software\Classes\.pdf"; ValueType: string; ValueName: ""; ValueData: "EasyPDF.Document"; Tasks: associate; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\{#MyAppFolder}"; ValueType: string; ValueName: "InstallDir"; ValueData: "{app}"; Flags: uninsdeletekey

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
