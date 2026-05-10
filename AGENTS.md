# AGENTS.md

# Analysis Agent Project — Codex Operating Standard

This repository is building an enterprise-grade statistical analysis agent kernel.

Codex must treat this project as a serious architecture project, not a quick demo, not a patch playground, and not a place to hide bugs behind brittle heuristics.

The goal is to evolve this codebase toward a clean agent kernel with:

- unified domain contracts
- structured task interpretation
- goal-driven intelligent planning
- dataset-aware tool selection
- tool manifests and applicability contracts
- verifier / human-review / execution boundaries
- deliverable checking based on evidence
- LangGraph orchestration with thin nodes
- UI as a thin client, not the brain

Codex must follow this file strictly.

---

## 1. Non-Negotiable Rules

### 1.1 No Lazy Patches

Never solve a bug by adding a narrow conditional unless the condition represents a real domain rule.

Forbidden:

```python
if "summary" in user_request:
    ...
elif "regression" in user_request:
    ...
```

Forbidden:

```python
if tool_name == "run_multiple_regression":
    special_case_fix()
```

Forbidden:

```python
# Hack for current test
```

Forbidden:

```python
# TODO: clean this later
```

Unless explicitly instructed, Codex must not add brittle patches, hidden fallbacks, fake compatibility shims, or hardcoded phrases.

---

### 1.2 No String-Pattern Intelligence

The agent must not become smarter by growing phrase lists.

Do not expand:

```python
ADVISORY_PATTERNS = (...)
PLAN_ONLY_PATTERNS = (...)
DIRECT_TOOL_PATTERNS = (...)
```

Natural-language understanding must move toward structured objects:

```text
IntentDecision
TaskSpec
PlanProposal
TaskContract
```

String matching may only be used for deterministic UI event types such as:

```text
run_plan
approve_human_review
reject_human_review
update_plan_step_choices
upload_dataset
```

Natural-language user messages must not be routed by substring matching as the primary design.

---

### 1.3 No Architecture Bypass

Do not bypass the intended architecture to make one test pass.

Wrong:

```text
UI directly calls executor
planner directly mutates state
verifier silently fixes arguments
plugin base builds UI reports
deliverable gate invents its own contract shape
```

Correct:

```text
user request
  -> IntentDecision
  -> TaskSpec
  -> PlanProposal
  -> ActionProposal
  -> VerificationResult
  -> ToolExecutionResult
  -> Observation / Evidence
  -> TaskContract / DeliverableCheck
  -> FinalResponse
```

---

### 1.4 No Fake Success

Never mark something as successful unless it actually happened.

Forbidden:

```python
return {"status": "ok", "message": "Completed"}
```

when:

- the tool did not run
- the result was not validated
- an exception was swallowed
- required evidence is missing
- the requested deliverable was not produced

Failures must be explicit, structured, and recoverable when possible.

---

### 1.5 No Silent Exception Swallowing

Forbidden:

```python
try:
    ...
except Exception:
    pass
```

Forbidden:

```python
except Exception:
    return {}
```

Every exception path must preserve:

```text
error_type
message
recoverable or not
where it failed
what state/action/tool caused it
```

---

### 1.6 No Broad Rewrites Without Diagnosis

Codex must not rewrite a large file or subsystem before proving:

1. what is wrong
2. where it is wrong
3. why the current design causes the issue
4. what minimal architectural change fixes the root cause
5. what tests prove the fix

---

### 1.7 No Deleting Code Without Dependency Search

Before deleting or renaming any file, class, function, or field, Codex must search all references.

Required search examples:

```powershell
Select-String -Path .\**\*.py -Pattern "ThingToDelete"
```

or equivalent ripgrep:

```bash
rg "ThingToDelete"
```

Codex must report:

```text
References found:
Files affected:
Migration strategy:
Compatibility strategy:
Tests to update:
```

---

### 1.8 No Invented APIs

Codex must not invent functions, classes, attributes, or imports without checking the existing codebase.

Before calling or importing something, Codex must verify it exists.

Forbidden:

