import json
import httpx
from langchain_groq import ChatGroq
from langchain_core.output_parsers import StrOutputParser
from app.core.config import settings
from app.core.constants import EXCLUDE_PATTERNS, TESTABLE_EXTENSIONS
from app.core.prompts import (
    TEAM_CODEBASE_PROMPT, TEAM_PR_REVIEW_PROMPT,
    TEAM_VALIDATOR_PROMPT, TEAM_AGGREGATOR_PROMPT,
)
from app.models.embedding import CodeEmbedding
from app.services.agents.indexer import get_embedding, index_repo
from app.services.agents.pr_review import fetch_pr_diff
from app.services.agents.documentation import generate_documentation
from app.services.agents.test_generator import generate_tests
from app.services.repo_service import fetch_all_repo_files

llm = ChatGroq(
    model_name="llama-3.3-70b-versatile",
    temperature=0,
    api_key=settings.GROQ_API_KEY,
)

def clean_json(raw: str) -> dict:
    cleaned = raw.strip().replace("```json", "").replace("```", "").strip()
    return json.loads(cleaned)


# supervisor node

def supervisor_node(state: dict) -> dict:
    remaining = [a for a in state["selected_agents"] if a not in state["completed"]]
    if not remaining:
        return {**state, "current_agent": "aggregator"}
    return {**state, "current_agent": remaining[0], "retry_count": 0}


# agent nodes

async def _codebase(state: dict, db, user_id: int) -> dict:
    try:
        repo_full = state["repo"]

        count = db.query(CodeEmbedding).filter(
            CodeEmbedding.user_id == user_id,
            CodeEmbedding.repo    == repo_full,
        ).count()

        if count == 0:
            await index_repo(
                owner        = state["owner"],
                repo         = state["repo_name"],
                db           = db,
                user_id      = user_id,
                access_token = state["access_token"],
            )

        query_vector = get_embedding("query: code quality architecture structure")
        results = (
            db.query(CodeEmbedding)
            .filter(
                CodeEmbedding.user_id == user_id,
                CodeEmbedding.repo    == repo_full,
            )
            .order_by(CodeEmbedding.embedding.cosine_distance(query_vector))
            .limit(8)
            .all()
        )

        context       = "\n\n".join([f"# {r.file_path}\n{r.chunk_text[:1000]}" for r in results])
        file_list_str = "\n".join({r.file_path for r in results})
        file_count    = len(file_list_str.splitlines())
        chain         = TEAM_CODEBASE_PROMPT | llm | StrOutputParser()

        try:
            raw    = chain.invoke({"repo": repo_full, "file_list": file_list_str, "context": context})
            result = clean_json(raw)
        except json.JSONDecodeError:
            try:
                raw    = chain.invoke({"repo": repo_full, "file_list": file_list_str, "context": context[:3000]})
                result = clean_json(raw)
            except Exception:
                result = {"score": 50, "summary": "Codebase analyzed but could not parse detailed results.", "actions": [], "issues": []}
        except Exception as e:
            result = {"score": 0, "summary": f"Error: {str(e)}", "actions": [], "issues": []}

        # summary zenginleştir
        if result and not result["summary"].startswith("Error"):
            issues = result.get("issues", [])
            high   = [i for i in issues if i.get("severity") == "high"]
            medium = [i for i in issues if i.get("severity") == "medium"]
            score  = result.get("score", 0)

            issue_str = (
                f"{len(high)} critical · {len(medium)} medium issues found."
                if issues else "No major issues detected."
            )
            result["summary"] = (
                f"Analyzed {file_count} key files in `{repo_full}`. "
                f"Code quality score: {score}/100. {issue_str} "
                + result.get("summary", "")
            )

    except Exception as e:
        result = {"score": 0, "summary": f"Error: {str(e)}", "actions": [], "issues": []}

    return {**state, "results": {**state.get("results", {}), "codebase": result}}


