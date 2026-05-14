# install_config.ps1
# Kopiert die Mod-Config automatisch in den richtigen WoT-Versionsordner.
# Aufruf: .\install_config.ps1
# Optional: .\install_config.ps1 -WotPath "D:\Games\World_of_Tanks"

param(
    [string]$WotPath = "C:\Games\World_of_Tanks"
)

$ResMods = Join-Path $WotPath "res_mods"

if (-not (Test-Path $ResMods)) {
    Write-Host "FEHLER: res_mods Ordner nicht gefunden unter: $ResMods" -ForegroundColor Red
    Write-Host "Bitte WoT-Pfad anpassen: .\install_config.ps1 -WotPath 'D:\Games\World_of_Tanks'"
    exit 1
}

# Hoechste Versionsnummer ermitteln
$versions = Get-ChildItem $ResMods -Directory |
    Where-Object { $_.Name -match '^\d+\.\d+' } |
    Sort-Object Name -Descending

if ($versions.Count -eq 0) {
    Write-Host "FEHLER: Keine WoT-Version in res_mods gefunden." -ForegroundColor Red
    exit 1
}

$latestVersion = $versions[0].Name
$targetDir = Join-Path $ResMods "$latestVersion\mods\damage_challenge"

Write-Host "WoT-Version erkannt: $latestVersion"
Write-Host "Zielordner: $targetDir"

# Ordner anlegen falls nicht vorhanden
if (-not (Test-Path $targetDir)) {
    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
    Write-Host "Ordner angelegt." -ForegroundColor Green
}

# config.example.json als config.json kopieren (nur wenn noch keine existiert)
$configSrc = Join-Path $PSScriptRoot "mod\config.example.json"
$configDst = Join-Path $targetDir "config.json"

if (Test-Path $configDst) {
    Write-Host "Config existiert bereits: $configDst" -ForegroundColor Yellow
    Write-Host "NICHT ueberschrieben. Bitte manuell anpassen wenn noetig."
} else {
    Copy-Item $configSrc $configDst
    Write-Host "Config kopiert nach: $configDst" -ForegroundColor Green
    Write-Host ""
    Write-Host "WICHTIG: Oeffne die Config und trage deine Daten ein:" -ForegroundColor Cyan
    Write-Host "  $configDst"
    notepad $configDst
}

# .wotmod kopieren
$wotmodSrc = Join-Path $PSScriptRoot "dist\mod_damage_challenge.wotmod"
$wotmodDst = Join-Path $WotPath "mods\mod_damage_challenge.wotmod"

if (Test-Path $wotmodSrc) {
    $modsDir = Join-Path $WotPath "mods"
    if (-not (Test-Path $modsDir)) {
        New-Item -ItemType Directory -Path $modsDir -Force | Out-Null
    }
    Copy-Item $wotmodSrc $wotmodDst -Force
    Write-Host ".wotmod kopiert nach: $wotmodDst" -ForegroundColor Green
} else {
    Write-Host "HINWEIS: dist\mod_damage_challenge.wotmod nicht gefunden." -ForegroundColor Yellow
    Write-Host "         Zuerst build_wotmod.py mit Python 2.7 ausfuehren."
}

Write-Host ""
Write-Host "Setup abgeschlossen! WoT neu starten und eine Trainingsschlacht spielen." -ForegroundColor Green