```python
from core.services.planner import create_plan
```

unless `create_plan` actually exists or Codex is explicitly adding it.

---

### 1.9 No Fake Architecture Tests

Architecture tests must verify real boundaries.

Forbidden:

```python
assert "some_string" in text
```

if the string is only added as a comment to satisfy the test.

Do not add fake comments to production files just to make architecture tests pass.

---

### 1.10 No UI-First Fixes

Until explicitly instructed, do not prioritize Streamlit UI fixes.

The current priority is agent kernel correctness:

```text
domain contracts
tool plugin boundaries
dataset context
interaction router
intelligent planner
supervisor/verifier/deliverable alignment
graph kernel tests
```

UI cutover comes later.

---

## 2. Required Working Procedure

Codex must follow this procedure for every non-trivial task.

---

### Step 1: Read the Project Plan First

Before modifying architecture, Codex must read:

```text
AGENT_KERNEL_REFACTOR_PLAN.md
AGENTS.md
```

If either file is missing, Codex must say so and avoid guessing project-wide architecture.

---

### Step 2: Inspect Before Editing

Before any code change, Codex must inspect relevant files.

For architecture tasks, inspect at least:

```text
core/graph.py
core/schema.py
core/workflow/
core/planning/
core/deliverables/
core/analysis_tool_plugins/
core/dataset_intelligence/
core/interaction_intent.py
tests/
```

Do not modify code before understanding the current route.

---

### Step 3: Produce a Change Plan Before Editing

For every meaningful change, Codex must first produce a short plan:

```text
Problem:
Root cause:
Files to inspect:
Files to modify:
Compatibility strategy:
Tests to add/update:
Risks:
Rollback plan:
```

Do not start editing until the plan is clear.

---

### Step 4: Make the Smallest Architectural Change That Fixes the Root Cause

Smallest does not mean patchy.

Correct small change:

```text
Introduce canonical TaskContract in core/domain/deliverable.py
Make old imports re-export it
Convert deliverable gate internal contract to DeliverableGateContract
Add architecture tests preventing duplicate TaskContract
```

Incorrect small change:

```text
Add if isinstance(contract, dict) special case in deliverable gate and move on
```

---

### Step 5: Add or Update Tests With Every Change

Every change must include tests unless it is purely documentation.

Required test categories:

```text
unit tests
architecture boundary tests
integration or graph kernel tests when flow changes
```

Do not claim success without running relevant tests.

---

### Step 6: Run Targeted Tests First

Do not immediately run the full suite if the change is localized.

Examples:

```powershell
pytest -q tests/deliverables
pytest -q tests/architecture/test_domain_contract_boundaries.py
pytest -q tests/dataset_intelligence
pytest -q tests/planning
pytest -q tests/workflow
```

Then run broader tests only after targeted tests pass.

---

### Step 7: Report Honestly

Final response must include:

```text
Changed files:
New files:
Deleted files:
Tests run:
Tests passed:
Tests failed:
Known remaining issues:
Next recommended step:
```

If tests were not run, say so clearly.

Never say “all good” unless tests actually passed.

---

## 3. Architecture Vision

The intended long-term architecture is:

```text
core/
  domain/
    intent.py
    task.py
    plan.py
    action.py
    observation.py
    evidence.py
    deliverable.py
    dataset_context.py

  services/
    interaction_router.py
    task_interpreter.py
    intelligent_planner.py
    plan_verifier.py
    action_verifier.py
    supervisor.py
    deliverable_checker.py
    final_response_builder.py

  tools/
    manifest.py
    arguments.py
    roles.py
    applicability.py
    policies.py
    registry.py
    executor.py
    result_builder.py

  data/
    context_refresh.py
    versions.py
    profiling.py

  workflow/
    langgraph_app.py
    nodes/
    routes.py

  runtime/
    langgraph_runtime.py

  reporting/
    builder.py
    markdown.py
    tables.py

  quality/
    statistical_guardrails.py
```

Do not force this final structure immediately. Use incremental migration.

---

## 4. Dependency Rules

### 4.1 Allowed Dependency Direction