async def _pr_review(state: dict) -> dict:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{settings.GITHUB_API_URL}/repos/{state['owner']}/{state['repo_name']}/pulls",
                headers={"Authorization": f"Bearer {state['access_token']}"},
                params={"state": "open", "per_page": 5},
            )
        prs = resp.json() if resp.status_code == 200 else []

        pr_list = "\n".join([f"PR #{p['number']}: {p['title']}" for p in prs]) or "No open PRs"

        diffs = []
        for pr in prs[:3]:
            try:
                diff = await fetch_pr_diff(
                    access_token = state["access_token"],
                    owner        = state["owner"],
                    repo         = state["repo_name"],
                    pr_number    = pr["number"],
                )
                diffs.append(f"## PR #{pr['number']}: {pr['title']}\n{diff[:2000]}")
            except Exception:
                continue

        chain = TEAM_PR_REVIEW_PROMPT | llm | StrOutputParser()
        try:
            raw    = chain.invoke({
                "repo":    state["repo"],
                "pr_list": pr_list,
                "diffs":   "\n\n".join(diffs) or "No diffs available",
            })
            result = clean_json(raw)

            # summary zenginleştir
            if result and not result["summary"].startswith("Error"):
                pr_count = result.get("pr_count", len(prs))
                issues   = result.get("issues", [])
                high     = [i for i in issues if i.get("severity") == "high"]
                score    = result.get("score", 0)

                if pr_count == 0:
                    result["summary"] = (
                        f"No open pull requests in `{state['repo']}`. "
                        f"Repository is clean and ready for development. Score: {score}/100."
                    )
                else:
                    result["summary"] = (
                        f"{pr_count} open PR(s) reviewed in `{state['repo']}`. "
                        f"Risk score: {score}/100. "
                        + (f"{len(high)} critical issue(s) found. " if high else "No critical issues. ")
                        + result.get("summary", "")
                    )

        except json.JSONDecodeError:
            result = {
                "score":    80,
                "summary":  f"{len(prs)} PR(s) reviewed but could not parse detailed results.",
                "actions":  [],
                "issues":   [],
                "pr_count": len(prs),
            }

    except Exception as e:
        result = {"score": 0, "summary": f"Error: {str(e)}", "actions": [], "issues": [], "pr_count": 0}

    return {**state, "results": {**state.get("results", {}), "pr_review": result}}


async def _test(state: dict, db, user_id: int) -> dict:
    try:
        file_list = await fetch_all_repo_files(
            access_token = state["access_token"],
            owner        = state["owner"],
            repo         = state["repo_name"],
        )

        # filter testable files
        testable = [
            f for f in file_list
            if any(f.endswith(e) for e in TESTABLE_EXTENSIONS)
            and not any(x in f for x in EXCLUDE_PATTERNS)
        ]

        # priority files
        priority_patterns = [
            "routes/", "routers/", "services/", "service/",
            "controllers/", "handlers/", "pages/", "components/",
        ]

        priority = [
            f for f in testable
            if any(p in f for p in priority_patterns)
        ][:2]

        # complete to 2 files if priority is less than 2
        if len(priority) < 2:
            rest     = [f for f in testable if f not in priority]
            priority += rest[:2 - len(priority)]

        selected = priority or testable[:2]

        if not selected:
            return {**state, "results": {**state.get("results", {}), "test": {
                "score":      0,
                "summary":    "No testable files found in the repository after filtering config and spec files.",
                "actions":    ["Add source files with testable logic"],
                "tests":      [],
                "test_count": 0,
                "coverage":   0,
            }}}

        framework = "pytest" if any(f.endswith(".py") for f in selected) else "jest"

        all_tests         = []
        total_coverage    = 0
        total_unit        = 0
        total_edge        = 0
        total_integration = 0
        tested_files      = []

        for file in selected:
            try:
                tr = await generate_tests(
                    target       = file,
                    owner        = state["owner"],
                    repo         = state["repo_name"],
                    user_id      = user_id,
                    framework    = framework,
                    access_token = state["access_token"],
                    db           = db,
                )
                all_tests         += tr.get("tests", [])
                total_coverage    += tr.get("coverage", 0)
                total_unit        += tr.get("unitCount", 0)
                total_edge        += tr.get("edgeCount", 0)
                total_integration += tr.get("integrationCount", 0)
                tested_files.append(file)
            except Exception:
                continue

        if not tested_files:
            return {**state, "results": {**state.get("results", {}), "test": {
                "score":      0,
                "summary":    "Test generation failed for all selected files.",
                "actions":    [],
                "tests":      [],
                "test_count": 0,
                "coverage":   0,
            }}}

        avg_coverage = total_coverage // len(tested_files)
        files_str    = "`, `".join(tested_files)

        result = {
            "score":      min(avg_coverage, 100),
            "summary":    (
                f"{len(all_tests)} tests generated for {len(tested_files)} file(s) "
                f"(`{files_str}`). "
                f"Framework: {framework}. "
                f"Breakdown: {total_unit} unit · {total_edge} edge · {total_integration} integration. "
                f"Avg estimated coverage: {avg_coverage}%."
            ),
            "test_count": len(all_tests),
            "coverage":   avg_coverage,
            "actions":    [
                f"Run: {'pytest' if framework == 'pytest' else 'npx jest'}",
                *[f"Generate tests for {f}" for f in testable if f not in tested_files][:3],
            ],
            "tests": all_tests,
        }

    except Exception as e:
        result = {
            "score":      0,
            "summary":    f"Error: {str(e)}",
            "actions":    [],
            "tests":      [],
            "test_count": 0,
            "coverage":   0,
        }

    return {**state, "results": {**state.get("results", {}), "test": result}}


