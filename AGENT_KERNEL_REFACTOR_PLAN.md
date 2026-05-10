# Analysis Agent Kernel Refactor Plan

## 0. 文档目的

本文件定义当前 `analysis_agent_mvp` 项目的长期架构重构计划。

当前项目已经具备一些企业级 agent 的雏形：

- LangGraph 主流程
- workflow nodes
- supervisor / verifier / executor / summarizer
- plugin registry
- dataset intelligence
- data versioning
- human review gate
- UI snapshot
- Streamlit app_v3

但项目目前存在几个根本性问题：

1. 核心语义协议不统一。
2. `interaction_intent.py` 仍然依赖字符串 pattern matching。
3. planner 更像工具目录生成器，而不是真正的智能 planner。
4. `TaskContract` 存在多套定义，supervisor / deliverable gate / final response 之间 contract 不统一。
5. `analysis_tool_plugins/base.py` 混入太多职责，正在变成新的 god file。
6. dataset profile / capability map 有多个来源，可能导致 stale context。
7. UI runtime 和 LangGraph 主流程仍然没有完全统一。
8. LangGraph nodes 和业务逻辑边界不够清晰。
9. core 目录下 root-level 文件过多，但现在不应优先做机械搬家。

本计划的核心目标不是“修几个 bug”，而是把项目重构成一个真正的 **enterprise-grade analysis agent kernel**。

---

## 1. 总体原则

### 1.1 不先修 UI

当前阶段不要优先接 UI，不要急着删除 `backend_turn.py`，不要急着让 `app_v3.py` 直接调用 LangGraph。

原因：

- UI 只是外壳。
- 当前 agent 内核还不够聪明。
- 如果现在先接 UI，只会把旧的笨逻辑接到更正式的 LangGraph 主流程上。
- 真正要先修的是 agent kernel：intent、task、planner、contract、tool manifest、dataset context。

当前阶段 UI 冻结：

```text
ui/app_v3.py        暂时不改
core/controller/    暂时不删
backend_turn.py     暂时保留 legacy
```

### 1.2 不打 patch，不靠硬编码

禁止继续添加以下类型的代码：

```python
if "summary" in user_request:
    ...
elif "regression" in user_request:
    ...
```

禁止继续扩大：

```python
ADVISORY_PATTERNS = (...)
PLAN_ONLY_PATTERNS = (...)
DIRECT_TOOL_PATTERNS = (...)
```

这种 pattern list 只能作为短期 legacy fallback，不能作为主架构。

### 1.3 先定义协议，再改实现

重构顺序必须是：

```text
Domain contracts
  -> Tool manifest contracts
  -> DatasetContext
  -> Interaction router
  -> Intelligent planner
  -> Supervisor / verifier / deliverable gate alignment
  -> Graph kernel tests
  -> UI runtime cutover
```

不要先改 UI，不要先搬目录，不要先重写 graph。

### 1.4 LangGraph 只负责 orchestration

LangGraph node 应该变薄。

正确方向：

```python
def planner_node(state):
    task_spec = state["task_spec"]
    dataset_context = state["dataset_context"]
    plan = intelligent_planner.create_plan(task_spec, dataset_context)
    return {"pending_plan": plan}
```

错误方向:

```python
def planner_node(state):
    # 这里写大量 if/else
    # 这里自己猜变量
    # 这里直接拼工具列表
    # 这里直接决定最终报告
```

业务智能应该下沉到 services。

### 1.5 工具声明和工具执行分离

未来工具系统应该拆成两层：

```text
ToolManifest
  描述工具是什么、适用于什么数据、需要什么变量、会产生什么输出。

ToolImplementation
  真正执行工具。
```

planner 应该读取 manifest，而不是依赖工具执行函数内部逻辑。

## 2. 目标架构

长期目标目录结构：

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

当前项目不需要一次性改成这样。
应该采用 strangler-style refactor：

```text
当前项目不需要一次性改成这样。
应该采用 strangler-style refactor：
```

## 3. 目标依赖方向

依赖方向必须保持单向：

```text
UI
  ↓
runtime
  ↓
workflow / LangGraph
  ↓
services
  ↓
domain
```

工具系统：