```text
UI
  -> runtime
  -> workflow
  -> services
  -> domain
```

Tool-related dependency direction:

```text
services / planner / verifier
  -> tool registry
  -> tool manifest
  -> tool implementation
```

---

### 4.2 Forbidden Dependency Direction

Forbidden:

```text
domain -> LangGraph
domain -> Streamlit
domain -> UI snapshot
planner -> Streamlit
planner -> UI adapter
plugin base -> full report builder
plugin base -> analysis run storage schema
runtime -> individual workflow nodes
runtime -> route_after_intent
UI -> executor directly
```

---

## 5. Domain Contract Rules

### 5.1 Canonical Domain Objects

The agent kernel must converge on:

```text
IntentDecision
TaskSpec
DatasetContext
ToolManifest
PlanProposal
ActionProposal
VerificationResult
ToolExecutionResult
Observation
EvidenceBundle
TaskContract
DeliverableCheckResult
FinalResponse
```

These objects define the internal agent protocol.

---

### 5.2 TaskSpec Is Not a Tool Call

Correct:

```python
TaskSpec(
    goal_type="regression_modeling",
    target_variables=["GPA"],
    predictor_variables=["SATM"],
    requested_methods=["linear_regression"],
)
```

Incorrect:

```python
TaskSpec(
    goal_type="run_multiple_regression"
)
```

---

### 5.3 IntentDecision Must Not Directly Select Tools

Correct:

```python
IntentDecision(
    intent="direct_analysis",
    task_spec=TaskSpec(goal_type="regression_modeling"),
)
```

Incorrect:

```python
IntentDecision(
    intent="run_multiple_regression",
)
```

---

### 5.4 PlanProposal Must Be Goal-Driven

Correct:

```text
For dataset overview:
1. inspect dataset shape
2. missingness report
3. numeric summary
4. categorical summary
5. correlation matrix only if enough numeric variables
```

Incorrect:

```text
List every tool that capability_map says is ready
```

---

### 5.5 TaskContract Must Be Unique

There must be only one canonical `TaskContract`.

Canonical location:

```text
core/domain/deliverable.py
```

Forbidden:

```text
core/schema.py defines another TaskContract
core/deliverables/contracts.py defines another TaskContract
```

If a component needs an internal flattened structure, name it differently:

```text
DeliverableGateContract
```

Do not call it `TaskContract`.

---

## 6. Plugin System Rules

### 6.1 `analysis_tool_plugins/base.py` Must Stay Minimal

`base.py` should define only the minimal `AnalysisToolPlugin` identity and runtime wrapper.

It must not own:

```text
p-value formatting
number formatting
report block construction
analysis_run construction
table display normalization
default extractor
guardrail orchestration
planner intelligence
```

---

### 6.2 Split Plugin Responsibilities

Target short-term structure:

```text
core/analysis_tool_plugins/
  base.py              # AnalysisToolPlugin only
  types.py             # function type aliases
  arguments.py         # ArgumentSchema
  display.py           # display config and formatting
  reporting.py         # report block construction
  roles.py             # VariableRoleSpec
  applicability.py     # ApplicabilityResult
  policy_types.py      # VersioningPolicy, RepairPolicy, PlanningPolicy
  policies.py          # policy presets
  guardrails.py        # guardrail evaluation helpers
  result_builder.py    # analysis_run builder
```

---

### 6.3 Planner Depends on Manifest-Level Metadata Only

Planner may use:

```text
tool_name
method_family
argument_schema
variable_roles
applicability_checker
planning_policy
requires_confirmation
mutates_data
expected_deliverables
```

Planner must not depend on:

```text
DisplayConfig
format_p_value
build_generic_report_blocks
analysis_run schema
Streamlit
UI snapshot
```

---

### 6.4 Tool Declaration and Tool Execution Should Be Separate

Long-term target:

```text
ToolManifest
  describes tool capabilities, inputs, outputs, applicability, policies

ToolImplementation
  executes the tool
```

Planner should read manifests.  
Executor should run implementations.

---

## 7. Dataset Context Rules

