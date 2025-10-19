# Security Guidelines

## 🚨 NEVER DO - Critical Security Rules

### ❌ NEVER Commit API Keys

**NEVER push or commit:**
- API keys (Google Places, OpenAI, Anthropic, Yelp, etc.)
- Access tokens or authentication credentials
- `.env` files containing secrets
- Any files with hardcoded credentials

**WHY:** API keys are sensitive credentials that can be abused if exposed publicly. Bots actively scan GitHub for exposed keys within minutes of commits.

**WHAT TO DO:**
- ✅ Store ALL API keys in `.env` file only
- ✅ Ensure `.env` is in `.gitignore`
- ✅ Use `[REDACTED]` or `[YOUR_API_KEY_HERE]` in documentation
- ✅ If accidentally committed, revoke the key immediately and force push to remove from history

**Example of SAFE documentation:**
```markdown
### API Used:
- **Service:** Google Places API (New)
- **API Key:** [STORED IN .env FILE]
```

---

### ❌ NEVER Commit Business Lead Data

**NEVER push or commit:**
- CSV files containing real business information
- Lead lists with contact details (phone numbers, emails, addresses)
- Enriched data files with PII (Personally Identifiable Information)
- Client prospect lists or business intelligence data

**WHY:**
- **Privacy:** Business contact information is private data that should not be publicly accessible
- **Compliance:** May violate privacy laws (GDPR, PIPEDA, CASL)
- **Competitive Risk:** Exposing your lead generation results to competitors
- **Ethical:** Businesses did not consent to their information being publicly shared

**PROTECTED FILES (already in .gitignore):**
- `data/*.csv` - All CSV lead files
- `data/*LEADS*.md` - Lead summary reports
- `data/*ENRICHED*.csv` - Enriched business data
- `outputs/` - Generated outputs directory

**WHAT TO DO:**
- ✅ Keep all lead data in `/data` directory (gitignored)
- ✅ Use sample/dummy data for testing and documentation
- ✅ Share lead data only via secure private channels (encrypted email, secure file sharing)
- ✅ Never reference actual business names/contacts in commit messages or code comments

**Example of SAFE test data:**
```csv
Business Name,Phone,Email
Example Corp,(555) 123-4567,contact@example.com
Sample Business,(555) 987-6543,info@sample.com
```

---

## 🛡️ If You Accidentally Commit Sensitive Data

### For API Keys:

1. **REVOKE THE KEY IMMEDIATELY**
   - Go to the API provider's console
   - Delete or regenerate the exposed key
   - Assume it's compromised - even if only exposed for seconds

2. **Remove from Git History:**
   ```bash
   # Edit the file to remove the key
   git add <file>
   git commit --amend --no-edit
   git push --force origin main
   ```

3. **Generate New Key:**
   - Create a fresh API key
   - Add to `.env` file
   - Test your application

### For Business Lead Data:

1. **Remove from Git History:**
   ```bash
   # Remove the sensitive file
   git rm --cached data/sensitive_file.csv
   git commit --amend --no-edit
   git push --force origin main
   ```

2. **Verify .gitignore:**
   ```bash
   # Check that data files are properly ignored
   cat .gitignore | grep data/
   ```

3. **Notify Stakeholders:**
   - If customer or private business data was exposed, consider legal/compliance requirements
   - Document the incident

---

## ✅ Security Best Practices

### Environment Variables
- Use `.env` for ALL sensitive configuration
- Never commit `.env` - only `.env.example`
- Document required variables in `.env.example` with placeholder values

### Git Hygiene
- Review changes before committing: `git diff`
- Check status: `git status`
- Use `.gitignore` proactively
- Never use `git add .` without reviewing first

### Data Protection
- Encrypt sensitive local files
- Use secure file sharing for lead data (not GitHub)
- Regularly rotate API keys
- Limit API key permissions to minimum required

### Code Review
- Review commit history for leaked secrets: `git log -p`
- Use tools like `git-secrets` or `gitleaks` to scan for sensitive data
- Enable GitHub's secret scanning alerts

---

## 📚 Additional Resources

- [GitHub: Removing sensitive data from a repository](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)
- [OWASP: Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
- [Canada's PIPEDA Privacy Law](https://www.priv.gc.ca/en/privacy-topics/privacy-laws-in-canada/the-personal-information-protection-and-electronic-documents-act-pipeda/)

---

## 🆘 Emergency Contact

If you discover a security incident:
1. Stop committing immediately
2. Follow the remediation steps above
3. Document what was exposed and for how long
4. Consider rotating all potentially compromised credentials
