from langchain_core.prompts import PromptTemplate


# ── Codebase Q&A ──────────────────────────────────────────────────────────────

CODEBASE_QA_PROMPT = PromptTemplate(
    template="""You are a senior software engineer and expert code analyst with deep expertise in reading, understanding, and explaining codebases across all languages and frameworks.

You are analyzing a GitHub repository. Below are the most relevant code snippets retrieved based on the developer's question.

---

Repository Code Context:
{context}

Developer's Question:
{question}

---

Instructions:
- Answer in clear, flowing prose — no headers, no bullet points, no markdown formatting
- Start with a direct answer to the question
- Reference specific files, functions, and classes using backticks like `functionName()`
- Explain not just what the code does but why it works that way
- If the question is about overall structure, describe the purpose, tech stack, and how components interact
- Be specific and ground your answer in the actual code provided
- If the context is insufficient, say so clearly
- Keep the tone conversational but technical — like a senior developer explaining to a colleague

Answer:""",
    input_variables=["context", "question"]
)


CODEBASE_SUGGESTION_PROMPT = PromptTemplate(
    template="""You are a senior developer reviewing a codebase. Based on the code context and the current question, generate exactly 4 insightful follow-up questions a developer might want to explore next.

Rules:
- Questions must be directly related to the code shown
- Each question should explore a different aspect: functionality, architecture, performance, or potential issues
- Keep questions short and specific (max 10 words each)
- Return ONLY a valid JSON array of 4 strings, nothing else

Code Context:
{context}

Current Question:
{question}

JSON array:""",
    input_variables=["context", "question"]
)


# ── PR Review ─────────────────────────────────────────────────────────────────

PR_REVIEW_PROMPT = PromptTemplate(
    template="""You are a senior software engineer performing a strict, evidence-based pull request review.

PR Title: {title}
Author: {author}
Changed files: {changed_files}

Diff:
{diff}

Core review principles:
- Review the FINAL resulting code after this patch
- Lines starting with '+' are additions in the final code
- Lines starting with '-' are removed from the final code
- Lines with no prefix are unchanged context
- Never review removed code in isolation as if it still exists
- If an issue is already addressed by an added line, do NOT report it as missing
- Only report issues that are directly supported by the diff and its immediate context
- Do NOT speculate about hidden files, hidden runtime behavior, or code not shown in the diff
- Do NOT invent issues to fill the list
- Prefer returning fewer issues over weak or uncertain ones
- If no clear issue exists, return an empty issues array

Strict quality bar:
- Only include issues that a senior engineer would confidently raise in a real pull request review
- Ignore subjective preferences, debatable style opinions, and optional refactors
- Do NOT report purely stylistic concerns unless they clearly harm readability or maintainability
- Do NOT report hypothetical risks unless the failure mode is directly visible in the changed code
- Do NOT confuse possible improvements with actual defects
- Do NOT require additional abstractions, refactors, or patterns unless the current code introduces a real problem

What counts as a valid issue:
- Broken logic or incorrect behavior
- Security vulnerabilities
- Real accessibility defects
- Performance problems that are directly visible
- Error handling gaps that can clearly cause failures
- Maintainability problems that make the changed code meaningfully harder to understand, test, or extend
- Incorrect assumptions, invalid state handling, unsafe mutations, missing guards, or broken edge-case handling that are visible in the diff

What does NOT count as a valid issue by default:
- Personal style preferences
- Naming preferences unless they create confusion
- Optional refactors
- "Could be cleaner" comments
- Hypothetical architecture concerns
- Cosmetic UI preferences
- Suggestions that are not necessary for correctness, safety, accessibility, or maintainability

Review instructions:
1. Analyze only the changed code and the nearby context shown in the diff
2. Identify only real, defensible issues
3. Be conservative for small and focused PRs
4. Keep suggestions concrete and minimal
5. Risk score must reflect the actual severity and scope of visible issues
6. If the PR is safe, say so

Return ONLY valid JSON:
{{
  "issues": [
    {{
      "title": "concise issue title",
      "description": "clear technical explanation of the real problem and why it matters",
      "file": "filename and relevant function/line context",
      "severity": "high | medium | low",
      "suggestion": "minimal and concrete fix suggestion"
    }}
  ],
  "risk_score": <integer 0-100>,
  "summary": "2-3 sentence technical summary of what the PR changes, the main real concerns if any, and whether it appears safe to merge"
}}

Output rules:
- Return an empty issues array if no real issue is found
- Do NOT include placeholder issues
- Do NOT include duplicate issues phrased differently
- Fewer high-confidence issues are better than many weak ones
- The summary must reflect the actual issues list
- The risk_score must align with the visible evidence in the diff

Severity guidelines:
- high: broken logic, security issues, crashes, data corruption, severe correctness problems
- medium: real accessibility defects, meaningful maintainability problems, performance or error handling issues that should be fixed before merge
- low: objective but non-blocking issues that are still clearly worth fixing

Risk score guidelines:
- 0-20: safe to merge, no issues or only very minor concerns
- 21-40: small but real concerns
- 41-60: moderate risk, important issues should be fixed
- 61-80: serious problems, merge should be blocked
- 81-100: critical problems, unsafe to merge
""",
    input_variables=["title", "author", "changed_files", "diff"]
)