```text
services / planner / verifier
  ↓
tool registry
  ↓
tool manifest
  ↓
tool implementation
```

禁止反向依赖：

```text
domain 不能 import LangGraph
domain 不能 import Streamlit
domain 不能 import UI snapshot
planner 不能 import Streamlit
plugin base 不能知道完整 report builder
tool manifest 不应该依赖 UI
LangGraph node 不应该包含大量业务判断
```

## 4. 当前主要问题清单

### 4.1 `interaction_intent.py` 仍然是 pattern matching

当前问题：

```text
用户自然语言请求
  -> substring matching
  -> advisory / plan_only / execute_plan / direct_tool / unknown
```

这导致 agent 对没写进 pattern 的表达方式非常迟钝。

目标：

```text
user request + dataset context + pending plan
  -> IntentDecision
  -> TaskSpec
```

### 4.2 planner 是工具目录生成器

当前 planner 倾向于：

```text
遍历 capability_map
把 ready / needs_user_choice 的工具全部列出来
```

这不是 planner。

真正 planner 应该：

```text
TaskSpec + DatasetContext + ToolRegistry
  -> PlanProposal
```

例如：

```text
What does the data look like?
```

应该生成：

```text
1. dataset overview
2. missingness report
3. numeric summary
4. categorical summary
5. correlation matrix if enough numeric variables
```

不应该生成 regression / ANOVA / clean_data。

### 4.3 `TaskContract` 多套定义

目前存在：

```text
core/schema.py
core/deliverables/contracts.py
```

问题：

- supervisor 输出一套 contract。
- deliverable gate 解析另一套 contract。
- final response 不一定知道 contract 是否真的满足。
- LLM 以为自己交付了，gate 也以为自己检查了，但双方 schema 不一致。

目标：

```text
core/domain/deliverable.py
  TaskContract
  RequiredDeliverable
  TaskConstraint
  DeliverableCheckResult
```

deliverable gate 内部如果需要 flat contract，应命名为：

```text
DeliverableGateContract
```

不能再叫 TaskContract。

### 4.4 `analysis_tool_plugins/base.py` 变成新的 god file

当前 `base.py` 混入了：

```text
ArgumentSchema
DisplayConfig
MetricDisplayConfig
TableDisplayConfig
VariableRoleSpec
ApplicabilityResult
VersioningPolicy
RepairPolicy
PlanningPolicy
format_p_value
format_number
default_extractor
build_generic_report_blocks
AnalysisToolPlugin
guardrail evaluation
analysis_run builder
```

问题：

- base 文件名义上是插件基类，实际管理了整个 plugin framework。
- planner、reporting、display、execution、analysis_runs 的职责混在一起。
- 以后每加一个新功能都容易继续往 base.py 塞东西。

目标：

```text
core/analysis_tool_plugins/
  base.py              # 只定义 AnalysisToolPlugin minimal runtime wrapper
  arguments.py         # ArgumentSchema
  display.py           # DisplayConfig, formatting
  reporting.py         # report block construction
  roles.py             # VariableRoleSpec
  applicability.py     # ApplicabilityResult
  policy_types.py      # VersioningPolicy, RepairPolicy, PlanningPolicy
  policies.py          # policy presets
  guardrails.py        # guardrail evaluation helpers
  result_builder.py    # analysis_run construction
```

更长期目标是迁移到：

```text
core/tools/
  manifest.py
  implementation.py
  registry.py
```

但短期先拆 plugin base。

### 4.5 dataset context 多个来源

当前可能存在：

```text
build_context_node 生成 dataset_profile_v2 / dataset_summary / capability_map
dataset_upload.py 又手写 basic capability_map
```

问题：

- upload 后的数据 context 和 graph turn 开始时的数据 context 可能不一致。
- clean_data 后 active data version 变化，但 profile / capability map 可能 stale。
- planner 可能基于旧数据做判断。

目标：

```text
core/data/context_refresh.py
```

或者：

```text
core/context/refresh.py
```

唯一负责：

```text
active_data_version_id
  -> dataframe
  -> DatasetContext
  -> dataset_profile
  -> dataset_summary
  -> capability_map
```