### 7.1 One Source of Truth

There must be one dataset context refresh service.

Target:

```text
core/data/context_refresh.py
```

or:

```text
core/context/refresh.py
```

It should produce:

```text
DatasetContext
dataset_profile
dataset_summary
capability_map
```

---

### 7.2 No Duplicate Capability Map Generation

Forbidden:

```text
build_context_node creates one capability_map
dataset_upload.py creates another basic capability_map
planner creates a third interpretation
```

All must call the same context refresh service.

---

### 7.3 No Stale Dataset Context

After data mutation, context must be refreshed against the new active data version.

Any tool that mutates data must produce or update:

```text
active_data_version_id
data_versions
data_audit_log
```

Then the next planning/verifier step must use fresh context.

---

## 8. Interaction Router Rules

### 8.1 Event Router Can Be Deterministic

Allowed deterministic routing:

```text
run_plan
approve_human_review
reject_human_review
update_plan_step_choices
upload_dataset
```

These are UI/system events, not natural language.

---

### 8.2 Natural Language Router Must Output Structured Decision

User messages must become:

```text
IntentDecision
TaskSpec
```

Not raw strings.

---

### 8.3 No Direct Tool Selection in Router

The router decides what the user wants.  
The planner decides how to do it.

Router:

```text
direct_analysis + regression_modeling
```

Planner:

```text
run_multiple_regression
regression_diagnostics
residual_histogram
```

---

## 9. Intelligent Planner Rules

### 9.1 Planner Input

Planner input should be:

```text
TaskSpec
DatasetContext
ToolRegistry / ToolManifest
```

---

### 9.2 Planner Output

Planner output should be:

```text
PlanProposal
```

---

### 9.3 Planner Must Not Be a Tool Catalog Renderer

Forbidden behavior:

```text
for every ready tool in capability_map:
    add tool to plan
```

---

### 9.4 Dataset Overview Planning

For:

```text
What does the data look like?
```

Expected plan:

```text
dataset overview
missingness report
numeric summary
categorical summary
correlation matrix only when appropriate
```

Must not include:

```text
regression
ANOVA
chi-square
clean_data
```

---

### 9.5 Regression Planning

For:

```text
run linear regression of GPA on SATM
```

Expected plan:

```text
validate GPA numeric
validate SATM numeric
run regression
optional diagnostics
summarize coefficients and limitations
```

---

### 9.6 Suggestion Planning

For:

```text
I do not know what to do with this data
```

Expected plan:

```text
dataset overview
missingness assessment
variable type audit
EDA
recommend possible next analyses
```

Must not immediately execute destructive tools or arbitrary models.

---

## 10. Verifier Rules

The verifier must check:

```text
tool exists
arguments satisfy ArgumentSchema
required variables exist
semantic types are appropriate
mutating tools require confirmation
data version is valid
required user choices are supplied
```

Verifier must not silently repair invalid actions unless the repair is explicit and recorded.

---

## 11. Human Review Rules

Data-mutating tools must require human review unless explicitly classified as safe.

Examples requiring confirmation:

```text
drop rows
drop columns
impute values
overwrite dataset
standardize missing values
save modified data
```

Before approval:

```text
No mutation should occur.
```

After rejection:

```text
No mutation should occur.
State should record rejection.
```

---

## 12. Execution Rules

Executor must be deterministic.

Executor should not:

```text
choose tools
change plans
ask user questions
invent arguments
silently coerce variables
```

Executor only runs a verified action.

---

## 13. Observation and Evidence Rules

Every executed tool should produce structured output:

```text
ToolExecutionResult
Observation
analysis_run
artifacts if any
evidence keys if relevant
```

Do not rely only on chat text.

Deliverable gate must be able to inspect structured evidence.

---

## 14. Deliverable Gate Rules

Deliverable gate should check whether the TaskContract is satisfied.

It should not simply check whether a tool ran.

Correct:

```text
Required deliverable: regression summary
Evidence:
- model fit succeeded
- coefficient table exists
- R-squared exists
- interpretation generated
```

