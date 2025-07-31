#
# Argument initialization
#

$nextarg = "none"
$DebugPort = "unassigned"
$targetcomputer = "."
$VMName = ""
$VMGuid = ""
$AutoAssign = "false"
$DebugOff = "false"

function funHelp()
{
$helpText=@"

DESCRIPTION:
NAME: kdnetdebugvm.ps1
Displays (and optionally sets) the port used to network debug a VM.

PARAMETERS: 
-computerName Specifies the name of the computer on which to run the script
-help         Displays help
-vmname       (optional) Name of the VM of interest
-vmguid       (optional) GUID of the VM of interest
-port         (optional) Network port to use for debugging
-debugoff
-autoassign

Either vmname or vmguid must be specified to identify the VM, but not both.
Note that vmname may not uniquely identify the VM, but vmguid does.

SYNTAX:
kdnetdebugvm.ps1 [-computerName targetcomputer] [-vmname NameOfVM] [-vmguid GuidOfVM] [-port PortNumber]

"@
$helpText
exit
}


foreach ($argument in $args)
{
    # parse commands with no following arguments
    switch ($argument)
    {
        "?"     {funHelp}
        "help"  {funHelp}
        "-help" {funHelp}
        "/?"    {funHelp}
        "-?"    {funHelp}
        "autoassign"    {$AutoAssign = "true"}
        "-autoassign"   {$AutoAssign = "true"}
        "/autoassign"   {$AutoAssign = "true"}
        "debugoff"        {$DebugOff = "true"}
        "-debugoff"       {$DebugOff = "true"}
        "/debugoff"       {$DebugOff = "true"}
        default {}
    }

    # parse values that followed a switch

    switch ($nextarg)
    {
        "vmname"        {$VMName = $argument}
        "-vmname"       {$VMName = $argument}
        "/vmname"       {$VMName = $argument}
        "vmguid"        {$VMGuid = $argument}
        "-vmguid"       {$VMGuid = $argument}
        "/vmguid"       {$VMGuid = $argument}
        "port"          {$DebugPort = $argument}
        "-port"         {$DebugPort = $argument}
        "/port"         {$DebugPort = $argument}
        "computername"  {$targetcomputer = $argument}
        "-computername" {$targetcomputer = $argument}
        "/computername" {$targetcomputer = $argument}
        default         {}
    }

    $nextarg = $argument
}

if (($VMName -eq "") -and ($VMGuid -eq ""))
{
    funHelp
}

if (($VMName -ne "") -and ($VMGuid -ne ""))
{
    funHelp
}

$ns = "root\virtualization\v2"
$VMWPName = "$env:windir\system32\vmwp.exe"

#Get a VMManagementService object
$VMManagementService = gwmi -class "Msvm_VirtualSystemManagementService" -namespace $ns -computername $targetcomputer

#Get the VM object that we want to modify
if ($VMName -ne "")
{
    $VM = Get-VM -computername $targetcomputer -VMName $VMName
}

if ($VMGuid -ne "")
{
    $VM = Get-VM -computername $targetcomputer -Id $VMGuid
}

#Get the VirtualSystemGlobalSettingData of the VM we want to modify
$VMSystemGlobalSettingData = gwmi -namespace $ns -computername $targetcomputer -class Msvm_VirtualSystemSettingData | ? { $_.ConfigurationID -eq $VM.Id }

# Set a new debugport
if ($DebugPort -ne "unassigned")
{
    #Change the ElementName property
    $VMSystemGlobalSettingData.DebugPort = $DebugPort
    $VMSystemGlobalSettingData.DebugPortEnabled = 1

    $VMManagementService.ModifySystemSettings($VMSystemGlobalSettingData.GetText(1))
    $FWRuleName = "SynthDebugInboundRule-$DebugPort"
    New-NetFirewallRule -DisplayName $FWRuleName -Program $VMWPName -Protocol UDP -Action Allow -Direction Inbound -LocalPort $DebugPort
}

# Enable auto assigned debug ports
if ($AutoAssign -ne "false")
{
    #Change the ElementName property
    $VMSystemGlobalSettingData.DebugPortEnabled = 2
    $VMManagementService.ModifySystemSettings($VMSystemGlobalSettingData.GetText(1))
    Write-Host -Foreground Yellow "Firewall Ports for autoassign mode can be opened only after the VM is started."
}

# Turn off debugging
if ($DebugOff -ne "false")
{
    $DebugPort = $VMSystemGlobalSettingData.DebugPort
    #Change the ElementName property
    $VMSystemGlobalSettingData.DebugPortEnabled = 0
    $VMSystemGlobalSettingData.DebugPort = 0
    $VMManagementService.ModifySystemSettings($VMSystemGlobalSettingData.GetText(1))
    # May throw an exception if the rule did not exist already.
    # If two rules exist with the same name, both will be deleted.
    if ($DebugPort -ne 0)
    {
        $FWRuleName = "SynthDebugInboundRule-$DebugPort"
        Remove-NetFirewallRule -DisplayName $FWRuleName
    }
}