### 4.6 UI runtime 与 LangGraph 主流程分裂

当前 UI 通过：

```text
app_v3.py
  -> backend_turn.py
```

而 `backend_turn.py` 可能手写了一套半流程，没有真正完整使用 LangGraph。

最终目标：

```text
app_v3.py
  -> runtime/langgraph_runtime.py
  -> graph.invoke()
```

但是这个阶段不优先做。
先做好 kernel，再接 UI。

## 5. 统一核心协议

未来所有核心流程都围绕这些 domain objects：

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

# 6. Phase 0：冻结 UI 与建立基线

## 6.1 目标

冻结外围，不继续在 UI 上 debug 症状。

## 6.2 不做

本阶段不做：

```text
不改 app_v3.py
不删 backend_turn.py
不接 LangGraph runtime
不大规模搬 core 目录
不重写所有 planner
```

## 6.3 做

建立基线分支：

```PowerShell
git status
git checkout -b agent-kernel-refactor
```

提交当前状态：

```PowerShell
git add .
git commit -m "baseline before agent kernel refactor"
```

跑当前核心测试：

```PowerShell
pytest -q tests/deliverables
pytest -q tests/dataset_intelligence
pytest -q tests/planning
pytest -q tests/workflow
pytest -q tests/architecture
```

如果测试很多失败，记录到：

```text
docs/BASELINE_TEST_STATUS.md
```

不要一上来就修全部测试。
先记录失败现状，避免后面分不清是重构引入的问题还是原来就有的问题。

## 7. Phase 1：建立 `core/domain/`

### 7.1 目标

建立 agent kernel 的核心语义对象。

新建：

```text
core/domain/
  __init__.py
  intent.py
  task.py
  plan.py
  deliverable.py
```

### 7.2 `TaskSpec`

`TaskSpec` 表示用户真正想完成的统计任务。

示例：

```python
TaskSpec(
    goal_type="regression_modeling",
    user_goal="Fit a linear regression model for GPA using SATM.",
    source_user_request="run linear regression of GPA on SATM",
    target_variables=["GPA"],
    predictor_variables=["SATM"],
    requested_methods=["linear_regression"],
    confidence=0.95,
)
```

重要原则：

```text
TaskSpec 不是 tool call。
TaskSpec 不应该包含 run_multiple_regression 这种具体 plugin 细节。
TaskSpec 是自然语言和 planner 之间的桥梁。
```

### 7.3 `IntentDecision`

`IntentDecision` 表示 interaction router 的结构化输出。

示例：

```python
IntentDecision(
    intent="direct_analysis",
    confidence=0.92,
    reason="User explicitly requested a linear regression analysis.",
    task_spec=TaskSpec(...),
    should_execute=True,
)
```

重要原则：

```text
IntentDecision 不直接选择工具。
IntentDecision 可以包含 TaskSpec。
```

### `7.4 PlanProposal`

`PlanProposal` 表示 intelligent planner 的输出。

示例：

```python
PlanProposal(
    user_goal="Understand what the dataset looks like.",
    task_spec=TaskSpec(goal_type="dataset_overview"),
    status="ready",
    steps=[
        PlanStep(
            title="Inspect dataset overview",
            goal="Report shape, columns, and basic schema.",
            tool_name="inspect_dataset",
            execution_ready=True,
        ),
        PlanStep(
            title="Assess missingness",
            goal="Report missing values by column.",
            tool_name="missingness_report",
            execution_ready=True,
        ),
    ],
)
```

重要原则：

```text
PlanProposal 是 goal-driven。
PlanProposal 不是 capability_map 的简单展开。
```

### 7.5 `TaskContract`

`TaskContract` 是最终交付标准

示例：

```python
TaskContract(
    user_goal="Fit and summarize a regression model.",
    required_deliverables=[
        RequiredDeliverable(
            deliverable_id="model_fit",
            description="Fit the requested regression model.",
            satisfied_by=["run_multiple_regression"],
            required_evidence=["coef_table", "r_squared"],
        ),
        RequiredDeliverable(
            deliverable_id="interpretation",
            description="Explain model coefficients and limitations.",
            required_evidence=["model_summary_text"],
        ),
    ],
)
```

重要原则：