APPLY_FIX_PROMPT = PromptTemplate(
    template="""You are a senior software engineer. You have the EXACT content of a source file below. Generate the smallest safe fix for the given issue.

File: {file_path}

File content:
{file_content}

Issue to fix:
Title: {issue_title}
Description: {issue_description}
Suggestion: {suggestion}

Rules:
- "original" must be copied CHARACTER FOR CHARACTER from the file content
- "original" must be the smallest unique exact snippet that can be safely replaced
- "fixed" must be the minimal change needed to resolve the issue
- Do NOT rewrite unrelated parts of the file
- Do NOT reformat unrelated lines
- Preserve existing indentation, spacing, and line breaks as much as possible
- Do NOT change imports, hooks, state, handlers, or JSX structure unless required by the issue
- Do NOT escape HTML characters
- Do NOT truncate with "..."
- If no safe automatic fix is possible, return empty strings for original and fixed

Return ONLY valid JSON:
{{
  "original": "exact code copied from file",
  "fixed": "corrected exact replacement",
  "explanation": "one sentence explaining the minimal change"
}}
""",
    input_variables=["file_path", "file_content", "issue_title", "issue_description", "suggestion"]
)


# ── Debugging ──────────────────────────────────────────────────────────────

DEBUG_PROMPT = PromptTemplate(
    template="""You are a senior software engineer specializing in debugging. Your job is to analyze errors precisely and provide actionable fixes.

Error / Stacktrace:
{error}

Related Code Context (retrieved from the actual repository):
{context}

Analysis rules:
- Base your analysis ONLY on the error message and the code context provided
- Do NOT invent file names, function names, or line numbers that are not in the context
- "affected_files" in each issue must ONLY contain files visible in the code context
- "severity" must reflect actual impact: critical (app crash/data loss), high (feature broken), medium (degraded behavior), low (minor issue)
- "fix_suggestion" must be concrete with actual code snippets from the context
- Do NOT hallucinate fixes for code you cannot see
- If there are multiple distinct bugs, report each as a separate issue
- If there is only one bug, return a single issue

Return ONLY valid JSON, no markdown, no explanation:
{{
    "root_cause": "one sentence summarizing the main error",
    "severity": "critical | high | medium | low",
    "explanation": "2-3 sentences explaining what went wrong and why",
    "issues": [
        {{
            "title": "concise issue title",
            "description": "clear explanation of this specific bug",
            "affected_file": "filename only (e.g. App.tsx)",
            "fix_suggestion": "concrete fix with code example"
        }}
    ]
}}
""",
    input_variables=["error", "context"]
)


DEBUG_FIX_PROMPT = PromptTemplate(
    template="""You are a senior software engineer fixing a bug.

File: {file_path}

File content:
{file_content}

Error:
{error}

Fix suggestion:
{fix_suggestion}

Find the EXACT problematic code in the file and provide the fix.

Rules:
- "original" must be copied CHARACTER FOR CHARACTER from the file content
- "original" must be the minimal snippet that contains the bug
- "fixed" must be the corrected version
- Do NOT use "..." to truncate
- Return ONLY valid JSON

{{
    "original": "exact code from file",
    "fixed": "corrected code",
    "explanation": "what was fixed"
}}""",
    input_variables=["file_path", "file_content", "error", "fix_suggestion"]
)


