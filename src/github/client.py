from github import Github
from github import Auth
from src.github.models import PRDiff, FileChange


class GitHubClient:
    """
    Wrapper around PyGithub that speaks our domain language.
    
    Why a wrapper class instead of using PyGithub directly?
    - Isolates GitHub API details from the rest of our code
    - If GitHub changes their API, we only update this file
    - Easy to mock in tests (swap real GitHub for fake data)
    - Single place to add retry logic, rate limit handling, etc.
    """

    def __init__(self, token: str):
        """
        token: GitHub Personal Access Token
        We pass it in rather than reading from env here
        because this class shouldn't care where the token comes from.
        (Separation of concerns)
        """
        auth = Auth.Token(token)
        self.client = Github(auth=auth)

    def get_pr_diff(self, repo_name: str, pr_number: int) -> PRDiff:
        """
        Fetches a PR and returns it as our PRDiff model.
        
        repo_name: "username/repo-name" e.g. "amey/my-project"
        pr_number: the PR number shown on GitHub
        
        Data flow:
        GitHub API → PyGithub objects → our PRDiff model
        """
        # Step 1: get the repository object
        repo = self.client.get_repo(repo_name)
        
        # Step 2: get the pull request object
        pr = repo.get_pull(pr_number)
        
        # Step 3: get all changed files
        files = []
        for github_file in pr.get_files():
            file_change = FileChange(
                filename=github_file.filename,
                status=github_file.status,
                additions=github_file.additions,
                deletions=github_file.deletions,
                patch=getattr(github_file, 'patch', None)
                # getattr with None fallback: binary files have no patch
            )
            files.append(file_change)
        
        # Step 4: assemble our PRDiff model
        return PRDiff(
            pr_number=pr.number,
            pr_title=pr.title,
            repo_name=repo_name,
            author=pr.user.login,
            base_branch=pr.base.ref,
            head_branch=pr.head.ref,
            description=pr.body or "",
            files=files
        )
    
    def post_review_comment(
        self, 
        repo_name: str, 
        pr_number: int, 
        comment: str
    ) -> None:
        """
        Posts a comment on the PR. 
        We'll use this in Milestone 6 to post agent findings.
        """
        repo = self.client.get_repo(repo_name)
        pr = repo.get_pull(pr_number)
        pr.create_issue_comment(comment)


    def get_pr_diff_stats(self, repo_name: str, pr_number: int) -> dict:
        """
        Returns a summary of the PR's changes without the full patch text.
        Useful for quick stats or logging.
        """
        pr_diff = self.get_pr_diff(repo_name, pr_number)
        total_additions = sum(f.additions for f in pr_diff.files)
        total_deletions = sum(f.deletions for f in pr_diff.files)
        return {
            "pr_number": pr_diff.pr_number,
            "pr_title": pr_diff.pr_title,
            "author": pr_diff.author,
            "total_files_changed": len(pr_diff.files),
            "total_additions": total_additions,
            "total_deletions": total_deletions
        }
    
    def detect_language(filename: str) -> str | None:
        extensions = {
            ".py": "Python",
            ".js": "JavaScript", 
            ".ts": "TypeScript",
            ".go": "Go",
            ".java": "Java",
            ".rs": "Rust",
        }
        suffix = "." + filename.rsplit(".", 1)[-1] if "." in filename else ""
        return extensions.get(suffix, None)