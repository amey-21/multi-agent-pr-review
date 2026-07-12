import os
from dotenv import load_dotenv
from src.github.client import GitHubClient

load_dotenv()  # reads .env file into environment variables

def test_fetch_pr():
    token = os.getenv("GITHUB_TOKEN")
    client = GitHubClient(token=token)
    
    # We'll use a real public repo for testing
    # torvalds/linux PR #1 is ancient but always there
    # Better: use one of your own repos with an open PR
    # For now let's use a well-known public repo
    pr_diff = client.get_pr_diff(
        repo_name="octocat/Hello-World",  
        pr_number=1
    )
    
    print(f"PR Title: {pr_diff.pr_title}")
    print(f"Author: {pr_diff.author}")
    print(f"Files changed: {len(pr_diff.files)}")
    print(f"\nPatch text preview:\n{pr_diff.get_patch_text()[:500]}")
    
    # basic assertions
    assert pr_diff.pr_number == 1
    assert len(pr_diff.files) > 0
    print("\n✅ GitHub client working correctly")

if __name__ == "__main__":
    test_fetch_pr()