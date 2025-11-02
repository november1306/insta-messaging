#!/usr/bin/env python3
"""
Custom PR review script using Claude API.
This script analyzes PR changes and posts review comments.

Usage:
    python claude-review.py --pr-number <PR_NUMBER>

Environment Variables:
    ANTHROPIC_API_KEY: Your Claude API key
    GITHUB_TOKEN: GitHub token for posting comments
    GITHUB_REPOSITORY: Repository name (owner/repo)
"""
import os
import sys
import json
import argparse
from typing import List, Dict
import requests


def get_pr_diff(repo: str, pr_number: int, github_token: str) -> str:
    """Fetch the PR diff from GitHub."""
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3.diff"
    }
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.text


def get_pr_files(repo: str, pr_number: int, github_token: str) -> List[Dict]:
    """Get list of changed files in the PR."""
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/files"
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def review_with_claude(diff: str, files: List[Dict], api_key: str) -> str:
    """Send diff to Claude for review using the official Anthropic client."""
    from anthropic import Anthropic
    
    client = Anthropic(api_key=api_key)
    
    file_list = "\n".join([f"- {f['filename']} ({f['status']})" for f in files])
    
    prompt = f"""You are an expert code reviewer for an Instagram Messenger Automation system. Review the following pull request changes.

**Project Context:**
- Multi-account Instagram messaging automation system
- Built with FastAPI and MySQL
- All operations must be account-scoped (require account_id parameter)
- Uses interfaces (IMessageSender, IMessageReceiver, etc.) not direct implementations
- Credentials stored encrypted in MySQL database
- Follows async/await patterns

Changed Files:
{file_list}

Diff:
```diff
{diff[:10000]}  # Increased limit for better context
```

Please provide a thorough code review focusing on:
1. **Security Issues**: Credential exposure, SQL injection, authentication bypass
2. **Account Isolation**: Ensure all operations are properly scoped to accounts
3. **Bugs**: Logic errors, async/await issues, potential runtime issues
4. **Performance**: Database queries, async operations, bottlenecks
5. **Best Practices**: FastAPI patterns, Pydantic models, type hints
6. **Architecture**: Interface usage, separation of concerns, domain models
7. **Testing**: Missing test coverage, test quality improvements
8. **Error Handling**: Webhook responses (always 200), internal error handling

Format your response as:
## Summary
[Brief overview with change count and risk assessment]

## Issues Found
[List specific issues with file:line references if any]

## Suggestions
[Improvement suggestions if any]

## Approval Status
[APPROVE / REQUEST_CHANGES / COMMENT with reasoning]
"""
    
    message = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )
    
    return message.content[0].text


def post_review_comment(
    repo: str,
    pr_number: int,
    review_body: str,
    github_token: str
) -> None:
    """Post the review as a PR comment."""
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    comment_body = f"""## 🤖 AI Code Review (Claude)

{review_body}

---
*This review was automatically generated using Claude AI. Please verify all suggestions.*
"""
    
    data = {"body": comment_body}
    
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    print(f"✅ Review posted successfully to PR #{pr_number}")


def main():
    parser = argparse.ArgumentParser(description="AI Code Review using Claude")
    parser.add_argument("--pr-number", type=int, required=True, help="Pull request number")
    args = parser.parse_args()
    
    # Get environment variables
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
    github_token = os.getenv("GITHUB_TOKEN")
    repo = os.getenv("GITHUB_REPOSITORY")
    
    if not all([anthropic_api_key, github_token, repo]):
        print("❌ Error: Missing required environment variables")
        print("Required: ANTHROPIC_API_KEY, GITHUB_TOKEN, GITHUB_REPOSITORY")
        sys.exit(1)
    
    try:
        print(f"📥 Fetching PR #{args.pr_number} from {repo}...")
        diff = get_pr_diff(repo, args.pr_number, github_token)
        files = get_pr_files(repo, args.pr_number, github_token)
        
        print(f"🔍 Analyzing {len(files)} changed files...")
        review = review_with_claude(diff, files, anthropic_api_key)
        
        print("💬 Posting review comment...")
        post_review_comment(repo, args.pr_number, review, github_token)
        
        print("✨ Code review complete!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
