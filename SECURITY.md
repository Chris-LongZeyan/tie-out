# Security Policy

## Supported versions

Security fixes are provided for the [latest published release](https://github.com/Chris-LongZeyan/tie-out/releases/latest), currently **v0.1.0**. Older releases do not receive separate security backports; upgrade to the latest release when a fix is available. The `main` branch is under development and is not a stable release.

Reports affecting any version are welcome, especially if the issue can also be reproduced on the latest release or `main`.

## Report a vulnerability privately

Use [GitHub's private vulnerability reporting form](https://github.com/Chris-LongZeyan/tie-out/security/advisories/new). You must be signed in to GitHub. Reports are shared privately with the repository's maintainers through GitHub Security Advisories.

Do not disclose an unpatched vulnerability in a public issue, discussion, or pull request. For ordinary bugs without a security impact, use the [bug report template](https://github.com/Chris-LongZeyan/tie-out/issues/new?template=bug_report.md).

Include the following information when available:

- The affected release or commit, Python version, operating system, and relevant dependency versions.
- A description of the vulnerability, its impact, and any prerequisites for exploitation.
- Minimal reproduction steps or a proof of concept using synthetic data.
- The affected command, input format, or report output, with sensitive details removed.
- Any suggested mitigation or fix.

Do not attach credentials, connection strings, customer data, or private database exports. Use synthetic fixtures and redact logs and screenshots. Test only against systems and data you are authorized to use.

## Response and disclosure

The maintainer will review reports, request any information needed to reproduce the issue, and discuss remediation through the private advisory. This is a volunteer-maintained project; response and resolution times are not guaranteed.

Please coordinate public disclosure with the maintainer so users can receive a fix or mitigation first. Confirmed vulnerabilities may be documented in a security advisory and release notes. Reporter credit will be discussed before publication.

## Security considerations

- **SQL Server permissions:** Use a database account with only the read permissions needed for reconciliation. The SQL query guard is an input check, not a security boundary; enforce access restrictions in SQL Server.
- **Sensitive reports:** HTML reports contain sampled record keys and values. Aggregate summaries can still reveal column names and statistics. Store and share outputs according to the sensitivity of the source data.
- **Untrusted inputs:** Input files are processed locally and datasets must fit in memory. Use appropriate resource limits when processing files from untrusted sources.
- **Dependencies:** Keep Python, optional Python packages, and the Microsoft ODBC driver updated within the project's supported requirements.

For community conduct concerns, use the reporting contact in the [Code of Conduct](CODE_OF_CONDUCT.md).
