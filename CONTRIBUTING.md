# Contributing

Contributions should preserve Tie-Out's comparison contract: exact key matching, decimal precision, documented missing-value handling, and separation of aggregate summaries from sampled report data.

## Repository structure

| Path | Purpose |
| --- | --- |
| `skills/tie-out/` | Complete installable Codex skill, runtime, references, and optional dependencies |
| `tests/` | Unit and regression tests; no live database required |
| `examples/` | Small synthetic CSV fixtures |
| `docs/` | User-facing usage and SQL Server guides |
| `evaluations/` | Optional benchmark and integration tests with dated results |
| `.github/workflows/` | Windows/Linux regression checks |

## Local checks

```sh
python -m pip install -r skills/tie-out/requirements.txt
python -m unittest discover -s tests -v
```

CI runs Python 3.10 and 3.13 on Windows and Linux. Live SQL acceptance and benchmark commands are documented in [evaluations/README.md](evaluations/README.md). Keep generated reports and virtual environments under ignored local directories.

## SonarQube Cloud

Connect this repository to a SonarQube Cloud project to enable analysis. Add a quality or reliability badge only after its endpoint reports results for this repository. Automatic analysis uses `.sonarcloud.properties`; a manually invoked scanner uses `sonar-project.properties`. Both classify the runtime as source code and the regression and evaluation scripts as test code. The frozen benchmark baseline is excluded from the analysis scope because it is retained solely for historical comparisons. See [SonarSource's configuration documentation](https://docs.sonarsource.com/sonarqube-cloud/analyzing-source-code/automatic-analysis#additional-analysis-configuration) for supported properties.

Before merging, review the GitHub Actions and SonarQube Cloud results for the proposed commit. If the quality gate fails, use the check's **Details** link to inspect the affected metric and issues. Local test results and remote analysis results are separate checks.

Automatic analysis does not import coverage reports. A migration to CI-based analysis requires configuring the scanner and disabling automatic analysis in the SonarCloud project settings.

## Change guidelines

- Include a minimal synthetic reproduction for a bug fix.
- Test changed behavior and preserve CLI exit-code semantics.
- Update the relevant user guide when flags or comparison rules change.
- Keep raw values out of aggregate summaries and credentials out of all output.
- Do not modify historical result snapshots to represent a new run. Record fresh evidence separately with its environment and limitations.

Bug reports should include the command, expected result, actual result, Python version, and a small synthetic fixture. Pull requests should explain the resulting behavior and validation performed.