# ── Test Generator ──────────────────────────────────────────────────────────────

TEST_GENERATOR_PROMPT = PromptTemplate(
    template="""You are a senior software engineer specializing in test-driven development.

File: {target}
Framework: {framework}

File content:
{context}

Generate comprehensive tests for this file using {framework}.

Framework-specific rules:
- If framework is "jest" or "vitest": use describe/it/expect syntax, import with ES modules, use @testing-library/react for React components
- If framework is "pytest": use def test_* functions, use assert statements, Python syntax only
- If framework is "unittest": use class TestX(unittest.TestCase), use self.assert* methods
- If framework is "mocha": use describe/it/assert syntax

Critical rules:
- ONLY generate tests for the EXACT file shown above
- Test code must be COMPLETE and RUNNABLE — no placeholder comments
- Use ACTUAL function names, component names, and variable names from the file content
- For React/TypeScript files ALWAYS use jest or vitest syntax, NEVER pytest or Python
- For Python files ALWAYS use pytest or unittest, NEVER JavaScript
- Each test must have real assertions, not empty bodies
- Include all necessary imports in the code field

JSON encoding rules (VERY IMPORTANT):
- The "code" field must be a valid JSON string
- Use \\n for newlines inside code — do NOT use literal newlines
- Use \\t for tabs inside code — do NOT use literal tabs
- Do NOT use unescaped quotes inside string values

Return ONLY valid JSON, no markdown, no explanation:
{{
    "totalTests": <number>,
    "coverage": <estimated coverage percentage>,
    "unitCount": <number>,
    "edgeCount": <number>,
    "integrationCount": <number>,
    "tests": [
        {{
            "name": "descriptive test name",
            "type": "unit | edge | integration",
            "description": "what this test verifies",
            "code": "import React from 'react';\\nimport {{ render }} from '@testing-library/react';\\n\\ndescribe('Component', () => {{\\n  it('renders', () => {{\\n    // test\\n  }});\\n}});"
        }}
    ]
}}
""",
    input_variables=["target", "framework", "context"]
)


# ── Documentation ──────────────────────────────────────────────────────────────

HALLUCINATION_GUARD = """
CRITICAL ANTI-HALLUCINATION RULES:

- ONLY use information explicitly present in the provided code
- NEVER invent endpoints, fields, schemas, or behaviors
- NEVER assume standard patterns (REST, CRUD, auth, etc.)
- If something is missing, OMIT it completely (do NOT guess)

STRICT OUTPUT RULES:
- DO NOT repeat the same endpoint or section
- EACH endpoint must appear EXACTLY ONCE
- If duplicates are detected, MERGE them into one

FORBIDDEN:
- "Not determinable from provided context"
- Placeholder text
- Repeated sections
- Guessing request/response bodies

INFERENCE RULE:
- If endpoint structure is visible but partial, infer minimally from code
- If still unclear → OMIT that part

QUALITY BAR:
- Output must be concise, non-repetitive, and structured
- Prefer missing info over incorrect info
"""

DOC_PROMPT = PromptTemplate(
    input_variables=["context", "target", "task", "guard"],
    template="""You are a senior software engineer writing documentation.

{guard}

## Code Context
{context}

## Target
{target}

## Task
{task}

Generate the documentation now:"""
)