async def _doc(state: dict, db, user_id: int) -> dict:
    try:
        doc_result = await generate_documentation(
            target       = state["repo"],
            owner        = state["owner"],
            repo         = state["repo_name"],
            user_id      = user_id,
            doc_type     = "readme",
            access_token = state["access_token"],
            db           = db,
        )

        markdown = doc_result.get("markdown", "")

        features = [
            line.lstrip("*- ").strip()
            for line in markdown.splitlines()
            if line.strip().startswith(("*", "-")) and 5 < len(line.strip()) < 80
        ][:4]

        feature_str = " · ".join(features) if features else "project overview"

        result = {
            "score":          80,
            "summary":        (
                f"README generated for `{state['repo']}`. "
                f"Covers: {feature_str}. "
                f"Includes tech stack, environment variables, installation steps, and project structure."
            ),
            "docs_generated": 1,
            "actions":        [
                "Review and publish generated README.md to repository root",
                "Add API endpoint documentation",
                "Add contributing guide and code of conduct",
            ],
            "docs": [{"type": "readme", "title": "README", "content": markdown}],
        }

    except Exception as e:
        result = {
            "score":          0,
            "summary":        f"Error: {str(e)}",
            "actions":        [],
            "docs":           [],
            "docs_generated": 0,
        }

    return {**state, "results": {**state.get("results", {}), "documentation": result}}


# node factory

def make_nodes(db, user_id: int):

    async def codebase_agent_node(state: dict) -> dict:
        return await _codebase(state, db, user_id)

    async def pr_review_agent_node(state: dict) -> dict:
        return await _pr_review(state)

    async def test_agent_node(state: dict) -> dict:
        return await _test(state, db, user_id)

    async def doc_agent_node(state: dict) -> dict:
        return await _doc(state, db, user_id)

    return codebase_agent_node, pr_review_agent_node, test_agent_node, doc_agent_node


# validator node

def validator_node(state: dict) -> dict:
    agent  = state["current_agent"]
    result = state.get("results", {}).get(agent, {})

    try:
        chain    = TEAM_VALIDATOR_PROMPT | llm | StrOutputParser()
        raw      = chain.invoke({"agent": agent, "repo": state["repo"], "output": json.dumps(result)})
        decision = clean_json(raw).get("decision", "done")
    except Exception:
        decision = "done"

    if decision == "retry" and state.get("retry_count", 0) < 2:
        return {**state, "retry_count": state.get("retry_count", 0) + 1}

    completed = list(state.get("completed", []))
    if agent not in completed:
        completed.append(agent)

    return {**state, "completed": completed}


# aggregator node

def aggregator_node(state: dict) -> dict:
    try:
        chain  = TEAM_AGGREGATOR_PROMPT | llm | StrOutputParser()
        raw    = chain.invoke({
            "repo":    state["repo"],
            "results": json.dumps(state.get("results", {}), indent=2),
        })
        parsed = clean_json(raw)
        return {
            **state,
            "health_score":   parsed.get("health_score", 0),
            "health_summary": parsed.get("summary", ""),
            "top_actions":    parsed.get("top_actions", []),
        }
    except Exception as e:
        return {
            **state,
            "health_score":   0,
            "health_summary": f"Error: {str(e)}",
            "top_actions":    [],
        }