#!/usr/bin/env python3
"""Generate self-signed SSL certificate for zubeir-ai-server"""
import os
import subprocess
import sys

# Check if cryptography is available
try:
    from cryptography import x509
    from cryptography.x509.oid import NameOID, ExtensionOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.backends import default_backend
    from datetime import datetime, timedelta
    import ipaddress
except ImportError:
    print("Installing cryptography package...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "cryptography"])
    from cryptography import x509
    from cryptography.x509.oid import NameOID, ExtensionOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.backends import default_backend
    from datetime import datetime, timedelta
    import ipaddress

# Create certs directory
os.makedirs("certs", exist_ok=True)

# Generate private key
print("Generating private key...")
private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
    backend=default_backend()
)

# Build certificate subject and issuer
subject = issuer = x509.Name([
    x509.NameAttribute(NameOID.COMMON_NAME, "zubeir-ai-server"),
])

# Create certificate
print("Creating certificate...")
cert = x509.CertificateBuilder().subject_name(
    subject
).issuer_name(
    issuer
).public_key(
    private_key.public_key()
).serial_number(
    x509.random_serial_number()
).not_valid_before(
    datetime.utcnow()
).not_valid_after(
    datetime.utcnow() + timedelta(days=3650)  # 10 years
).add_extension(
    x509.SubjectAlternativeName([
        x509.DNSName("zubeir-ai-server"),
        x509.DNSName("localhost"),
        x509.IPAddress(ipaddress.IPv4Address("10.0.0.79")),
        x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
    ]),
    critical=False,
).add_extension(
    x509.BasicConstraints(ca=False, path_length=None),
    critical=True,
).sign(private_key, hashes.SHA256(), default_backend())

# Write certificate to file
with open("certs/zubeir-ai-server.crt", "wb") as f:
    f.write(cert.public_bytes(serialization.Encoding.PEM))
    print("Certificate saved to certs/zubeir-ai-server.crt")

# Write private key to file
with open("certs/zubeir-ai-server.key", "wb") as f:
    f.write(private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption()
    ))
    print("Private key saved to certs/zubeir-ai-server.key")

print("\nCertificate details:")
print(f"  CN: zubeir-ai-server")
print(f"  IP: 10.0.0.79")
print(f"  Valid for: 10 years")
print(f"\nFiles generated:")
for f in os.listdir("certs"):
    path = os.path.join("certs", f)
    size = os.path.getsize(path)
    print(f"  {path} ({size} bytes)")

print("\nNext steps:")
print("1. Update .streamlit/config.toml with SSL configuration")
print("2. Update your hosts file: 10.0.0.79 zubeir-ai-server")
print("3. Import certs/zubeir-ai-server.crt into browser trust store (to remove 'not secure')")
print("4. Restart the Streamlit server")