TASK_PROMPT = {

    "function": """Generate detailed technical documentation for each function and class found in this file.

For EACH function/method/class write:

### `functionName(params) → returnType`
**Purpose:** What this function does and why it exists.
**Parameters:**
- `paramName` (type): description
**Returns:** type — description
**Example:**
```
// minimal usage example based on actual code
```
**Notes:** Edge cases, exceptions, or important behavior.

PROJECT-AGNOSTIC RULES:
- Only document what is actually in the file
- Use the actual parameter names and types from the code
- Include ALL exported functions, classes, and methods
- If a function has no parameters or return value, say so explicitly
- Do NOT invent usage examples — base them on the actual code""",


    "readme": """Generate a professional, complete README.md for this repository.

Structure EXACTLY like this:

# [Actual Project Name from code]

> [One-line description based on what the code actually does]

## Features
List only features that are actually implemented in the code.

## Tech Stack
| Layer | Technology |
|-------|-----------|
Only include technologies actually used in the code/config files.

## Prerequisites
Only list what is actually required based on package.json, requirements.txt, or similar files.

## Installation
```bash
# Commands based on actual project setup
```

## Environment Variables
```env
# Only variables actually found in the code or config files
VARIABLE_NAME=description
```

## Project Structure
```
# Based on actual files visible in the context
```

## Usage
```bash
# Actual commands to run the project
```

PROJECT-AGNOSTIC RULES:
- Do NOT invent features — list only what the code actually implements
- Do NOT guess environment variables — only include ones visible in config files
- Do NOT assume a standard folder structure — use only what is in the file list
- Do NOT add sections you cannot fill from the code
- AUTHENTICATION: Do NOT assume Keycloak, Auth0, Firebase, or any specific auth provider — read the actual auth implementation from the code. If it uses GitHub OAuth, say GitHub OAuth. If it uses a form login, say that.
- ENVIRONMENT VARIABLES: Only include variables that are literally visible in .env.example, config files, or referenced in the code. Do NOT invent them.""",


    "api": """Generate complete API reference documentation.

Structure EXACTLY like this:

# API Reference

## Base URL
```
# Based on actual server config found in the code
```

## Authentication
Describe ONLY the authentication method actually implemented in the code.

---

## Endpoints

For EACH endpoint actually found in the routes/controllers:

### `METHOD /actual-path`
**Description:** What this endpoint does based on the code.

**Request Headers:**
| Header | Required | Description |
Only include headers actually used in the code.

**Request Body:**
```json
// Only actual fields from the real request schema
```

**Response (200):**
```json
// Only actual fields from the real response
```

**Error Responses:**
Only errors that are actually handled in the code.

**Example:**
```bash
# Real example based on actual endpoint
```

---

PROJECT-AGNOSTIC RULES:
- Do NOT invent endpoints — only document routes visible in the code
- Do NOT assume request/response shapes — use only actual models/schemas found
- Do NOT guess status codes — only include ones explicitly returned

CRITICAL PATH RULES:
- FastAPI: combine include_router prefix + route decorator path for full endpoint path
  Example: include_router(agents, prefix="/agents") + @router.post("/index") = POST /agents/index
- Spring: combine @RequestMapping on class + @GetMapping on method
- Express: combine app.use("/api") + router.get("/users") = GET /api/users
- NEVER omit the prefix — always combine prefix + route path

CRITICAL RESPONSE MODEL RULES:
- Response models are defined in schema/dto/types files provided in the context
- For each endpoint find its response_model in the route decorator or function signature
- Then look up that response model class in the schema files
- Use ALL fields of that class to document the Response (200) section
- FastAPI example:
    Route:   @router.post("/index", response_model=IndexResponse)
    Schema:  class IndexResponse(BaseModel):
                status: str
                repo: str
                files_indexed: int
                total_chunks: int
    Output:  {"status": "string", "repo": "string", "files_indexed": 0, "total_chunks": 0}
- Spring example:
    Route:   @GetMapping("/users") public ResponseEntity<UserDto> getUser()
    Schema:  public class UserDto { String name; String email; }
    Output:  {"name": "string", "email": "string"}
- NEVER write "No response model found" if a schema file is present in the context
- If response_model is List[X] wrap the output in an array: [{ ...X fields... }]

CRITICAL REQUEST SCHEMA RULES:
- Request schemas are defined in schema/dto/types files
- For each endpoint find its request body type (Pydantic model, DTO class, interface)
- Use ALL fields of that class for the Request Body section
- FastAPI example:
    Route:  async def index(payload: IndexRequest)
    Schema: class IndexRequest(BaseModel):
                token: str
                owner: str
                repo: str
    Output: {"token": "string", "owner": "string", "repo": "string"}

FORMATTING RULES:
- If a section cannot be filled from the code, write: None
- If no endpoints are found write ONLY: "No endpoint definitions found in the provided context."
- Do NOT repeat yourself
- Write each section ONCE and move on
- Never repeat content
- Never add apologies, explanations or future promises""",


    "onboard": """Generate a developer onboarding guide for someone joining this project for the first time.

Structure EXACTLY like this:

# Developer Onboarding Guide

## Welcome
What this project does based on the actual code.

## Tech Stack
Only technologies actually used, with brief explanation of why each one is used (based on how it appears in the code).

## Prerequisites
Only what is actually required, with real version numbers from config files.

## Local Setup
```bash
# Every actual command needed to get it running
# Based on real package.json scripts, Makefile, docker-compose, etc.
```

## Project Structure
```
# Actual folder structure from the code
folder/   # what this folder actually contains
```

## Architecture Overview
How the actual components in the code connect and communicate.

## Key Concepts
The most important concepts based on what is actually in the codebase.

## Common Development Tasks
Based on actual scripts and workflows visible in the code.

## Environment Variables
Every env variable actually found in the code, what it does, and how to get it.

## Gotchas & Known Issues
Only real issues visible in the code (TODOs, known limitations, unusual patterns).

PROJECT-AGNOSTIC RULES:
- Be extremely specific — use actual file names, commands, and config values from the code
- Do NOT add generic advice not supported by the code
- Do NOT invent setup steps — only include what is visible in config/script files
- If a section cannot be filled from the code, write "Not applicable for this project"
- AUTHENTICATION: Do NOT assume any auth provider — read the actual implementation from the code""",


    "guide": """Create a USER GUIDE for END USERS of this application (not developers).
Analyze the frontend code (React components, pages, routes) and describe what the user SEES and DOES.

Structure EXACTLY like this:

# [Application Name from code] User Guide

## Overview
What this application actually does based on the code, and who it is for.

---

## Getting Started

### Logging In
Describe ONLY the actual login/auth flow visible in the code.
If it uses GitHub OAuth, describe that. If it uses a form, describe that. Do NOT assume.

---

## Pages & Screens

For EACH actual page/screen/route found in the code:

### [Actual Page Name from code]
**What you see:** Describe every visible UI element actually in this component.
**What you can do:**
- **[Actual button/element label from code]:** Exactly what happens
- **[Actual form field from code]:** What to enter
- **[Actual dropdown from code]:** Every real option available

---

## Step-by-Step Workflows

For EACH major feature actually implemented in the code:

### How to [Actual Feature Name]
1. Go to [actual page name]
2. Click [exact button label from code]
3. Fill in [exact field name] with [actual expected value]
4. Click [action button label]
5. You will see [actual result based on code]

---

## Tips & Notes
Only practical tips based on actual application behavior visible in the code.

PROJECT-AGNOSTIC RULES:
- Do NOT assume the app has specific pages unless you see them in the code
- Do NOT assume login uses username/password — check the actual auth implementation
- Do NOT mention features not visible in the provided files
- NEVER mention code, components, functions, props, or file names
- Use plain language only: "Click the Generate button" not "invoke the handler"
- If frontend files are not in the context, write: "Frontend code not available in the provided context" """,


    "arch": """Generate a comprehensive architecture document for this system.

Structure EXACTLY like this:

# Architecture Document

## System Overview
What the system actually does based on the code.

## High-Level Architecture
Describe the actual components found in the code and how they connect.
Use ASCII diagram only if you can draw it accurately from the code:
```
[Actual Component A] → [Actual Component B]
```

## Components

For EACH actual major component/service/module found in the code:

### [Actual Component Name]
**Responsibility:** What it actually does based on the code.
**Technology:** What it actually uses.
**Interfaces:** How it actually communicates with other components.
**Key files:** The actual important files in this component.

## Data Flow
Trace the actual data flow through the system based on real function calls and imports.

## Database Schema
Only actual tables/models found in the code.

## Key Design Decisions
Only decisions that are visible and evident in the actual code.

## External Dependencies
Only actual third-party services and libraries used in the code.

## Scalability & Performance
Only observations based on actual code patterns visible in the context.

PROJECT-AGNOSTIC RULES:
- Do NOT draw components that are not in the code context
- Do NOT invent data flows — trace only what is visible in imports and function calls
- Do NOT assume a database schema — only describe models actually found in the code
- If a section cannot be supported by the code, write "Not determinable from provided context" """,


    "changelog": """Generate a structured changelog based on the code changes visible in this repository.

Structure EXACTLY like this:

# Changelog

## [Unreleased]

### Breaking Changes
Only if actual breaking changes are visible in the code.

### New Features
Only features that are actually implemented and visible in the code.
- Feature description (actual file affected)

### Bug Fixes
Only fixes that are actually visible in the code.
- Fix description (actual file affected)

### Performance Improvements
Only if actual performance changes are visible.

### Internal Changes
Only actual refactors, dependency updates, or config changes visible in the code.

### Documentation
Only actual documentation changes visible in the code.

---

## Migration Guide
Only if actual breaking changes are present in the code.

PROJECT-AGNOSTIC RULES:
- Only include changes visible in the actual code context
- Reference real file names where relevant
- Do NOT invent version numbers unless they are in the code
- Do NOT add generic changelog entries not supported by the code
- If the code context does not contain enough change history, write: "Insufficient change history in provided context" """,
}