Incorrect:

```text
run_multiple_regression executed, so task complete
```

---

## 15. Final Response Rules

Final response must distinguish:

```text
completed deliverables
partial deliverables
missing deliverables
blocked deliverables
warnings
limitations
```

It must not claim full completion when deliverables are missing.

---

## 16. LangGraph Rules

### 16.1 Graph Nodes Should Be Thin

Nodes should call services.

Correct:

```python
def planner_node(state):
    return intelligent_planner.create_plan_from_state(state)
```

Incorrect:

```python
def planner_node(state):
    # hundreds of lines of routing, planning, schema checks, string matching
```

---

### 16.2 LangGraph Owns Orchestration, Not Business Intelligence

LangGraph should orchestrate:

```text
build_context
intent_router
planner
supervisor
verify
human_review
execute
summarize
deliverable_gate
final_response
```

Business logic belongs in services.

---

## 17. Runtime and UI Rules

### 17.1 UI Is Not the Brain

Streamlit must not:

```text
choose tools
repair plans
validate statistical method applicability
construct TaskContract
decide execution safety
```

UI should:

```text
collect user input
display snapshots
send events
show approval controls
```

---

### 17.2 Runtime Adapter Must Be Thin

Future runtime adapter may do:

```text
compile graph
manage thread_id
invoke graph
resume graph interrupts
build UI snapshot
handle runtime errors
```

Runtime adapter must not:

```text
call individual workflow nodes
implement route_after_intent
call supervisor_node directly
call verify_node directly
execute tools directly
```

---

## 18. Testing Requirements

### 18.1 Every Architecture Change Needs Tests

Add tests before or with the implementation.

Test categories:

```text
unit tests
architecture boundary tests
kernel integration tests
regression tests
```

---

### 18.2 Required Architecture Tests

Add or maintain:

```text
tests/architecture/test_domain_contract_boundaries.py
tests/architecture/test_analysis_tool_plugin_boundaries.py
tests/architecture/test_planner_boundaries.py
tests/architecture/test_runtime_boundaries.py
```

---

### 18.3 Required Kernel Tests

Add or maintain:

```text
tests/graph_kernel/test_dataset_overview_flow.py
tests/graph_kernel/test_direct_regression_flow.py
tests/graph_kernel/test_plan_generation_flow.py
tests/graph_kernel/test_clean_data_requires_review.py
tests/graph_kernel/test_deliverable_contract_flow.py
```

---

### 18.4 Tests Must Verify Behavior, Not Comments

Do not satisfy tests with fake comments or unused strings.

If a test checks for an import or class, it must represent actual architecture.

---

## 19. Baseline and Regression Policy

Before a phase:

```powershell
pytest -q relevant_tests
```

After a phase:

```powershell
pytest -q relevant_tests
```

If tests fail, Codex must classify:

```text
Existing failure before change
New failure caused by change
Test expectation outdated because architecture intentionally changed
```

Do not hide failures.

---

## 20. Git and Change Management

### 20.1 One Phase Per Commit

Good commits:

```text
add core domain contracts
align deliverable gate with canonical TaskContract
split analysis_tool_plugins base responsibilities
add dataset context refresh service
replace pattern router with structured IntentDecision router
implement goal-driven planner
```

Bad commit:

```text
fix stuff
big refactor
update files
misc changes
```

---

### 20.2 No Unrelated Cleanup

Do not reformat unrelated files.

Do not rename unrelated variables.

Do not move files not involved in the current phase.

---

### 20.3 Preserve Compatibility During Migration

When moving objects, first create compatibility exports.

Example:

```python
# core/schema.py
from core.domain.deliverable import TaskContract
```

Do not break all imports at once.

---

## 21. Required Report Format After Work

After any task, Codex must report:

```text
Summary:
Changed files:
New files:
Deleted files:
Architecture impact:
Compatibility impact:
Tests added:
Tests run:
Test results:
Known failures:
Manual verification:
Next recommended step:
```

If no tests were run:

```text
Tests run: Not run
Reason:
Risk:
```

---