```text
TaskContract 描述交付物，不只是工具列表。
TaskContract 是 supervisor / deliverable_gate / final_response 的共同协议。
```

### 7.6 兼容策略

暂时不要删除 `core/schema.py`。

应该让：

```python
from core.schema import TaskContract
```

继续可用，但实际 re-export：

```python
from core.domain.deliverable import TaskContract
```

### 7.7 验收标准

搜索：

```PowerShell
Select-String -Path core\**\*.py,tests\**\*.py -Pattern "class TaskContract"
```

理想结果：

```text
core/domain/deliverable.py
```

允许短期存在 legacy adapter，但不能再有第二个 canonical TaskContract。

测试：

```PowerShell
pytest -q tests/deliverables
pytest -q tests/architecture/test_domain_contract_boundaries.py
```

## 8. Phase 2：拆分 `analysis_tool_plugins/base.py`

### 8.1 目标

防止 `analysis_tool_plugins/base.py` 继续变成新的 god file。

### 8.2 当前问题

`base.py` 当前混合了：

```text
插件基类
参数 schema
展示配置
报告块构建
变量角色
applicability
versioning policy
repair policy
planning policy
guardrail execution
analysis_run construction
```

这违反单一职责。

### 8.3 目标结构

短期目标：

```text
core/analysis_tool_plugins/
  base.py
  types.py
  arguments.py
  display.py
  reporting.py
  roles.py
  applicability.py
  policy_types.py
  policies.py
  guardrails.py
  result_builder.py
  registry.py
  execution.py
```

长期目标：

```text
core/tools/
  manifest.py
  implementation.py
  arguments.py
  roles.py
  applicability.py
  policies.py
  registry.py
  executor.py
  result_builder.py
```

### 8.4 各文件职责

`types.py`

只放函数类型别名：

```text
ExecuteFn
ExtractorFn
GuardrailFn
```

`arguments.py`

只放参数契约：

```text
ArgumentSchema
canonicalize_arguments
to_contract_dict
to_legacy_schema_dict
```

`display.py`

只放展示和格式化：

```text
DisplayConfig
MetricDisplayConfig
TableDisplayConfig
format_number
format_p_value
format_bool_yes_no
humanize_key
```

`reporting.py`

只放 report block 构建：

```text
default_extractor
build_generic_report_blocks
metric_rows_from_dict_with_display
normalize_table_from_list_with_display
```

`roles.py`

只放变量角色：

```text
VariableRoleSpec
```

`applicability.py`

只放工具适用性结果：

```text
ApplicabilityResult
```

`policy_types.py`

只放 policy 类型：

```text
VersioningPolicy
RepairPolicy
PlanningPolicy
```

`policies.py`

只放 policy presets：

```text
NON_MUTATING_VERSIONING
MUTATING_CHILD_VERSIONING
EDA_READY_PLANNING
NEEDS_USER_VARIABLES_PLANNING
DEFAULT_ANALYSIS_REPAIR
```

`guardrails.py`

只放 guardrail evaluation helper。

`result_builder.py`

只放 analysis_run 构建：

```text
build_analysis_run_for_plugin
```

### 8.5 `base.py` 最终职责

`base.py` 只保留：

```text
AnalysisToolPlugin
```

它可以有：

```text
tool_name
display_name
execute
extractor
requires_confirmation
argument_schema
guardrail_evaluators
display_config
method_family
variable_roles
applicability_checker
plan_step_builder
mutates_data
versioning_policy
repair_policy
planning_policy
```

但不应该包括：

```text
format_p_value
format_number
build_generic_report_blocks
default_extractor
build_analysis_run
metric table rendering
guardrail orchestration
```

### 8.6 迁移方式

不要一次删除旧代码。

采用兼容导出：

```text
Step 1: 新建目标模块。
Step 2: 从 base.py 复制代码到目标模块。
Step 3: base.py import/re-export 旧名字。
Step 4: 逐步修改 plugins / registry / planner / tests 的 import。
Step 5: 添加 architecture tests 防止 base.py 再膨胀。
Step 6: 确认测试稳定后，删除 base.py 的兼容 re-export。
```

### 8.7 验收标准

新增测试：