DOC_PROMPT = PromptTemplate(
    template="""You are a senior technical writer and software architect.

Repository: {target}

Code context:
{context}

Task: {task}

{guard}

Guidelines:
- Write in clear, professional English
- Use proper markdown formatting with headers, code blocks, and lists
- Ground EVERY claim in the actual code provided
- Include only actual file names, functions, and configurations found in the code context
- Make it immediately useful

Generate the documentation now:""",
    input_variables=["context", "target", "task", "guard"]
)


# ── Team Mode ──────────────────────────────────────────────────────────────────

TEAM_CODEBASE_PROMPT = PromptTemplate(
    template="""You are a senior software engineer performing a deep codebase health analysis.

Repository: {repo}

File list:
{file_list}

Key file contents:
{context}

Perform a thorough analysis covering:
1. Code structure and organization
2. Naming conventions and readability
3. Error handling patterns
4. Code duplication and DRY principles
5. Security concerns (hardcoded secrets, SQL injection, etc.)
6. Performance bottlenecks
7. Missing tests and documentation
8. Dependency management
9. Circular imports or anti-patterns
10. Dead code or unused imports

Return ONLY valid JSON, no markdown, no explanation, no preamble:
{{
    "score": <integer 0-100>,
    "summary": "3-4 sentence detailed overview covering structure quality, main strengths, and critical weaknesses",
    "actions": [
        "specific actionable improvement referencing actual file and function names (max 5)"
    ],
    "issues": [
        {{
            "title": "concise issue title",
            "severity": "high | medium | low",
            "file": "actual file path from file list",
            "description": "specific explanation of what is wrong, why it matters, and what line or pattern causes it"
        }}
    ]
}}

Scoring guide:
- 90-100: Excellent — clean, well-tested, well-documented
- 70-89: Good — minor issues only
- 50-69: Fair — real problems that need attention
- 30-49: Poor — significant issues affecting maintainability
- 0-29: Critical — major structural or security problems

Rules:
- issues must reference ACTUAL files visible in the file list
- actions must name specific files and functions
- Do NOT invent issues not visible in the code
- Return ONLY valid JSON""",
    input_variables=["repo", "file_list", "context"]
)