## 22. Forbidden Final Responses

Forbidden:

```text
Done.
```

Forbidden:

```text
I fixed it.
```

Forbidden:

```text
This should work.
```

Forbidden:

```text
All tests pass.
```

unless tests were actually run and the output confirms it.

---

## 23. Current Refactor Roadmap

Follow this roadmap unless explicitly instructed otherwise.

```text
Phase 0:
  Freeze UI and record baseline.

Phase 1:
  Add core/domain contracts:
  IntentDecision, TaskSpec, PlanProposal, TaskContract.

Phase 2:
  Split analysis_tool_plugins/base.py.

Phase 3:
  Unify DatasetContext refresh.

Phase 4:
  Replace pattern-based interaction_intent with structured router.

Phase 5:
  Implement goal-driven intelligent planner.

Phase 6:
  Align supervisor, verifier, deliverable gate, final response around domain contracts.

Phase 7:
  Add graph kernel tests.

Phase 8:
  Cut app_v3 over to LangGraph runtime.

Phase 9:
  Clean legacy backend_turn and reorganize core.
```

Do not skip phases unless explicitly instructed.

---

## 24. Phase 1 Constraints

When implementing Phase 1:

Allowed:

```text
create core/domain/
add intent.py
add task.py
add plan.py
add deliverable.py
make core/schema.py re-export canonical TaskContract
rename deliverable gate internal contract to DeliverableGateContract
add architecture tests
```

Not allowed:

```text
rewrite planner
rewrite UI
delete backend_turn
rewrite graph.py
split plugin base
change supervisor prompt
```

---

## 25. Phase 2 Constraints

When implementing Phase 2:

Allowed:

```text
create arguments.py
create display.py
create reporting.py
create roles.py
create applicability.py
create policy_types.py
create result_builder.py
make base.py minimal
add compatibility exports temporarily
update imports gradually
add architecture tests
```

Not allowed:

```text
change tool behavior
change planner behavior
change UI behavior
change verifier behavior
```

---

## 26. Phase 3 Constraints

When implementing Phase 3:

Allowed:

```text
create context refresh service
make build_context_node use it
make dataset_upload use it
add tests for consistent capability_map
```

Not allowed:

```text
rewrite all dataset intelligence
change plugin registry semantics
change UI display
```

---

## 27. Phase 4 Constraints

When implementing Phase 4:

Allowed:

```text
create structured IntentDecision router
use LLM structured output if available
keep conservative fallback
write tests for common user requests
```

Not allowed:

```text
add more phrase patterns
make router pick tools directly
execute tools from router
```

---

## 28. Phase 5 Constraints

When implementing Phase 5:

Allowed:

```text
create intelligent planner service
use TaskSpec + DatasetContext + ToolRegistry
generate PlanProposal
write planner intelligence tests
```

Not allowed:

```text
dump all ready tools into plan
hardcode specific user phrases
planner mutates data
planner runs tools
```

---

## 29. Phase 6 Constraints

When implementing Phase 6:

Allowed:

```text
align supervisor output with TaskContract
make deliverable gate parse canonical contract
make final response report satisfied/missing deliverables
```

Not allowed:

```text
create another TaskContract
skip deliverable evidence checks
claim completion without evidence
```

---

## 30. Emergency Stop Conditions

Codex must stop and ask for direction if:

```text
A change requires deleting many files.
A public schema must be broken.
A test failure contradicts the intended architecture.
The same concept appears to have two or more active definitions.
The requested fix conflicts with AGENT_KERNEL_REFACTOR_PLAN.md.
Codex cannot determine which runtime path is currently active.
```

Do not guess in these cases.

---

## 31. Project Philosophy

This project is not a Streamlit toy.

This project is not a collection of statistical tools.

This project is an enterprise-grade statistical analysis agent kernel.

Every change should move the project toward:

```text
clear contracts
testable reasoning
structured evidence
safe execution
data-aware planning
minimal UI logic
thin LangGraph nodes
clean tool manifests
honest final responses
```

If a change makes the demo look better but makes the kernel less principled, reject the change.