```text
tests/architecture/test_analysis_tool_plugin_boundaries.py
```

检查：

```text
base.py 不包含 format_p_value
base.py 不包含 build_generic_report_blocks
base.py 不包含 build_analysis_run
base.py 不包含 default_extractor
base.py 不包含 metric_rows_from_dict_with_display
```

测试：

```PowerShell
pytest -q tests/architecture/test_analysis_tool_plugin_boundaries.py
pytest -q tests/architecture/test_unified_analysis_tool_plugins.py
pytest -q tests/dataset_intelligence
pytest -q tests/planning
```

## 9. Phase 3：统一 DatasetContext

## 9.1 目标

建立 dataset context 的唯一来源。

## 9.2 当前问题

现在可能有：

```text
workflow/nodes/context.py 生成正式 profile/capability
ui_adapter/dataset_upload.py 生成 basic profile/capability
```

这会导致：

```text
upload 后 context 一套
graph turn 时 context 另一套
clean_data 后可能 stale
planner 读取到旧 profile
```

### 9.3 目标

新建：

```text
core/data/context_refresh.py
```

或者：

```text
core/context/refresh.py
```

推荐长期使用：

```text
core/data/context_refresh.py
```

因为这是数据层服务。

职责：

```text
state
  -> active_data_version_id
  -> active_data_path
  -> dataframe
  -> DatasetContext
  -> dataset_profile
  -> dataset_summary
  -> capability_map
```

### 9.4 DatasetContext

未来可定义：

```python
class DatasetContext(BaseModel):
    data_version_id: str
    path: str
    n_rows: int
    n_cols: int
    columns: List[ColumnProfile]
    numeric_columns: List[str]
    categorical_columns: List[str]
    missingness: Dict[str, Any]
    capability_map: Dict[str, Any]
    summary_text: str
```

### 9.5 应用位置

以下地方都应使用统一 refresh：

```text
build_context_node
dataset_upload.py
planner
supervisor prompt builder
verifier
capability_map generation
```

### 9.6 验收标准

测试：

```text
upload path 和 build_context path 产生同 schema 的 capability_map
clean_data 后下一轮 context 使用新的 active_data_version_id
planner 不直接读取旧 dataset_profile 字段
```

测试文件：

```text
tests/data/test_context_refresh.py
tests/workflow/test_build_context_uses_context_refresh.py
tests/ui_adapter/test_dataset_upload_uses_context_refresh.py
```

## 10. Phase 4：重做 interaction router

### 10.1 目标

废掉自然语言层面的 substring intent router。

### 10.2 分两层 router

Event router

deterministic，可以硬编码事件类型：

```text
run_plan
approve_human_review
reject_human_review
update_plan_step_choices
upload_dataset
```

这些不是自然语言理解。

User message router

自然语言请求必须输出：

```text
IntentDecision
TaskSpec
```

### 10.3 输入

router 输入：

```text
user_request
dataset_context summary
pending_plan summary
last assistant response
available high-level capabilities
```

### 10.4 输出

router 输出：

```python
IntentDecision(
    intent="direct_analysis",
    confidence=0.9,
    task_spec=TaskSpec(...),
    should_execute=True,
)
```

### 10.5 不允许

router 不允许直接选具体工具：

错误：

```python
intent = "run_multiple_regression"
```

正确：

```python
intent = "direct_analysis"
task_spec.goal_type = "regression_modeling"
task_spec.requested_methods = ["linear_regression"]
```

### 10.6 LLM Router

可以建立：

```text
core/services/interaction_router.py
```

它调用 LLM structured output。

但必须有 schema validation：

```text
LLM raw JSON
  -> IntentDecision.model_validate()
  -> fallback if invalid
```

fallback 只能保守：

```text
unknown
clarification
advisory
```

不能回到大量 substring matching。

### 10.7 验收测试

测试：

```text
"What does the data look like?"
  -> intent = dataset_overview
  -> task_spec.goal_type = dataset_overview

"run linear regression of GPA on SATM"
  -> intent = direct_analysis
  -> task_spec.goal_type = regression_modeling
  -> target_variables = ["GPA"]
  -> predictor_variables = ["SATM"]

"I don't know what to do with this data"
  -> intent = plan_analysis
  -> task_spec.goal_type = eda or dataset_overview

"drop rows with missing GPA"
 -> intent = modify_data
  -> task_spec.goal_type = data_cleaning
```

