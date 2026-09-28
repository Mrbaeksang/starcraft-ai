# GitHub repository setup

Most project content is automated in the repository itself.

A few GitHub settings require repository **Administration write** permission and cannot be changed by ordinary contents-only automation.

Run once from a machine where GitHub CLI is authenticated as the repository owner:

```bash
bash scripts/bootstrap_github_repo.sh
```

The script configures:

- About description;
- homepage URL;
- repository topics;
- Issues / Discussions;
- merge strategy;
- automatic source-branch deletion after merge;
- lightweight protection on `main` against force-push/deletion;
- project labels;
- GitHub Pages using the repository's Pages workflow.

It intentionally does not require pull requests for every main-branch change yet because trusted GitHub Actions currently commit `uv.lock` to main.

After the automation design stabilizes, stricter required-status-check rules can be added.
