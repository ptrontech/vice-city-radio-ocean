[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$demarrage = Join-Path $PSScriptRoot 'lancer.pyw'
if (-not (Test-Path -LiteralPath $demarrage -PathType Leaf)) {
    throw 'Le lanceur du logiciel est introuvable.'
}
$python = (Get-Command pythonw.exe -CommandType Application | Select-Object -First 1).Source
$bureau = [Environment]::GetFolderPath('DesktopDirectory')
$nom = 'Atelier des IA ' + [char]0x2013 + ' Vice City.lnk'
$chemin = Join-Path $bureau $nom
$wsh = New-Object -ComObject WScript.Shell
$lien = $wsh.CreateShortcut($chemin)
$lien.TargetPath = $python
$lien.Arguments = '"' + $demarrage + '"'
$lien.WorkingDirectory = $PSScriptRoot
$lien.Description = 'Ouvrir les conversations et le journal du projet Radio Ocean'
$lien.IconLocation = (Join-Path $PSScriptRoot 'atelier.ico') + ',0'
$lien.Save()
Write-Output $chemin