测试文件：

```text
tests/kernel/test_interaction_router.py
```

## 11. Phase 5：重做 Intelligent Planner

### 11.1 目标

从工具目录生成器升级为目标驱动 planner。

### 11.2 输入

```text
TaskSpec
DatasetContext
ToolRegistry / ToolManifest
```

### 11.3 输出

```
PlanProposal
```

### 11.4 Planner 不应该做的事

planner 不应该：

```text
遍历 capability_map 然后把所有 ready tools 塞进 plan
盲目推荐 regression
盲目推荐 ANOVA
盲目推荐 chi-square
对用户没问的任务生成过度计划
直接执行工具
```

### 11.5 Planner 应该做的事

planner 应该：

```text
理解任务目标
选择合理 method family
根据数据语义选择候选工具
判断变量是否缺失
判断哪些步骤 ready
判断哪些步骤需要用户选择
判断哪些步骤不推荐
输出 rationale
输出 expected deliverables
```

### 11.6 示例：dataset overview

输入：

```text
What does the data look like?
```

输出：

```text
Plan:
1. Inspect dataset shape and schema
2. Missingness report
3. Numeric summary
4. Categorical summary
5. Correlation matrix if numeric columns >= 2

Do not include:
- regression
- ANOVA
- chi-square
- clean_data
```

### 11.7 示例：linear regression

输入：

```text
run linear regression of GPA on SATM
```

输出：

```text
Plan:
1. Validate GPA is numeric
2. Validate SATM is numeric
3. Run multiple regression
4. Run regression diagnostics if model succeeds
5. Summarize coefficients and model limitations
```

### 11.8 示例：user asks for suggestions

输入：

```text
I don't know what to do with this data.
```

输出：

```text
Plan:
1. Dataset overview
2. Missingness assessment
3. Variable type audit
4. EDA
5. Recommend possible modeling/testing paths
```

Do not immediately execute a regression.

### 11.9 ToolManifest dependency

planner should read:

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

planner should not depend on:

```text
DisplayConfig
report block formatting
p-value formatting
analysis_run schema
Streamlit UI
```

### 11.10 验收测试

测试文件：

```text
tests/kernel/test_intelligent_planner.py
```

测试：

```text
dataset_overview 不生成 modeling steps
regression request 只选择 regression-related steps
data_cleaning request marks requires_confirmation
missing target variable causes needs_user_choice
categorical target does not select linear regression
continuous variables do not trigger chi-square by default
```

## 12. Phase 6：统一 Supervisor / Verifier / Deliverable Gate

### 12.1 目标

让以下组件共享同一套协议：

```text
TaskSpec
PlanProposal
ActionProposal
TaskContract
DeliverableCheckResult
```

### 12.2 Supervisor

supervisor 不应该随意发明 JSON。

它应该：

```text
读取 state.task_spec / pending_plan / task_contract
选择下一步 action
或者请求 planner repair
或者生成 final answer
```

### 12.3 Verifier

verifier 应该验证：

```text
ActionProposal 是否符合 tool manifest
arguments 是否满足 ArgumentSchema
变量是否存在
变量类型是否合适
clean_data 是否 requires_confirmation
data mutation 是否需要 human review
```

### 12.4 Deliverable Gate

deliverable gate 应该检查：

```text
TaskContract.required_deliverables
observations
analysis_runs
artifacts
evidence bundles
```

它不应该只看工具是否跑过。

### 12.5 Final Response

final response 应该基于：

```text
TaskContract
DeliverableCheckResult
Observation
EvidenceBundle
```

而不是只拼接最近的 tool result。

### 12.6 验收测试

测试文件：

```text
tests/kernel/test_task_contract_flow.py
tests/kernel/test_deliverable_gate_contract_alignment.py
```

测试：

```text
supervisor 输出 canonical TaskContract
deliverable_gate 能解析 canonical TaskContract
final_response 明确说明 satisfied / missing deliverables
partial result 不冒充 full completion
```

