# Regula Health - Security Advisory

## Vulnerability Fixes - January 16, 2026

### Summary
Four security vulnerabilities were identified in third-party dependencies and have been patched by upgrading to the latest secure versions.

### Vulnerabilities Fixed

#### 1. cryptography - NULL Pointer Dereference (CVE-TBD)
**Severity:** HIGH  
**Component:** cryptography  
**Affected Version:** 42.0.0  
**Fixed Version:** 42.0.4  
**Description:** NULL pointer dereference with `pkcs12.serialize_key_and_certificates` when called with a non-matching certificate and private key and an hmac_hash override.  
**Impact:** Potential denial of service (application crash)  
**Remediation:** Upgraded to cryptography 42.0.4

#### 2. FastAPI - Content-Type Header ReDoS
**Severity:** MEDIUM  
**Component:** fastapi  
**Affected Version:** 0.109.0  
**Fixed Version:** 0.109.1  
**Description:** Regular expression denial of service (ReDoS) vulnerability in Content-Type header parsing.  
**Impact:** Potential denial of service through malicious Content-Type headers  
**Remediation:** Upgraded to fastapi 0.109.1

#### 3. python-multipart - Malformed multipart/form-data DoS
**Severity:** HIGH  
**Component:** python-multipart  
**Affected Version:** 0.0.6  
**Fixed Version:** 0.0.18  
**Description:** Denial of service via deformation of `multipart/form-data` boundary.  
**Impact:** Potential denial of service through malformed file uploads  
**Remediation:** Upgraded to python-multipart 0.0.18

#### 4. python-multipart - Content-Type Header ReDoS
**Severity:** MEDIUM  
**Component:** python-multipart  
**Affected Version:** 0.0.6  
**Fixed Version:** 0.0.7 (using 0.0.18 which includes this fix)  
**Description:** ReDoS vulnerability in Content-Type header parsing.  
**Impact:** Potential denial of service through malicious Content-Type headers  
**Remediation:** Upgraded to python-multipart 0.0.18

### Actions Taken

1. ✅ Updated `backend/requirements.txt` with patched versions
2. ✅ Verified all dependencies are now at secure versions
3. ✅ Documented vulnerabilities and fixes in this advisory

### Deployment Instructions

For existing deployments, update dependencies immediately:

```bash
# Pull latest changes
git pull

# Rebuild Docker image
docker-compose build backend

# Restart services
docker-compose up -d backend

# Or for local development
cd backend
pip install -r requirements.txt --upgrade
```

### Verification

After updating, verify the installed versions:

```bash
pip list | grep -E "cryptography|fastapi|python-multipart"
```

Expected output:
```
cryptography      42.0.4
fastapi           0.109.1
python-multipart  0.0.18
```

### Risk Assessment

**Before Fix:**
- HIGH risk of DoS attacks via malformed file uploads
- HIGH risk of application crashes via cryptography exploit
- MEDIUM risk of ReDoS attacks via Content-Type headers

**After Fix:**
- ✅ All known vulnerabilities patched
- ✅ No remaining security alerts
- ✅ Production-ready security posture

### Additional Security Recommendations

While these vulnerabilities have been fixed, we recommend:

1. **Continuous Monitoring:** 
   - Subscribe to security advisories for all dependencies
   - Run `pip-audit` regularly to detect new vulnerabilities
   - Enable GitHub Dependabot alerts

2. **Production Hardening:**
   - Implement rate limiting on file upload endpoints
   - Set maximum file size limits (currently 50MB)
   - Add WAF (Web Application Firewall) rules
   - Monitor for unusual traffic patterns

3. **Regular Updates:**
   - Schedule monthly dependency updates
   - Test updates in staging before production
   - Maintain security patch SLA (< 24 hours for critical)

### Contact

For security concerns, contact: security@regula.health

**Do not create public GitHub issues for security vulnerabilities.**

---

**Last Updated:** January 16, 2026  
**Status:** ✅ ALL VULNERABILITIES PATCHED