$VMSystemGlobalSettingData

exit

# SIG # Begin signature block
# MIIpZAYJKoZIhvcNAQcCoIIpVTCCKVECAQExDzANBglghkgBZQMEAgEFADB5Bgor
# BgEEAYI3AgEEoGswaTA0BgorBgEEAYI3AgEeMCYCAwEAAAQQH8w7YFlLCE63JNLG
# KX7zUQIBAAIBAAIBAAIBAAIBADAxMA0GCWCGSAFlAwQCAQUABCDbHDLYuqp9Du8W
# ZSYoLwjEyhkYywkzwemxEtpUqBqajKCCDdYwgga9MIIEpaADAgECAhMzAAAAHEif
# gd+hsLd3AAAAAAAcMA0GCSqGSIb3DQEBDAUAMIGIMQswCQYDVQQGEwJVUzETMBEG
# A1UECBMKV2FzaGluZ3RvbjEQMA4GA1UEBxMHUmVkbW9uZDEeMBwGA1UEChMVTWlj
# cm9zb2Z0IENvcnBvcmF0aW9uMTIwMAYDVQQDEylNaWNyb3NvZnQgUm9vdCBDZXJ0
# aWZpY2F0ZSBBdXRob3JpdHkgMjAxMDAeFw0yNDA4MDgyMTM2MjNaFw0zNTA2MjMy
# MjA0MDFaMF8xCzAJBgNVBAYTAlVTMR4wHAYDVQQKExVNaWNyb3NvZnQgQ29ycG9y
# YXRpb24xMDAuBgNVBAMTJ01pY3Jvc29mdCBXaW5kb3dzIENvZGUgU2lnbmluZyBQ
# Q0EgMjAyNDCCAiIwDQYJKoZIhvcNAQEBBQADggIPADCCAgoCggIBAJp9a30nwXYq
# Lq7j1TT/zCtt7vxU+CCj+7BkifS/B2gXKGU7OV9SXRJGP1yFs5p6jpsYi4cYzF56
# AV0AEmmEjV8wT2lvPU5BhN3wV30HqYPIYEj5P3WXf0kXD9fvjUf1GAtXEriJ8w7A
# LNaVEm9Rs4ePA0ZsYHaCbU5kBUJQDXv76hafOcQgdFCA3I3zYtfzX2vOwx87uDOa
# CuyKORZih9c3zTf+TLC5QYLyhVMBnDXEHDOrvaw92DSyIqpdgRWpufzqDFy1egVj
# koXZhb+9pZ9heUzNXTXhOoXzexh6YzAL4flBWm+Bc1hQyESenEvBJznV+25u3h77
# jjgMUY44+WXQ4u9qddDe/U5SeAaKRvvibmi4z7QRpLvZsla0CPiOUGz00Do5sfkC
# 0EwlsSzfM3+8A9rsyFVOgWDVPzt98OJP2EoaEOq8GE9GCoN2i7/4C2FCwff1BSCT
# JWZO1Wcr2MteJE6UxGV+ihA8nN51YPKD2dYGoewrXvRzC/1HoUeSvlZf0mf9GHEt
# vvkbJVRRo6PBf0md5t87Vb1mM/fIp1eypyaxmXkgpcBwuylsOq2kSVOJ5wBPoaEs
# sJkeMcKnEuuu++UKdDHlS0DtsYjN0QnOucvTdSsdvhzKOSjJF3XVqr9f2C945LXT
# 5rxKIHUIEDBcNYU6BKDDH6rfpKOOCSilAgMBAAGjggFGMIIBQjAOBgNVHQ8BAf8E
# BAMCAYYwEAYJKwYBBAGCNxUBBAMCAQAwHQYDVR0OBBYEFB6C3w7XjLPXAjSDDtqr
# rWW5r7jsMBkGCSsGAQQBgjcUAgQMHgoAUwB1AGIAQwBBMA8GA1UdEwEB/wQFMAMB
# Af8wHwYDVR0jBBgwFoAU1fZWy4/oolxiaNE9lJBb186aGMQwVgYDVR0fBE8wTTBL
# oEmgR4ZFaHR0cDovL2NybC5taWNyb3NvZnQuY29tL3BraS9jcmwvcHJvZHVjdHMv
# TWljUm9vQ2VyQXV0XzIwMTAtMDYtMjMuY3JsMFoGCCsGAQUFBwEBBE4wTDBKBggr
# BgEFBQcwAoY+aHR0cDovL3d3dy5taWNyb3NvZnQuY29tL3BraS9jZXJ0cy9NaWNS
# b29DZXJBdXRfMjAxMC0wNi0yMy5jcnQwDQYJKoZIhvcNAQEMBQADggIBAENf+N8/
# u+mUjDtc9btoA52RBc0XVDSBMQBMqxu56hXHBwuctUWs1XBqDDMIFCHu9c6Y/UF+
# TN8EIgjnujApKYmHP4f4EM3ARSmlzrpF5ozOJx0BA5FUv1jmpdf/2ZbqpvCxlxv/
# G1R4KjrSmmqPHzs6igw3b7RTbj7BxIS8fOIkwYWQhB2fLjlg+3HSrDGPFIhpIJWV
# amMIR7a72OGonjdf45rspwqIHuynZU4avy9ruB/Rhhbwm+fMb8BMecIaTmkohx/E
# ZZ5GNWcN6oTYW3G2BM3B3YznWkl9t4shP60fMue+2ksdHGWSE8EVTdSmGUdj0jrU
# c46lGVFJISF3/MxcxnlNeP1Khyr+ZzT4Ets/I7mufpaLnLalzMR2zIuhGOAWWswe
# sbjtFzkVUFgDR2SW903I0XKlbPEA6q8epHGJ9roxh85nsEKcBNUw4Scp68KCqSpF
# BaKiyV1skd+l8U50WNePMb9Bzz0OfASal8v5sQG+DW01kN+I+RKUIbM5I50wJjiH
# ymQFNDsbobFx9I95mCEEPU7fUZ3VT/HOUVbkmX7ltIC/eQAu5GO8fu+ceETMybvb
# oxUM4dYNC+PzooUxfmC0DuKRwB21bX9+acuIBkxIm4Ed3O19w1VLoA7UNOUuJ7z6
# NQ2W/+q7cnfOPl2QVL4qlgCblUT2vmQpllV3MIIHETCCBPmgAwIBAgITMwAAAIe8
# gm6Foa5TqAAAAAAAhzANBgkqhkiG9w0BAQwFADBfMQswCQYDVQQGEwJVUzEeMBwG
# A1UEChMVTWljcm9zb2Z0IENvcnBvcmF0aW9uMTAwLgYDVQQDEydNaWNyb3NvZnQg
# V2luZG93cyBDb2RlIFNpZ25pbmcgUENBIDIwMjQwHhcNMjUwNTA4MTgyNDU0WhcN
# MjYwNTA2MTgyNDU0WjB0MQswCQYDVQQGEwJVUzETMBEGA1UECBMKV2FzaGluZ3Rv
# bjEQMA4GA1UEBxMHUmVkbW9uZDEeMBwGA1UEChMVTWljcm9zb2Z0IENvcnBvcmF0
# aW9uMR4wHAYDVQQDExVNaWNyb3NvZnQgQ29ycG9yYXRpb24wggIiMA0GCSqGSIb3
# DQEBAQUAA4ICDwAwggIKAoICAQC0JvvNCq9eE0sLt0WdArsItuEZpbuTI0W3EVMS
# i6PTkY1xniZhsm8rsEzr/Ngq77HknKV8GYYNkVxhppwdoQilh/R0KELXZi22Qqi4
# jEUsOYgkDHPIbnUEcQvbaG1R2ijOme/uGE9DX3RBx9Pkbi8TYec1d2iDhzF/xofy
# oZHPUTvL2PzDae7ncAjjRChG7kCzobShkcMpUZPyYMXKtqCMAx4OBYdeBF6PGfft
# 4Z16crWAmSEGMCcXQ7EVxWj1W7R5sOo4TilWQBQp9yYyvKYUObpiQwUjNZb4wALe
# Y6msmJogp7LC5N6warLYTbhwJJblmhZQIhaD8UABuP030nUofVkGDqK6xC/REnOE
# KTnsE+KaRb8JDOBXWSscNMQSR7wbX2NF+hK/S4dg6NUHzr0p0k20yY8LZg0OPOeb
# Hg5WdXUqkFHNB4Ck2aOT4rhu7YYiYBewfVZXF4/XF/BemkMKgnQToJvFJYLMPZM3
# tosN1IW0Ow3Ny3RvwQfHPGQ1kSqprOl14JFTI9CO/CZzhZbgeRB9Z3dWcXt1RYpu
# NIAkMWl7gDTRYy4gWhkgmzE1x1cz1hA8hKZIvD0VmNiwqN1HHRDHn2ryxmLgZgLh
# kth4K/i3CR+xSiptNnYnpMkE0Rre89r45MKUHytz0z0yqSsey/BsJ9RhnTvqiNrX
# Ay0TBwIDAQABo4IBrzCCAaswDgYDVR0PAQH/BAQDAgeAMB8GA1UdJQQYMBYGCisG
# AQQBgjc9BgEGCCsGAQUFBwMDMAwGA1UdEwEB/wQCMAAwHQYDVR0OBBYEFCYGR6ii
# PVV4VrV7+HKNkZBNf6SoMEUGA1UdEQQ+MDykOjA4MR4wHAYDVQQLExVNaWNyb3Nv
# ZnQgQ29ycG9yYXRpb24xFjAUBgNVBAUTDTIzMDg2NSs1MDQ1ODEwHwYDVR0jBBgw
# FoAUHoLfDteMs9cCNIMO2qutZbmvuOwwagYDVR0fBGMwYTBfoF2gW4ZZaHR0cDov
# L3d3dy5taWNyb3NvZnQuY29tL3BraW9wcy9jcmwvTWljcm9zb2Z0JTIwV2luZG93
# cyUyMENvZGUlMjBTaWduaW5nJTIwUENBJTIwMjAyNC5jcmwwdwYIKwYBBQUHAQEE
# azBpMGcGCCsGAQUFBzAChltodHRwOi8vd3d3Lm1pY3Jvc29mdC5jb20vcGtpb3Bz
# L2NlcnRzL01pY3Jvc29mdCUyMFdpbmRvd3MlMjBDb2RlJTIwU2lnbmluZyUyMFBD
# QSUyMDIwMjQuY3J0MA0GCSqGSIb3DQEBDAUAA4ICAQB+y/LNkTgCe/vYXjHxIrS/
# 73+FTugtMOG7l/fuiVFw3poLaGGtcn7LF5s8/h6soz4ST82QeZA3y/ADvl5VXeO1
# 5mROcELkFZ8kbdzqXTnyuWpDOTTm54DX2XVwxQfFIxYJqBij8pwvlNAB5r3JOBOA
# fegOad1NuCoP0/aA5hgu4ci3d0i+LaBVHm2RlHM44si1KyEg8Rs9g/SQPSijwRMt
# Da7TsWmz7F1J9P+UV36yOmwQ4jepF5h8hFUSrCJ3x7tEqA0ruiy2yCT15FcaJdnQ
# 3tZ8RRUdoCJ/pxtDI3YySMLA2XYLs4qHzoF/TPPNtaWDTvr4a+rBbUZm58pV+S14
# jhtkQAoO+275/a+ESeRSEeP9+Hde3Ez06U1MRKu+uicTPfDhUggSXzcaDImnRS6i
# FjEryJGHhRyZYoMphCjLn+PBJe58nvL/HWuP7kCMbSJOYz1ghVU/k5cgTYqq/V3E
# yzIo2K0MtwoUQcZygkTdCRUv6EtqFWbxtK6fyM6mbCoRgs2tKdMl8EN5nSMRXZEr
# sx6bG6M7BgTiSP56F//HvdLyGKfAR247Nu4/1nxgcDBZVcvCJyj6FmYKnvQEWixb
# aXFlpvCMvahUFV1b/1FKk2EF4ntMScCjyTKUXSTt8cgmVfS8FB1YkZm7IsCjBkua
# GWbGZBLKlwLys7wpFhqvOzGCGuQwghrgAgEBMHYwXzELMAkGA1UEBhMCVVMxHjAc
# BgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEwMC4GA1UEAxMnTWljcm9zb2Z0
# IFdpbmRvd3MgQ29kZSBTaWduaW5nIFBDQSAyMDI0AhMzAAAAh7yCboWhrlOoAAAA
# AACHMA0GCWCGSAFlAwQCAQUAoIGoMBkGCSqGSIb3DQEJAzEMBgorBgEEAYI3AgEE
# MC8GCSqGSIb3DQEJBDEiBCD12p2EXg5HuAOMXy8l2stP0pmptaSGI99pdu8uRzlU
# uDBaBgorBgEEAYI3AgEMMUwwSqAkgCIATQBpAGMAcgBvAHMAbwBmAHQAIABXAGkA
# bgBkAG8AdwBzoSKAIGh0dHA6Ly93d3cubWljcm9zb2Z0LmNvbS93aW5kb3dzMA0G
# CSqGSIb3DQEBAQUABIICADHnv8A6nECr1dcAjlHkTVZKTj9h0ZL9mHd1na0Xe4Ue
# xCn/fkFUXJPXuMIBLqzK+wNa1Fk+6uJ6Shr8UXwXrjMc7m/aPztYqW0jWL4wmDq6
# Nucs+YnsmX1m8XPjmq9/Avno/kwN537yWIWHNUAPdC5zA+5ltcrWtLJPKuS5ZfCM
# 7D4CaR6M4u3+UeeSi0BtCY9D4cts2I18iJe6VGEi0Oodxqh60KLjFDFTmL1a0xis
# /FsP9RgsZvitGLouE1JKYUnVrJqD2KqQkPlQaD9vTe/VFMf5dTsbFqDpns/qisMo
# sIdbU75U45e0Nmp6cddugKk7VUApNucQdfDvZKf849uMMFNxL1e43akBCtOv4tIo
# /45s+a/ZWrtQQmIAOV5WtqOrE2uGbdQmt5cmEmNNNBXT4y/bw1+VrBn2Y8guxZs3
# 7fN+PjIAGlyxBvtD5GrP9j+cTWxWTrBg8AeuA3tw4bZRDn/vumKbkJzNVNnGS/eg
# W2Klp+p5NybAJbH9vVJ5+DrJGQCs6EE1jATQuGYOPzRmd/KK5J/IMAPTa/e91Chh
# aIwky46Fo/VBToeMfci5/Zj7m/qFaUUq+fVStw+LNj0T84p3Px8jCo3cBP89HaIy
# FYd8oF5PA/zC+Etzeuj2s72SCejDLdc/SlnImBloLeUdR+j3soeTO2NUz3Q3AFcl
# oYIXlDCCF5AGCisGAQQBgjcDAwExgheAMIIXfAYJKoZIhvcNAQcCoIIXbTCCF2kC
# AQMxDzANBglghkgBZQMEAgEFADCCAVIGCyqGSIb3DQEJEAEEoIIBQQSCAT0wggE5
# AgEBBgorBgEEAYRZCgMBMDEwDQYJYIZIAWUDBAIBBQAEIHR4xZAtXXWPuPKlwDMB
# oWF9Ka8P8n2VuvBnom1lyQsNAgZoSr7nBKcYEzIwMjUwNzA5MDI1NDU2LjM0NVow
# BIACAfSggdGkgc4wgcsxCzAJBgNVBAYTAlVTMRMwEQYDVQQIEwpXYXNoaW5ndG9u
# MRAwDgYDVQQHEwdSZWRtb25kMR4wHAYDVQQKExVNaWNyb3NvZnQgQ29ycG9yYXRp
# b24xJTAjBgNVBAsTHE1pY3Jvc29mdCBBbWVyaWNhIE9wZXJhdGlvbnMxJzAlBgNV
# BAsTHm5TaGllbGQgVFNTIEVTTjpBNDAwLTA1RTAtRDk0NzElMCMGA1UEAxMcTWlj
# cm9zb2Z0IFRpbWUtU3RhbXAgU2VydmljZaCCEeowggcgMIIFCKADAgECAhMzAAAC
# AnlQdCEUfbihAAEAAAICMA0GCSqGSIb3DQEBCwUAMHwxCzAJBgNVBAYTAlVTMRMw
# EQYDVQQIEwpXYXNoaW5ndG9uMRAwDgYDVQQHEwdSZWRtb25kMR4wHAYDVQQKExVN
# aWNyb3NvZnQgQ29ycG9yYXRpb24xJjAkBgNVBAMTHU1pY3Jvc29mdCBUaW1lLVN0
# YW1wIFBDQSAyMDEwMB4XDTI1MDEzMDE5NDI0NFoXDTI2MDQyMjE5NDI0NFowgcsx
# CzAJBgNVBAYTAlVTMRMwEQYDVQQIEwpXYXNoaW5ndG9uMRAwDgYDVQQHEwdSZWRt
# b25kMR4wHAYDVQQKExVNaWNyb3NvZnQgQ29ycG9yYXRpb24xJTAjBgNVBAsTHE1p
# Y3Jvc29mdCBBbWVyaWNhIE9wZXJhdGlvbnMxJzAlBgNVBAsTHm5TaGllbGQgVFNT
# IEVTTjpBNDAwLTA1RTAtRDk0NzElMCMGA1UEAxMcTWljcm9zb2Z0IFRpbWUtU3Rh
# bXAgU2VydmljZTCCAiIwDQYJKoZIhvcNAQEBBQADggIPADCCAgoCggIBALd5Knpy
# 5xQY6Rw+Di8pYol8RB6yErZkGxhTW0Na9C7ov2Wn52eqtqMh014fUc3ejPeKIagl
# a43YdU1mRw63fxpYZ5szSBRQ60+O4uG47l3rtilCwcEkBaFy978xV2hA+PWeOICN
# KI6svzEVqsUsjjpEfw14OEA9dwmlafsAjMLIiNk5onYNYD7pDA3PCqMGAil/WFYX
# Coe88R53LSei1du1Z9P28JIv2x0Mror8cf0expjnAuZRQHtJ+4sajU5YSbownIba
# OLGqL03JGjKl0Xx1HKNbEpGXYnHC9t62UNOKjrpeWJM5ySrZGAz5mhxkRvoSg521
# 3RcqHcvPHb0CEfGWT7p4jBq+Udi44tkMqh085U3qPUgn1uuiVjqZluhDnU6p7mcQ
# zmH9YlfbwYtmKgSQk3yo57k/k/ZjH0eg6ou6BfTSoLPGrgEObzEfzkcrG8oI7kqK
# SilpEYa1CVeMPK6wxaWsdzJK3noOEvh1xWeft0W8vnTO9CUVkyFWh6FZJCSRa5SU
# IKog6tN7tFuadt0miwf7uUL6fneCcrLg6hnO5R6rMKdIHUk1c8qcmiM/cN7nHCym
# Lm1S9AU1+V8ZOyNmBACAMF2D8M7RMaAtEMq9lAJnmoi5elBHKDfvJznV73nPxTab
# KxTRedKlZ6KAeqTI4C0N9wimrka/sdX51rZHAgMBAAGjggFJMIIBRTAdBgNVHQ4E
# FgQU2ga5tQ+M/Z/yJ+Qgq/DLWuVIdNkwHwYDVR0jBBgwFoAUn6cVXQBeYl2D9OXS
# ZacbUzUZ6XIwXwYDVR0fBFgwVjBUoFKgUIZOaHR0cDovL3d3dy5taWNyb3NvZnQu
# Y29tL3BraW9wcy9jcmwvTWljcm9zb2Z0JTIwVGltZS1TdGFtcCUyMFBDQSUyMDIw
# MTAoMSkuY3JsMGwGCCsGAQUFBwEBBGAwXjBcBggrBgEFBQcwAoZQaHR0cDovL3d3
# dy5taWNyb3NvZnQuY29tL3BraW9wcy9jZXJ0cy9NaWNyb3NvZnQlMjBUaW1lLVN0
# YW1wJTIwUENBJTIwMjAxMCgxKS5jcnQwDAYDVR0TAQH/BAIwADAWBgNVHSUBAf8E
# DDAKBggrBgEFBQcDCDAOBgNVHQ8BAf8EBAMCB4AwDQYJKoZIhvcNAQELBQADggIB
# AIPzdoVBTE3fseQ6gkMzWZocVlVQZypNBw+c4PpShhEyYMq/QZpseUTzYBiAs+5W
# W6Sfse0k8XbPSOdOAB9EyfbokUs8bs79dsorbmGsE8nfSUG7CMBNW3nxQDUFajuW
# yafKu6v/qHwAXOtfKte2W/NBippFhj2TRQVjkYz6f1hoQQrYPbrx75r4cOZZ761g
# vYf707hDUxAtqD5yI3AuSP/5CXGleJai70q8A/S0iT58fwXfDDlU5OL1pn36o+Oz
# PDfUfid22K8FlofmzlugmYfYlu0y5/bLuFJ0l0TRRbYHQURk8siZ6aUqGyUk1WoQ
# 7tE+CXtzzVC5VI7nx9+mZvC1LGFisRLdWw+CVef04MXsOqY8wb8bKwHij9CSk1Sr
# 7BLts5FM3Oocy0f6it3ZhKZr7VvJYGv+LMgqCA4J0TNpkN/KbXYYzprhL4jLoBQi
# nv8oikCZ9Z9etwwrtXsQHPGh7OQtEQRYjhe0/CkQGe05rWgMfdn/51HGzEvS+DJr
# uM1+s7uiLNMCWf/ZkFgH2KhR6huPkAYvjmbaZwpKTscTnNRF5WQgulgoFDn5f/yM
# U7X+lnKrNB4jX+gn9EuiJzVKJ4td8RP0RZkgGNkxnzjqYNunXKcr1Rs2IKNLCZMX
# nT1if0zjtVCzGy/WiVC7nWtVUeRI2b6tOsvArW2+G/SZMIIHcTCCBVmgAwIBAgIT
# MwAAABXF52ueAptJmQAAAAAAFTANBgkqhkiG9w0BAQsFADCBiDELMAkGA1UEBhMC
# VVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAcBgNV
# BAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEyMDAGA1UEAxMpTWljcm9zb2Z0IFJv
# b3QgQ2VydGlmaWNhdGUgQXV0aG9yaXR5IDIwMTAwHhcNMjEwOTMwMTgyMjI1WhcN
# MzAwOTMwMTgzMjI1WjB8MQswCQYDVQQGEwJVUzETMBEGA1UECBMKV2FzaGluZ3Rv
# bjEQMA4GA1UEBxMHUmVkbW9uZDEeMBwGA1UEChMVTWljcm9zb2Z0IENvcnBvcmF0
# aW9uMSYwJAYDVQQDEx1NaWNyb3NvZnQgVGltZS1TdGFtcCBQQ0EgMjAxMDCCAiIw
# DQYJKoZIhvcNAQEBBQADggIPADCCAgoCggIBAOThpkzntHIhC3miy9ckeb0O1YLT
# /e6cBwfSqWxOdcjKNVf2AX9sSuDivbk+F2Az/1xPx2b3lVNxWuJ+Slr+uDZnhUYj
# DLWNE893MsAQGOhgfWpSg0S3po5GawcU88V29YZQ3MFEyHFcUTE3oAo4bo3t1w/Y
# JlN8OWECesSq/XJprx2rrPY2vjUmZNqYO7oaezOtgFt+jBAcnVL+tuhiJdxqD89d
# 9P6OU8/W7IVWTe/dvI2k45GPsjksUZzpcGkNyjYtcI4xyDUoveO0hyTD4MmPfrVU
# j9z6BVWYbWg7mka97aSueik3rMvrg0XnRm7KMtXAhjBcTyziYrLNueKNiOSWrAFK
# u75xqRdbZ2De+JKRHh09/SDPc31BmkZ1zcRfNN0Sidb9pSB9fvzZnkXftnIv231f
# gLrbqn427DZM9ituqBJR6L8FA6PRc6ZNN3SUHDSCD/AQ8rdHGO2n6Jl8P0zbr17C
# 89XYcz1DTsEzOUyOArxCaC4Q6oRRRuLRvWoYWmEBc8pnol7XKHYC4jMYctenIPDC
# +hIK12NvDMk2ZItboKaDIV1fMHSRlJTYuVD5C4lh8zYGNRiER9vcG9H9stQcxWv2
# XFJRXRLbJbqvUAV6bMURHXLvjflSxIUXk8A8FdsaN8cIFRg/eKtFtvUeh17aj54W
# cmnGrnu3tz5q4i6tAgMBAAGjggHdMIIB2TASBgkrBgEEAYI3FQEEBQIDAQABMCMG
# CSsGAQQBgjcVAgQWBBQqp1L+ZMSavoKRPEY1Kc8Q/y8E7jAdBgNVHQ4EFgQUn6cV
# XQBeYl2D9OXSZacbUzUZ6XIwXAYDVR0gBFUwUzBRBgwrBgEEAYI3TIN9AQEwQTA/
# BggrBgEFBQcCARYzaHR0cDovL3d3dy5taWNyb3NvZnQuY29tL3BraW9wcy9Eb2Nz
# L1JlcG9zaXRvcnkuaHRtMBMGA1UdJQQMMAoGCCsGAQUFBwMIMBkGCSsGAQQBgjcU
# AgQMHgoAUwB1AGIAQwBBMAsGA1UdDwQEAwIBhjAPBgNVHRMBAf8EBTADAQH/MB8G
# A1UdIwQYMBaAFNX2VsuP6KJcYmjRPZSQW9fOmhjEMFYGA1UdHwRPME0wS6BJoEeG
# RWh0dHA6Ly9jcmwubWljcm9zb2Z0LmNvbS9wa2kvY3JsL3Byb2R1Y3RzL01pY1Jv
# b0NlckF1dF8yMDEwLTA2LTIzLmNybDBaBggrBgEFBQcBAQROMEwwSgYIKwYBBQUH
# MAKGPmh0dHA6Ly93d3cubWljcm9zb2Z0LmNvbS9wa2kvY2VydHMvTWljUm9vQ2Vy
# QXV0XzIwMTAtMDYtMjMuY3J0MA0GCSqGSIb3DQEBCwUAA4ICAQCdVX38Kq3hLB9n
# ATEkW+Geckv8qW/qXBS2Pk5HZHixBpOXPTEztTnXwnE2P9pkbHzQdTltuw8x5MKP
# +2zRoZQYIu7pZmc6U03dmLq2HnjYNi6cqYJWAAOwBb6J6Gngugnue99qb74py27Y
# P0h1AdkY3m2CDPVtI1TkeFN1JFe53Z/zjj3G82jfZfakVqr3lbYoVSfQJL1AoL8Z
# thISEV09J+BAljis9/kpicO8F7BUhUKz/AyeixmJ5/ALaoHCgRlCGVJ1ijbCHcNh
# cy4sa3tuPywJeBTpkbKpW99Jo3QMvOyRgNI95ko+ZjtPu4b6MhrZlvSP9pEB9s7G
# dP32THJvEKt1MMU0sHrYUP4KWN1APMdUbZ1jdEgssU5HLcEUBHG/ZPkkvnNtyo4J
# vbMBV0lUZNlz138eW0QBjloZkWsNn6Qo3GcZKCS6OEuabvshVGtqRRFHqfG3rsjo
# iV5PndLQTHa1V1QJsWkBRH58oWFsc/4Ku+xBZj1p/cvBQUl+fpO+y/g75LcVv7TO
# PqUxUYS8vwLBgqJ7Fx0ViY1w/ue10CgaiQuPNtq6TPmb/wrpNPgkNWcr4A245oyZ
# 1uEi6vAnQj0llOZ0dFtq0Z4+7X6gMTN9vMvpe784cETRkPHIqzqKOghif9lwY1NN
# je6CbaUFEMFxBmoQtB1VM1izoXBm8qGCA00wggI1AgEBMIH5oYHRpIHOMIHLMQsw
# CQYDVQQGEwJVUzETMBEGA1UECBMKV2FzaGluZ3RvbjEQMA4GA1UEBxMHUmVkbW9u
# ZDEeMBwGA1UEChMVTWljcm9zb2Z0IENvcnBvcmF0aW9uMSUwIwYDVQQLExxNaWNy
# b3NvZnQgQW1lcmljYSBPcGVyYXRpb25zMScwJQYDVQQLEx5uU2hpZWxkIFRTUyBF
# U046QTQwMC0wNUUwLUQ5NDcxJTAjBgNVBAMTHE1pY3Jvc29mdCBUaW1lLVN0YW1w
# IFNlcnZpY2WiIwoBATAHBgUrDgMCGgMVAEmJSGkJYD/df+NnIjLTJ7pEnAvOoIGD
# MIGApH4wfDELMAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNV
# BAcTB1JlZG1vbmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEmMCQG
# A1UEAxMdTWljcm9zb2Z0IFRpbWUtU3RhbXAgUENBIDIwMTAwDQYJKoZIhvcNAQEL
# BQACBQDsGCreMCIYDzIwMjUwNzA4MjM0MDE0WhgPMjAyNTA3MDkyMzQwMTRaMHQw
# OgYKKwYBBAGEWQoEATEsMCowCgIFAOwYKt4CAQAwBwIBAAICNE8wBwIBAAICEvAw
# CgIFAOwZfF4CAQAwNgYKKwYBBAGEWQoEAjEoMCYwDAYKKwYBBAGEWQoDAqAKMAgC
# AQACAwehIKEKMAgCAQACAwGGoDANBgkqhkiG9w0BAQsFAAOCAQEAHznVY7u0FW9f
# dGlhWkYakJ70XfZrm7+oVfLUCCs5IHuNMsu5LRi3F15BhVt2pBLGAUV5A2w0Xdel
# jRH1pULsAFfPK8U26DCqxxDU7oYW+GaH5bi7ZrhjflBpty1jkH5lIrVcxnoX2ANl
# MfCDbTaB043kezQGPCWpB1xS2+NaT1iBs4aI0WwQw8UOi8UoN3HKyUvsZp+dpaS7
# mVKh5qflrRbU/KBR9fsZZEWYHQdSRGmQPE1zETssiULouzOwtcso5037bT+ylsEP
# kF+t9WLk8Pwn3mblvM2xO4nE02FxKj5jp+j+H4b7Od9S7cDx6NWUG8xfHRAHuROV
# x8SFNy74DTGCBA0wggQJAgEBMIGTMHwxCzAJBgNVBAYTAlVTMRMwEQYDVQQIEwpX
# YXNoaW5ndG9uMRAwDgYDVQQHEwdSZWRtb25kMR4wHAYDVQQKExVNaWNyb3NvZnQg
# Q29ycG9yYXRpb24xJjAkBgNVBAMTHU1pY3Jvc29mdCBUaW1lLVN0YW1wIFBDQSAy
# MDEwAhMzAAACAnlQdCEUfbihAAEAAAICMA0GCWCGSAFlAwQCAQUAoIIBSjAaBgkq
# hkiG9w0BCQMxDQYLKoZIhvcNAQkQAQQwLwYJKoZIhvcNAQkEMSIEIGOm9hbqWHoZ
# Lj8ooBQggbUSRFShB1HwY9UDDgskWEWGMIH6BgsqhkiG9w0BCRACLzGB6jCB5zCB
# 5DCBvQQg843qARgHlsvNcta5SYvxl3zFcCypeSx50XKiV8yUX+wwgZgwgYCkfjB8
# MQswCQYDVQQGEwJVUzETMBEGA1UECBMKV2FzaGluZ3RvbjEQMA4GA1UEBxMHUmVk
# bW9uZDEeMBwGA1UEChMVTWljcm9zb2Z0IENvcnBvcmF0aW9uMSYwJAYDVQQDEx1N
# aWNyb3NvZnQgVGltZS1TdGFtcCBQQ0EgMjAxMAITMwAAAgJ5UHQhFH24oQABAAAC
# AjAiBCAWYfYpTdX4n2PWIkndUwP1UqN5gpquHgfB74fiH5nR0TANBgkqhkiG9w0B
# AQsFAASCAgAOioT/Yr6bH3x7SQPB9HajCKgo6/vlE8AO+WRaBUjh+G7Ov/ASqEhb
# WFeKSWsMSmbAhdqpRhzjMj76ks651zgK4vTaXIwZoEaAfwwY0OuXWh/QeIjWQOwC
# iyut0pYQuwDqqLJ/d+nIjutpI1cW6f6iWV5gMWpJiZqje62X05lGGOsWSCgzTIWv
# 8u3IbTgtf9CEcB/qJ5lpIZp82arPOTNaMLFtEefUf2LlANEC9vr/V/rIePxhobBo
# uzPk1lT00kNDHkJMjlLWDbaeL4UHHgzmuJVXKZ1yPguIJWtG52kp8vasWuq695TW
# rrj4C1hfkv3gB+VVm5yUad8IfNIkxZdOI33oxjUiRM928weU8WvjCc0ihEM7CXqI
# KVIRC4DBUiTCVUnX3rTd7nIkUGHp/IACTRNYqFjGuNfXWidUTEanBAQ/kbrjb5/q
# ZRYZJj/koC5k+RXlLE/miUJROH8oYkCrJM7BA4fMFwF0AJvpy64CX1YfQL5dbByL
# bI/IRSHwGCINlnESJ6GUI+MEL+jTDXzK3/T0diYriJLjLtMHtWYMIZdHOrBrEFvF
# SxGHfKpMVfQpUsI/u3AUsxyIkds04US142yd6QJOobofMP8ZS1rqXtwJuzcJD2D8
# 5JMhGVRNkhZK9UBjg2bG+EqelB+HOKnYj5F1rT9IScqlfZLH9tl8lw==
# SIG # End signature block
