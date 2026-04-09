import httpx
import asyncio
from datetime import datetime
from app.core.config import settings


# github api

async def fetch_open_prs(owner: str, repo: str, access_token: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{settings.GITHUB_API_URL}/repos/{owner}/{repo}/pulls",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"state": "open", "per_page": 100},
        )
    return resp.json() if resp.status_code == 200 else []


async def fetch_commits(
    owner: str, repo: str, access_token: str,
    since_iso: str, until_iso: str,
) -> list[dict]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{settings.GITHUB_API_URL}/repos/{owner}/{repo}/commits",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"since": since_iso, "until": until_iso, "per_page": 100},
        )
    return resp.json() if resp.status_code == 200 else []


async def fetch_contributors(owner: str, repo: str, access_token: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{settings.GITHUB_API_URL}/repos/{owner}/{repo}/contributors",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"per_page": 10},
        )
    return resp.json() if resp.status_code == 200 else []


async def fetch_issues(
    owner: str, repo: str, access_token: str,
    since_iso: str,
) -> list[dict]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{settings.GITHUB_API_URL}/repos/{owner}/{repo}/issues",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"state": "all", "since": since_iso, "per_page": 100},
        )
    return resp.json() if resp.status_code == 200 else []


async def fetch_commit_files(
    owner: str, repo: str, sha: str, access_token: str
) -> list[str]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{settings.GITHUB_API_URL}/repos/{owner}/{repo}/commits/{sha}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if resp.status_code != 200:
        return []
    return [f["filename"] for f in resp.json().get("files", [])]


# helpers

