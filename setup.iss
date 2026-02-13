#define MyAppName "Kinolist Tag Editor"
#define MyAppVersion "0.2.10"
#define VersionInfoVersion "0.1.0.0"
#define MyAppPublisher "Vanyunin Alexander"

[Setup]
AppId={{7807E6AC-E0B1-4441-8BC9-C2607C259241}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
VersionInfoVersion={#VersionInfoVersion}
AppCopyright=Copyright (C) 2022-2025 {#MyAppPublisher}
AppPublisher={#MyAppPublisher}
DefaultDirName={userappdata}\kl_tag
DefaultGroupName={#MyAppName}
PrivilegesRequired=lowest
OutputDir=.\dist
SetupIconFile=.\images\favicon.ico
UninstallDisplayIcon=.\images\favicon.ico
LicenseFile=.\LICENSE
OutputBaseFilename=KL_Tag {#MyAppVersion} Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ChangesEnvironment=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Files]
Source: ".\dist\kl_tag\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Registry]
Root: HKA; Subkey: "Software\Classes\Directory\Background\shell\KL_Tag"; Flags: uninsdeletekey 
Root: HKA; Subkey: "Software\Classes\Directory\Background\shell\KL_Tag"; ValueName: "MUIVerb"; ValueType: String; ValueData: "Редактировать теги MP4"; Flags: uninsdeletevalue 
Root: HKA; Subkey: "Software\Classes\Directory\Background\shell\KL_Tag"; ValueName: "Icon"; ValueType: ExpandSZ; ValueData: "%APPDATA%\kl_tag\kl_tag.exe"; Flags: uninsdeletevalue 
Root: HKA; Subkey: "Software\Classes\Directory\Background\shell\KL_Tag\command"; Flags: uninsdeletekey 
Root: HKA; Subkey: "Software\Classes\Directory\Background\shell\KL_Tag\command"; ValueType: ExpandSZ; ValueData: """%APPDATA%\kl_tag\kl_tag.exe"" ""%V"""; Flags: uninsdeletevalue 
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.mp4\shell\KL_Tag"; Flags: uninsdeletekey 
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.mp4\shell\KL_Tag"; ValueType: String; ValueData: "Редактировать теги"; Flags: uninsdeletevalue 
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.mp4\shell\KL_Tag"; ValueName: "Icon"; ValueType: String; ValueData: "{userappdata}\KL_Tag\kl_tag.exe"; Flags: uninsdeletevalue 
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.mp4\shell\KL_Tag\command"; Flags: uninsdeletekey 
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.mp4\shell\KL_Tag\command"; ValueType: String; ValueData: """{userappdata}\KL_Tag\kl_tag.exe"" ""%1"""; Flags: uninsdeletevalue 