# Claude Code PR Review Setup Guide

This repository is configured to automatically review pull requests using Claude Code.

## Workflows Configured

### Claude Code PR Review (`.github/workflows/claude-pr-review.yml`)
- **Triggers**: When PRs are opened, updated, or reopened targeting `main` or `develop` branches
- **Action**: Claude Code reviews the PR and posts detailed feedback as comments
- **Model**: Claude Sonnet 4 (high-quality, balanced performance)

## Required Setup

### Step 1: Add Anthropic API Key to GitHub Secrets

1. **Get your Anthropic API Key**:
   - Go to https://console.anthropic.com/settings/keys
   - Create a new API key if you don't have one
   - Copy the key (starts with `sk-ant-`)

2. **Add the secret to GitHub**:
   - Go to your repository: https://github.com/november1306/insta-messaging/settings/secrets/actions
   - Click **"New repository secret"**
   - Name: `ANTHROPIC_API_KEY`
   - Value: Paste your API key (e.g., `sk-ant-api03-...`)
   - Click **"Add secret"**

### Step 2: Enable Automatic Branch Deletion

To automatically delete branches after PRs are merged:

1. Go to your repository settings: https://github.com/november1306/insta-messaging/settings
2. Scroll down to the **"Pull Requests"** section
3. Check the box: **"Automatically delete head branches"**
4. This will delete ANY branch after a successful merge

### Step 3: Verify Workflow Permissions

The workflows are already configured with the correct permissions:
- `GITHUB_TOKEN` is automatically provided by GitHub Actions
- No additional token configuration needed

## Testing the Setup

### Test PR Review Workflow

1. Create a new branch:
   ```bash
   git checkout -b test/pr-review-setup
   ```

2. Make a small change:
   ```bash
   echo "# Test PR Review" >> test.md
   git add test.md
   git commit -m "test: Verify PR review workflow"
   ```

3. Push and create a PR:
   ```bash
   git push -u origin test/pr-review-setup
   gh pr create --title "Test: PR Review Workflow" --body "Testing Claude Code PR review"
   ```

4. Check the PR:
   - Go to the PR page on GitHub
   - Check the "Actions" tab to see the workflow running
   - Claude Code will post review comments within a few minutes

## Review Configuration

### Current Settings

- **Model**: `claude-sonnet-4` - Best balance of quality and speed
- **Review Level**: `detailed` - Comprehensive code analysis
- **Auto Comment**: `true` - Automatically posts reviews as PR comments

### What Claude Code Reviews

Claude Code will analyze:
- **Code Quality**: Best practices, patterns, maintainability
- **Security**: Vulnerabilities, authentication issues, data handling
- **Performance**: Async patterns, database queries, API calls
- **Python/FastAPI Specific**: FastAPI conventions, async/await usage
- **Logic**: Potential bugs, edge cases, error handling
- **Documentation**: Code clarity, missing comments

## Customization

### Adjust Review Triggers

Edit `.github/workflows/claude-pr-review.yml` to change when reviews run:

```yaml
on:
  pull_request:
    types: [opened, synchronize, reopened]
    branches:
      - main
      - develop
      - feature/*  # Add more branch patterns
```

### Change Review Model

Available models:
- `claude-sonnet-4` (recommended) - Best quality
- `claude-sonnet-3-5` - Good balance
- `claude-haiku-3-5` - Fastest, lower cost

### Disable Auto-Comments

Set `auto-comment: false` if you want to review Claude's feedback before posting.

## Troubleshooting

### Workflow Fails with "Unauthorized"
- Check that `ANTHROPIC_API_KEY` secret is set correctly
- Verify the API key is valid and has sufficient credits

### No Review Comments Appear
- Check the Actions tab for workflow run details
- Ensure the PR targets `main` or `develop` branch
- Verify workflow permissions are enabled in repository settings

## Cost Considerations

- Each PR review costs approximately $0.10-$0.50 depending on code size
- Reviews only run on PR creation and updates
- Monitor usage at https://console.anthropic.com/settings/usage

## Support

- Claude Code Documentation: https://docs.anthropic.com/claude-code
- GitHub Actions Logs: Check the Actions tab for detailed logs
- Anthropic Support: https://support.anthropic.com
