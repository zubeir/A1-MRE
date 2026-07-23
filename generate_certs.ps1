# Generate self-signed certificate for zubeir-ai-server
$certPath = ".\certs"

# Create certs directory if it doesn't exist
if (-not (Test-Path $certPath)) {
    New-Item -ItemType Directory -Path $certPath | Out-Null
    Write-Host "Created $certPath directory"
}

# Generate self-signed certificate
$cert = New-SelfSignedCertificate -DnsName zubeir-ai-server `
    -CertStoreLocation cert:\LocalMachine\My `
    -FriendlyName 'zubeir-ai-server-streamlit' `
    -NotAfter (Get-Date).AddYears(10) `
    -KeyExportPolicy Exportable

Write-Host "Certificate created with thumbprint: $($cert.Thumbprint)"

# Export as PFX (includes private key)
$pwd = ConvertTo-SecureString -String 'streamlit' -Force -AsPlainText
Export-PfxCertificate -Cert $cert `
    -FilePath "$certPath\zubeir-ai-server.pfx" `
    -Password $pwd | Out-Null

Write-Host "Exported PFX to $certPath\zubeir-ai-server.pfx"

# Also export just the certificate (public key) as CER for client trust
Export-Certificate -Cert $cert `
    -FilePath "$certPath\zubeir-ai-server.cer" | Out-Null

Write-Host "Exported CER to $certPath\zubeir-ai-server.cer"

# List the generated files
Write-Host "`nGenerated certificate files:"
Get-ChildItem $certPath

Write-Host "`nNext steps:"
Write-Host "1. Import the certificate into your browser/system trust store (optional, to avoid 'not secure' warning)"
Write-Host "2. Update your hosts file to map 10.0.0.79 to zubeir-ai-server"
Write-Host "3. Update .streamlit/config.toml with SSL configuration"
Write-Host "4. Restart the Streamlit server"