def time_ago(dt_str: str) -> str:
    try:
        dt    = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        now   = datetime.now(dt.tzinfo)
        secs  = (now - dt).total_seconds()

        if secs < 3600:
            m = int(secs // 60)
            return f"{m} minute{'s' if m != 1 else ''} ago"
        if secs < 86400:
            h = int(secs // 3600)
            return f"{h} hour{'s' if h != 1 else ''} ago"
        d = int(secs // 86400)
        return f"{d} day{'s' if d != 1 else ''} ago"
    except Exception:
        return ""


def determine_complexity(change_count: int, bug_rate: int) -> str:
    if bug_rate > 20 or change_count > 40:
        return "high"
    if bug_rate > 10 or change_count > 20:
        return "medium"
    return "low"


def calculate_risk_score(
    open_prs:             int,
    bug_count:            int,
    total_commits:        int,
    high_complexity_files: int,
) -> int:
    score  = 0
    score += min(open_prs              * 5, 25)
    score += min(bug_count             * 3, 30)
    score += min(high_complexity_files * 8, 30)
    score -= min(total_commits         * 1, 15)
    return max(0, min(100, score))


# main

async def get_repo_intelligence(
    owner:        str,
    repo:         str,
    access_token: str,
    since:        str, 
    until:        str, 
) -> dict:

    since_dt  = datetime.strptime(since, "%Y-%m-%d")
    until_dt  = datetime.strptime(until, "%Y-%m-%d")
    since_iso = since_dt.isoformat() + "Z"
    until_iso = until_dt.isoformat() + "Z"

    # fetch in parallel
    prs, commits, contributors, issues = await asyncio.gather(
        fetch_open_prs(owner, repo, access_token),
        fetch_commits(owner, repo, access_token, since_iso, until_iso),
        fetch_contributors(owner, repo, access_token),
        fetch_issues(owner, repo, access_token, since_iso),
    )

    # metrics
    open_pr_count   = len(prs)
    total_commits   = len(commits)
    reviews_waiting = sum(1 for pr in prs if pr.get("requested_reviewers"))

    bug_issues = [
        i for i in issues
        if not i.get("pull_request")
        and any(
            l["name"].lower() in ["bug", "fix", "error"]
            for l in i.get("labels", [])
        )
    ]
    bug_count = len(bug_issues)

    bugs_this_week = sum(
        1 for i in bug_issues
        if (datetime.utcnow() - datetime.fromisoformat(
            i["created_at"].replace("Z", "")
        )).days <= 7
    )

    # contributors
    total_contribs = sum(c.get("contributions", 0) for c in contributors) or 1
    contributor_list = [
        {
            "name":       c.get("login", ""),
            "commits":    c.get("contributions", 0),
            "prs":        sum(
                1 for pr in prs
                if pr.get("user", {}).get("login") == c.get("login")
            ),
            "percentage": round(c.get("contributions", 0) / total_contribs * 100),
        }
        for c in contributors[:6]
    ]

    # recent activity
    activity = []

    for pr in prs[:3]:
        activity.append({
            "type":    "pr",
            "message": pr.get("title", ""),
            "file":    pr.get("head", {}).get("ref", ""),
            "timeAgo": time_ago(pr.get("created_at", "")),
        })

    for issue in bug_issues[:3]:
        activity.append({
            "type":    "bug",
            "message": issue.get("title", ""),
            "file":    "",
            "timeAgo": time_ago(issue.get("created_at", "")),
        })

    for commit in commits[:4]:
        activity.append({
            "type":    "commit",
            "message": commit.get("commit", {}).get("message", "").split("\n")[0][:80],
            "file":    commit.get("commit", {}).get("author", {}).get("name", ""),
            "timeAgo": time_ago(
                commit.get("commit", {}).get("author", {}).get("date", "")
            ),
        })

    activity = activity[:8]

    # module health 
    file_change_count: dict[str, int] = {}
    for commit in commits[:20]:
        files = await fetch_commit_files(owner, repo, commit["sha"], access_token)
        for f in files:
            file_change_count[f] = file_change_count.get(f, 0) + 1

    file_bug_count: dict[str, int] = {}
    for issue in bug_issues:
        body = (issue.get("body") or "").lower()
        for f in file_change_count:
            if f.split("/")[-1].lower() in body:
                file_bug_count[f] = file_bug_count.get(f, 0) + 1

    modules = []
    for path, change_count in sorted(
        file_change_count.items(), key=lambda x: -x[1]
    )[:8]:
        bugs_for_file = file_bug_count.get(path, 0)
        bug_rate      = min(round(bugs_for_file / max(bug_count, 1) * 100), 100)
        complexity    = determine_complexity(change_count, bug_rate)
        last_commit   = commits[0] if commits else None

        modules.append({
            "name":        path.split("/")[-1],
            "path":        "/".join(path.split("/")[:-1]) + "/" if "/" in path else "",
            "bugRate":     bug_rate,
            "complexity":  complexity,
            "lastChanged": time_ago(
                last_commit["commit"]["author"]["date"]
            ) if last_commit else "",
            "changeCount": change_count,
        })

    # bug hotspots
    hotspot_files        = sorted(file_bug_count.items(), key=lambda x: -x[1])[:5]
    total_bugs_in_files  = sum(v for _, v in hotspot_files) or 1
    hotspots = [
        {
            "file":       path.split("/")[-1],
            "bugCount":   count,
            "percentage": round(count / total_bugs_in_files * 100),
        }
        for path, count in hotspot_files
    ]

    # risk score
    high_complexity = sum(1 for m in modules if m["complexity"] == "high")
    risk_score      = calculate_risk_score(
        open_pr_count, bug_count, total_commits, high_complexity
    )
    risk_label = (
        "High risk"   if risk_score > 66 else
        "Medium risk" if risk_score > 33 else
        "Low risk"
    )

    return {
        "metrics": {
            "totalBugs":      bug_count,
            "bugsThisWeek":   bugs_this_week,
            "openPrs":        open_pr_count,
            "reviewsWaiting": reviews_waiting,
            "totalCommits":   total_commits,
            "riskScore":      risk_score,
            "riskLabel":      risk_label,
        },
        "modules":      modules,
        "hotspots":     hotspots,
        "activity":     activity,
        "contributors": contributor_list,
    }