## 13. Phase 7：Graph Kernel Tests

### 13.1 目标

不碰 UI，直接测试 LangGraph kernel。

测试入口：

```python
from core.graph import create_graph_app
```

### 13.2 测试场景

建立：

```text
tests/graph_kernel/
  test_dataset_overview_flow.py
  test_direct_regression_flow.py
  test_plan_generation_flow.py
  test_clean_data_requires_review.py
  test_deliverable_contract_flow.py
```

### 13.3 场景 1：dataset overview

输入：

```text
What does the data look like?
```

期望：

```text
IntentDecision.intent = dataset_overview
TaskSpec.goal_type = dataset_overview
PlanProposal 不包含 regression / ANOVA
Final response 包含 dataset shape / missingness / summary
```

### 13.4 场景 2：direct regression

输入：

```text
run linear regression of GPA on SATM
```

期望：

```text
TaskSpec.goal_type = regression_modeling
Plan includes run_multiple_regression
Verifier checks GPA and SATM
Executor runs tool
Observation recorded
Deliverable satisfied
```

### 13.5 场景 3：clean data

输入：

```text
drop rows with missing GPA
```

期望：

```text
TaskSpec.goal_type = data_cleaning
Plan step mutates_data = True
requires_confirmation = True
verify routes to human_review
No mutation before approval
```

### 13.6 场景 4：suggest plan

输入：

```text
I don't know what to do with this data.
```

期望：

```text
PlanProposal generated
Plan status partially_ready or ready
No immediate destructive action
No irrelevant model execution
```

## 14. Phase 8：UI Runtime Cutover

### 14.1 前置条件

必须等以下阶段完成：

```text
Domain contracts
Tool plugin base split
DatasetContext unified
Interaction router rewritten
Intelligent planner rewritten
Supervisor / deliverable gate aligned
Graph kernel tests passing
```

然后才接 UI。

### 14.2 目标

让 app_v3 使用唯一 LangGraph 主流程：

```text
app_v3.py
  -> runtime/langgraph_runtime.py
  -> core.graph.create_graph_app()
```

### 14.3 新建 runtime adapter

```text
core/runtime/langgraph_runtime.py
```

职责：

```text
compile graph
manage thread_id
invoke graph
resume human_review interrupts
convert graph state to ui_snapshot
handle runtime errors
```

不允许：

```text
不允许 runtime adapter 自己写 route_after_intent
不允许 runtime adapter 自己调用 supervisor_node
不允许 runtime adapter 自己执行 tool
不允许 runtime adapter 变成第二个 backend_turn
```

### 14.4 app_v3 修改

`app_v3.py` 从：

```python
from core.controller.backend_turn import run_backend_turn
```

改成：

```python
from core.runtime.langgraph_runtime import run_langgraph_turn
```

### 14.5 backend_turn 处理

初期：

```text
backend_turn.py 保留为 legacy
app_v3 不再 import 它
app_v2 如果还用，就暂时留着
```

等确认不再需要 app_v2 后，再删除：

```text
core/controller/backend_turn.py
tests/controller/test_backend_turn_*
```

## 15. Phase 9：core 目录整理

### 15.1 前置条件

只有在 kernel 稳定后，才做目录重组。

不要一开始就机械搬文件。

### 15.2 目标

把 root-level core 文件逐步迁移：

```text
core/schema.py
core/context_builder.py
core/report_builder.py
core/guardrails.py
core/data_versions.py
core/analysis_runs.py
```

### 15.3 迁移原则

每个旧文件先变成 compatibility export。

例如：

```python
# core/schema.py
from core.domain.action import ActionProposal
from core.domain.deliverable import TaskContract
```

不要直接删除旧 import path。

### 15.4 推荐迁移

```text
core/schema.py
  -> core/domain/

core/context_builder.py
  -> core/services/context_builder.py

core/report_builder.py
  -> core/reporting/

core/guardrails.py
  -> core/quality/

core/data_versions.py
  -> core/data/versions.py

core/analysis_runs.py
  -> core/results/analysis_runs.py
```

## 16. Architecture Tests

必须增加 architecture tests 防止项目再次退化。

### 16.1 domain boundary

