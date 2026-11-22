[CmdletBinding()]
param(
    [string]$Pythonw,
    [switch]$Bureau
)
$ErrorActionPreference = 'Stop'
$projet = (Get-Item -LiteralPath $PSScriptRoot).Parent.FullName
$racine = (Get-Item -LiteralPath $projet).Parent.FullName
$lanceur = Join-Path $PSScriptRoot 'lancer.py'
if (-not $Pythonw) { $Pythonw = (Get-Command pythonw.exe -CommandType Application | Select-Object -First 1).Source }
$nom = 'Radio Oc' + [char]0xe9 + 'an'
$direct = 'Jouer ' + [char]0xe0 + ' ' + $nom
$liens = @(
    @{ Nom = $direct; Param = ' --profil Campagne'; Bureau = $true },
    @{ Nom = ('Options ' + $nom); Param = ''; Bureau = $true },
    @{ Nom = ('Mode libre ' + $nom); Param = ' --profil Libre'; Bureau = $false }
)
$wsh = New-Object -ComObject WScript.Shell
foreach ($spec in $liens) {
    $dossiers = @($racine)
    if ($Bureau -and $spec.Bureau) { $dossiers += [Environment]::GetFolderPath('DesktopDirectory') }
    foreach ($dossier in $dossiers) {
        $chemin = Join-Path $dossier ($spec.Nom+'.lnk')
        $existe = Test-Path -LiteralPath $chemin
        $lien = $wsh.CreateShortcut($chemin)
        if ($existe -and $lien.Arguments.IndexOf($lanceur,[StringComparison]::OrdinalIgnoreCase) -lt 0) {
            throw "Un autre raccourci utilise ce nom : $chemin"
        }
        $lien.TargetPath = $Pythonw
        $lien.Arguments = '"' + $lanceur + '"' + $spec.Param
        $lien.WorkingDirectory = $projet
        $lien.IconLocation = (Join-Path $racine 'Jeu\gta-vc.exe') + ',0'
        $lien.WindowStyle = 1
        $lien.Save()
        Write-Output $chemin
    }
}