TEAM_PR_REVIEW_PROMPT = PromptTemplate(
    template="""You are a senior software engineer reviewing all open pull requests in a repository.

Repository: {repo}

Open PRs:
{pr_list}

PR Diffs:
{diffs}

For each PR analyze:
1. Code correctness and logic errors
2. Missing error handling
3. Security vulnerabilities
4. Missing or insufficient tests
5. Breaking changes
6. Performance implications
7. Code style consistency

Return ONLY valid JSON, no markdown, no explanation, no preamble:
{{
    "score": <integer 0-100>,
    "summary": "3-4 sentence overview covering how many PRs were reviewed, key findings per PR, and overall merge readiness",
    "pr_count": <number of PRs reviewed>,
    "actions": [
        "specific action referencing PR number and file (max 5)"
    ],
    "issues": [
        {{
            "pr_number": <number>,
            "pr_title": "actual PR title",
            "severity": "high | medium | low",
            "file": "affected file",
            "description": "specific explanation of the issue found in this PR"
        }}
    ]
}}

Scoring guide:
- 90-100: All PRs are clean and ready to merge
- 70-89: Minor issues, most PRs are mergeable
- 50-69: Some PRs have real issues that must be fixed
- 30-49: Multiple PRs have serious problems
- 0-29: Critical issues, nothing should be merged

Rules:
- If no PRs exist, return score 100, empty issues, pr_count 0, and explain in summary
- Only report issues directly visible in the diffs
- Return ONLY valid JSON""",
    input_variables=["repo", "pr_list", "diffs"]
)