```text
tests/architecture/test_domain_contract_boundaries.py
```

检查：

```text
TaskContract 只有一个 canonical 定义
core/schema.py re-export domain TaskContract
deliverables/contracts.py 不定义第二个 TaskContract
domain 不 import LangGraph
domain 不 import Streamlit
```

### 16.2 plugin boundary

```text
tests/architecture/test_analysis_tool_plugin_boundaries.py
```

检查：

```text
base.py 不包含 format_p_value
base.py 不包含 build_generic_report_blocks
base.py 不包含 build_analysis_run
base.py 不包含 default_extractor
base.py 不包含 report table normalization
```

###16.3 planner boundary

```text
tests/architecture/test_planner_boundaries.py
```

检查：

```text
planner 不 import Streamlit
planner 不 import UI snapshot
planner 不直接 import display formatting
planner 使用 TaskSpec / DatasetContext / ToolRegistry
```

### 16.4 runtime boundary

```text
tests/architecture/test_runtime_boundaries.py
```

检查：

```text
runtime/langgraph_runtime.py 使用 create_graph_app
runtime 不 import individual workflow nodes
runtime 不 import route_after_intent
runtime 不手写 supervisor/verify/execute flow
```

## 17. 禁止事项

整个重构期间禁止：

```text
1. 为了通过一个输入，加新的字符串 pattern。
2. 在 UI 层写业务逻辑。
3. 在 LangGraph node 里塞大量统计判断。
4. 在 plugin base.py 里继续加 display/report/analysis_run helper。
5. 新增第二套 TaskContract。
6. planner 直接列出所有 ready tools。
7. verifier 绕过 tool manifest。
8. dataset_upload.py 手写 basic capability_map。
9. runtime adapter 自己手写 graph routing。
10. 为了测试过，在生产文件里加假注释或假字符串。
```

## 18. 推荐提交策略

每个 phase 单独提交。

示例：

```text
commit 1: add core domain contracts
commit 2: align schema and deliverable contracts with domain TaskContract
commit 3: split analysis_tool_plugins base responsibilities
commit 4: add unified dataset context refresh service
commit 5: replace pattern intent router with structured IntentDecision router
commit 6: implement goal-driven intelligent planner
commit 7: align supervisor and deliverable gate with TaskContract
commit 8: add graph kernel integration tests
commit 9: cut app_v3 over to LangGraph runtime
commit 10: clean legacy backend_turn and reorganize core
```

不要一个 commit 做所有事情。

## 19. 每阶段验收模板

每个 phase 完成后记录：

```text
Phase:
Goal:
Files changed:
New files:
Deleted files:
Compatibility maintained:
Tests added:
Tests run:
Known failures:
Architecture boundary protected:
Next phase:
```

可以在：

```text
docs/REFACTOR_LOG.md
```

持续记录。

## 20. 最终成功标准

重构完成后，系统应该满足：

```text
1. 用户请求先转成 IntentDecision 和 TaskSpec。
2. planner 根据 TaskSpec + DatasetContext + ToolManifest 生成 PlanProposal。
3. planner 不再是 capability_map tool catalog renderer。
4. TaskContract 只有一套 canonical 定义。
5. deliverable_gate 和 supervisor 使用同一套 contract。
6. analysis_tool_plugins/base.py 只保留 plugin minimal definition。
7. tool display/reporting/result building 从 base.py 拆出。
8. DatasetContext 只有一个来源。
9. LangGraph nodes 变薄，业务逻辑下沉到 services。
10. app_v3 最终接入 LangGraph runtime，而不是 backend_turn 手写流程。
11. graph-level kernel tests 能验证 agent 内核。
12. architecture tests 能防止重新叠屎山。
```

## 21.项目理念

这个项目不是一个 Streamlit 数据分析 demo。

目标是：

```text
一个企业级统计分析 agent kernel
```

它应该具备：

```text
可解释的任务理解
可验证的计划生成
数据语义感知
工具适用性约束
人类确认边界
结果证据链
deliverable 检查
可测试的 agent kernel
清晰的架构边界
```

任何修改如果只是让当前 demo 看起来能跑，但破坏这些长期目标，都不应该接受。