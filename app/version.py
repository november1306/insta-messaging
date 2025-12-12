"""
Application version information.

Version format: MAJOR.MINOR
- MAJOR: Breaking changes (0 for MVP/beta)
- MINOR: Incremented with each merged PR (0.1 → 0.2 → 0.3...)

Manual update process:
1. Before merging PR to main, update __version__ below
2. Commit: "chore: bump version to X.Y"
3. Merge PR

Version is displayed on server startup and in GET / endpoint.
"""

__version__ = "0.2"
