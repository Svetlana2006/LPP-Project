$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$rawPath = Join-Path $root 'data\raw\south_korea_large_food_waste_generators.csv'
$outputDirectory = Join-Path $root 'data\processed'
$snapshotDate = '2026-11-09'
$restaurantType = [string][char]0xC74C + [char]0xC2DD + [char]0xC810
$seoulPrefix = [string][char]0xC11C + [char]0xC6B8

if (-not (Test-Path -LiteralPath $rawPath)) {
    throw "Required source extract not found: $rawPath"
}

New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
$sourceRows = Import-Csv -LiteralPath $rawPath
$restaurantRows = @($sourceRows | Where-Object { $_.BIZEST_SE -eq $restaurantType })
$restaurantObservations = [System.Collections.Generic.List[object]]::new()

foreach ($row in $restaurantRows) {
    $restaurantObservations.Add([pscustomobject]@{
        observation_id = 'KR-WASTE-{0:D5}' -f ($restaurantObservations.Count + 1)
        business_name = $row.CONM_NM
        business_type = $row.BIZEST_SE
        administrative_locality = $row.INSTT_NM
        road_address = $row.LCTN_ROAD_NM_ADDR
        lot_address = $row.LCTN_LOTNO_ADDR
        declaration_date = $row.DCLR_YMD
        source_reference_date = $row.CRTR_YMD
        raw_reported_discharge_quantity = $row.PROD_QTY
        quantity_unit_status = 'STANDARD_KG_PER_MONTH'
        quantity_period_status = 'REPORTED_EXPECTED_MONTHLY_AMOUNT'
        model_supply_eligibility = 'NOT_ESTABLISHED'
        evidence_class = 'PROXY'
        source_id = 'KR-PDP-15107746'
        source_url = 'https://www.data.go.kr/data/15107746/standard.do'
        snapshot_date = $snapshotDate
    })
}

$restaurantPath = Join-Path $outputDirectory 'korea_restaurant_waste_observations.csv'
$restaurantObservations | Export-Csv -NoTypeInformation -Encoding utf8 -LiteralPath $restaurantPath

$seoulObservations = @(
    $restaurantObservations | Where-Object {
        $_.administrative_locality.StartsWith($seoulPrefix)
    }
)
$seoulPath = Join-Path $outputDirectory 'korea_seoul_restaurant_waste_observations.csv'
$seoulObservations | Export-Csv -NoTypeInformation -Encoding utf8 -LiteralPath $seoulPath

$directoryUrl = 'https://www.foodbank1377.org/introduce/foodbankMap.do'
$firstPage = Invoke-WebRequest -Uri $directoryUrl -SessionVariable foodbankSession -UseBasicParsing
$firstPageHtml = $firstPage.Content
$totalMatch = [regex]::Match($firstPageHtml, 'var\s+total\s*=\s*(\d+)')
$rowCountMatch = [regex]::Match(
    $firstPageHtml,
    'id="rowCount"[^>]*value="(\d+)"'
)

if (-not $totalMatch.Success -or -not $rowCountMatch.Success) {
    throw 'Could not read the food-bank directory pagination metadata.'
}

$expectedCount = [int]$totalMatch.Groups[1].Value
$pageSize = [int]$rowCountMatch.Groups[1].Value
$pageCount = [math]::Ceiling($expectedCount / $pageSize)
$sites = [System.Collections.Generic.List[object]]::new()

for ($page = 1; $page -le $pageCount; $page++) {
    $pageHtml = $firstPageHtml
    if ($page -gt 1) {
        $response = Invoke-WebRequest `
            -Uri $directoryUrl `
            -Method Post `
            -WebSession $foodbankSession `
            -Body @{ currentPage = [string]$page; rowCount = [string]$pageSize } `
            -UseBasicParsing
        $pageHtml = $response.Content
    }

    $mapListMatch = [regex]::Match(
        $pageHtml,
        'var\s+mapList\s*=\s*(\[.*?\]);',
        [System.Text.RegularExpressions.RegexOptions]::Singleline
    )
    if (-not $mapListMatch.Success) {
        throw "Could not read food-bank directory records from page $page."
    }

    $pageSites = ConvertFrom-Json $mapListMatch.Groups[1].Value
    foreach ($site in $pageSites) {
        $sites.Add([pscustomobject]@{
            site_id = 'KFB-{0:D4}' -f ($sites.Count + 1)
            organization_name = $site.SHOP_NM
            administrative_area = $site.ASN_CODNM
            address_as_listed = ([string]$site.ADDR).Trim()
            directory_type = 'Korea Foodbank map listing'
            capacity_kg = ''
            receiving_capacity_status = 'NOT_PUBLISHED'
            source_id = 'KFB-MAP-2026-11-09'
            source_url = $directoryUrl
            snapshot_date = $snapshotDate
        })
    }
}

if ($sites.Count -ne $expectedCount) {
    throw "Expected $expectedCount food-bank records; retrieved $($sites.Count)."
}

$sitePath = Join-Path $outputDirectory 'korea_foodbank_sites.csv'
$sites | Export-Csv -NoTypeInformation -Encoding utf8 -LiteralPath $sitePath

Write-Output "Restaurant observations: $($restaurantObservations.Count)"
Write-Output "Seoul restaurant observations: $($seoulObservations.Count)"
Write-Output "Food-bank directory sites: $($sites.Count)"
Write-Output "Wrote $restaurantPath"
Write-Output "Wrote $seoulPath"
Write-Output "Wrote $sitePath"