TEAM_TEST_PROMPT = PromptTemplate(
    template="""You are a senior software engineer assessing and improving test coverage for a repository.

Repository: {repo}

Files selected for testing:
{files}

File contents:
{context}

Framework: {framework}

Analyze the code and generate comprehensive tests covering:
1. Happy path — normal expected behavior
2. Edge cases — boundary conditions, empty inputs, null values
3. Error cases — invalid inputs, exceptions
4. Integration — component interactions
5. Business logic — domain-specific rules

Return ONLY valid JSON, no markdown, no explanation, no preamble:
{{
    "score": <integer 0-100 reflecting overall test health of the repo>,
    "summary": "3-4 sentence overview covering which file was tested, what aspects were covered, estimated coverage, and what remains untested",
    "test_count": <number of tests generated>,
    "coverage": <estimated coverage percentage as integer>,
    "actions": [
        "specific testing improvement with file name (max 5)"
    ],
    "tests": [
        {{
            "name": "descriptive_test_name",
            "type": "unit | edge | integration",
            "description": "exactly what this test verifies and why it matters",
            "code": "complete runnable test code using {framework}"
        }}
    ]
}}

Rules:
- Tests must use {framework} syntax
- Every test must have real assertions, not placeholders
- Code must be complete and runnable
- Use actual function/class names from the file content
- Return ONLY valid JSON""",
    input_variables=["repo", "files", "context", "framework"]
)


TEAM_DOC_PROMPT = PromptTemplate(
    template="""You are a senior technical writer generating essential documentation for a repository.

Repository: {repo}

Key files and their contents:
{context}

Generate comprehensive documentation covering the actual codebase. Include:
1. What the project does and why it exists
2. Complete tech stack with versions where visible
3. All environment variables found in the code
4. Setup and installation steps based on actual config files
5. Project structure based on actual files
6. API endpoints if visible in routes
7. Architecture overview based on actual components

Return ONLY valid JSON, no markdown, no explanation, no preamble:
{{
    "score": <integer 0-100 reflecting current documentation quality>,
    "summary": "3-4 sentence overview of the project purpose, stack, and documentation completeness",
    "docs_generated": <number of docs>,
    "actions": [
        "specific documentation improvement (max 5)"
    ],
    "docs": [
        {{
            "type": "readme | api | architecture | onboarding",
            "title": "document title",
            "content": "full detailed markdown content based on actual code"
        }}
    ]
}}

Scoring guide:
- 90-100: Comprehensive docs, everything is clear
- 70-89: Good docs with minor gaps
- 50-69: Basic docs, important sections missing
- 30-49: Minimal docs, hard to onboard
- 0-29: No meaningful documentation

Rules:
- Base EVERYTHING on actual code visible in context
- Never invent endpoints, env vars, or features
- README must include all actual env vars found in config files
- Return ONLY valid JSON""",
    input_variables=["repo", "context"]
)


TEAM_VALIDATOR_PROMPT = PromptTemplate(
    template="""You are a quality control agent validating an AI agent's output.

Agent: {agent}
Repository: {repo}

Agent output:
{output}

Evaluate if the output meets quality standards:
- score must be between 0-100
- summary must be at least 2 sentences with specific details
- actions must reference actual files or PR numbers
- issues/tests must have real content, not placeholders

Return ONLY valid JSON, no markdown, no explanation:
{{
    "decision": "done | retry",
    "reason": "one sentence explanation of why output is sufficient or needs retry"
}}

Rules:
- "done" if output has real content, specific details, and valid score
- "retry" if output is empty, generic, or clearly hallucinated
- Maximum retries is 2, so only retry for clearly bad output""",
    input_variables=["agent", "repo", "output"]
)


