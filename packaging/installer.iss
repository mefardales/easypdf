; ---------------------------------------------------------------------------
; Instalador de easypdf.surf para Windows (Inno Setup 6)
;
;   1) pyinstaller packaging/easypdf.spec --noconfirm     -> dist/EasyPDF/
;   2) iscc packaging/installer.iss                       -> dist/installer/
;
; Se instala sin permisos de administrador si el usuario lo prefiere.
; ---------------------------------------------------------------------------

#define MyAppName "easypdf.surf"
; Los archivos y carpetas siguen llamandose EasyPDF (un ejecutable llamado
; easypdf.surf.exe pareceria tener una extension rara).
#define MyAppFolder "EasyPDF"
#define MyAppVersion "1.5.2"
#define MyAppPublisher "easypdf.surf"
#define MyAppURL "https://github.com/mefardales/easypdf"
#define MyAppExeName "EasyPDF.exe"
#define SourceDir "..\dist\EasyPDF"

[Setup]
; No cambies este AppId: es lo que permite actualizar sobre una version anterior.
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
; Permite instalar para todos los usuarios (admin) o solo para el actual.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline
ChangesAssociations=yes
MinVersion=10.0

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "associate"; Description: "Abrir los archivos .pdf con easypdf.surf"; GroupDescription: "Asociaciones de archivo:"; Flags: unchecked

[Files]
Source: "{#SourceDir}\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\*"; DestDir: "{app}"; Excludes: "{#MyAppExeName}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; DestName: "LEEME.md"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; Identificador propio de documento: siempre se registra, para que la
; aplicacion aparezca en "Abrir con" aunque no sea la predeterminada.
Root: HKA; Subkey: "Software\Classes\EasyPDF.Document"; ValueType: string; ValueName: ""; ValueData: "Documento PDF"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\EasyPDF.Document\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName},0"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\EasyPDF.Document\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}\SupportedTypes"; ValueType: string; ValueName: ".pdf"; ValueData: ""; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\.pdf\OpenWithProgids"; ValueType: string; ValueName: "EasyPDF.Document"; ValueData: ""; Flags: uninsdeletevalue
; Solo si el usuario marca la casilla: pasa a ser el programa predeterminado.
Root: HKA; Subkey: "Software\Classes\.pdf"; ValueType: string; ValueName: ""; ValueData: "EasyPDF.Document"; Tasks: associate; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\{#MyAppFolder}"; ValueType: string; ValueName: "InstallDir"; ValueData: "{app}"; Flags: uninsdeletekey

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
