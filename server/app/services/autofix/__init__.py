"""Error-repair agent: catch errors while the app runs (development only), let Claude Code
propose a tested fix in a separate git worktree, and push it only after an admin approves.

capture.py  records and de-duplicates errors (secrets removed)
agent.py    worktree, agent rounds, checks, review, approve / reject
review.py   deterministic risk scan of the diff
"""