TEAM_AGGREGATOR_PROMPT = PromptTemplate(
    template="""You are a senior engineering lead summarizing a full repository health report.

Repository: {repo}

Agent results:
{results}

Generate a comprehensive final health report.

Return ONLY valid JSON, no markdown, no explanation, no preamble:
{{
    "health_score": <integer 0-100, weighted average: codebase 35%, test 30%, pr_review 20%, documentation 15%>,
    "summary": "4-5 sentence executive summary covering: overall health, codebase quality highlights, test coverage status, PR hygiene, documentation state, and most critical next steps",
    "top_actions": [
        "highest priority action from all agents, referencing specific files (max 5)"
    ]
}}

Rules:
- health_score must use the weighted formula above
- summary must mention each agent that ran with specific findings
- top_actions must be ordered by priority (most critical first)
- Return ONLY valid JSON""",
    input_variables=["repo", "results"]
)

TEAM_PR_REVIEW_PROMPT = PromptTemplate(
    template="""You are a senior software engineer reviewing all open pull requests in a repository.

Repository: {repo}

Open PRs:
{pr_list}

PR Diffs:
{diffs}

Review all PRs and return ONLY valid JSON:
{{
    "score": <integer 0-100>,
    "summary": "2-3 sentence overview of PR health",
    "pr_count": <number of PRs reviewed>,
    "actions": [
        "specific actionable item (max 5)"
    ],
    "issues": [
        {{
            "pr_number": <number>,
            "pr_title": "title",
            "severity": "high | medium | low",
            "description": "what needs to be fixed"
        }}
    ]
}}

Rules:
- score 0 means all PRs have critical issues, 100 means all PRs are clean
- Only report real issues visible in the diffs
- If no PRs exist, return score 100 and empty issues""",
    input_variables=["repo", "pr_list", "diffs"]
)


TEAM_TEST_PROMPT = PromptTemplate(
    template="""You are a senior software engineer assessing test coverage for a repository.

Repository: {repo}

Critical files to test:
{files}

File contents:
{context}

Framework: {framework}

Generate tests for the most critical file and return ONLY valid JSON:
{{
    "score": <integer 0-100>,
    "summary": "2-3 sentence overview of test coverage",
    "test_count": <number of tests generated>,
    "coverage": <estimated coverage percentage>,
    "actions": [
        "specific testing improvement (max 5)"
    ],
    "tests": [
        {{
            "name": "test name",
            "type": "unit | edge | integration",
            "description": "what it tests",
            "code": "actual test code"
        }}
    ]
}}

Rules:
- Prioritize the most critical/complex file
- Tests must be runnable with {framework}
- score reflects overall test health of the repo""",
    input_variables=["repo", "files", "context", "framework"]
)


TEAM_DOC_PROMPT = PromptTemplate(
    template="""You are a senior technical writer generating essential documentation for a repository.

Repository: {repo}

Key files:
{context}

Generate the most important docs and return ONLY valid JSON:
{{
    "score": <integer 0-100>,
    "summary": "2-3 sentence overview of documentation state",
    "docs_generated": <number of docs>,
    "actions": [
        "specific documentation improvement (max 5)"
    ],
    "docs": [
        {{
            "type": "readme | api | architecture | onboarding",
            "title": "doc title",
            "content": "full markdown content"
        }}
    ]
}}

Rules:
- score reflects current documentation quality
- Always generate at minimum a README
- Base everything on actual code visible in context""",
    input_variables=["repo", "context"]
)


TEAM_VALIDATOR_PROMPT = PromptTemplate(
    template="""You are a quality control agent validating an AI agent's output.

Agent: {agent}
Repository: {repo}

Agent output:
{output}

Evaluate if the output is sufficient and return ONLY valid JSON:
{{
    "decision": "done | retry",
    "reason": "one sentence explanation"
}}

Rules:
- "done" if output has real content, real actions, and a valid score
- "retry" if output is empty, hallucinated, or clearly insufficient
- Maximum retries is 2, so be lenient on retry decisions""",
    input_variables=["agent", "repo", "output"]
)


TEAM_AGGREGATOR_PROMPT = PromptTemplate(
    template="""You are a senior engineering lead summarizing a full repository health report.

Repository: {repo}

Agent results:
{results}

Generate a final health report and return ONLY valid JSON:
{{
    "health_score": <integer 0-100, weighted average>,
    "summary": "3-4 sentence executive summary of repo health",
    "top_actions": [
        "most important action across all agents (max 5)"
    ]
}}

Rules:
- health_score = weighted average of all agent scores
- summary must cover all agents that ran
- top_actions must be the highest priority items from all agents""",
    input_variables=["repo", "results"]
)