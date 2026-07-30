# 项目开发准则

## 项目文档

- 开发进度记录在 `@PROGRESS.md`
- 开发计划记录在 `@DEVELOPMENT_PLAN.md`

开始任何开发任务前，必须先阅读：

1. `@DEVELOPMENT_PLAN.md` 确认当前任务目标
2. `@PROGRESS.md` 了解已有实现状态和历史修改

---

## 开发流程

### 普通任务

对于不涉及 `DEVELOPMENT_PLAN.md` 的小型修改：

1. 分析当前代码结构
2. 确认修改范围
3. 直接实施修改
4. 完成后更新必要的文档

### 计划任务

对于涉及 `DEVELOPMENT_PLAN.md` 中定义的功能：

必须遵循以下流程：

1. 进入 PLAN 模式
2. 根据当前代码状态生成详细 TODO
3. 等待用户确认 TODO
4. 用户确认后再进入实现模式
5. 按 TODO 执行修改

未经用户确认，不允许直接实现计划任务。

---

## 大型修改规范

以下情况属于大型修改：

- 新增核心功能
- 修改整体架构
- 引入新的框架或依赖
- 修改数据库结构
- 修改 API 设计
- 大范围重构
- 涉及 `DEVELOPMENT_PLAN.md` 的任务

大型修改完成后必须：

1. 更新 `@PROGRESS.md`
   - 记录已完成内容
   - 记录关键实现细节
   - 记录当前项目状态

2. 更新 `@DEVELOPMENT_PLAN.md`
   - 标记已完成任务
   - 调整后续计划
   - 添加新的待办事项（如果有）

---

## 代码修改规范

修改代码时：

- 优先保持现有项目结构
- 不随意重构无关代码
- 不删除已有功能，除非明确要求
- 引入新依赖前说明原因
- 修改公共接口时说明影响范围

---

## 测试要求

完成代码修改后：

- 优先运行已有测试
- 如果没有测试，需要说明验证方式
- 对关键功能提供测试结果

---

## 文档同步原则

代码状态必须与项目文档保持一致。

禁止出现：

- 文档描述的功能不存在
- 已完成任务仍显示未完成
- 代码实现与开发计划不一致

如果发现文档过时，应优先更新文档。

---

## Git 提交规范

### Commit 原则

每次 commit 应满足：

- 一个 commit 尽量只包含一个逻辑变更
- commit message 必须清晰描述修改内容
- 禁止使用无意义描述：
  - update
  - fix
  - change
  - modify
  - test

---

### Commit Message 格式

采用 Conventional Commits 格式：

type 类型：

| 类型 | 使用场景 |
| - | --- |
| feat | 新功能 |
| debug | Bug 修复 |
| refactor | 重构，不改变功能 |
| docs | 文档修改 |
| test | 测试相关 |
| perf | 性能优化 |
| build | 构建系统或依赖修改 |
| chore | 其他维护修改 |

示例：

feat: add vector database retrieval module

fix: resolve agent memory persistence issue

refactor: simplify tool calling architecture

docs: update development progress

---

### Commit 前检查清单

提交代码前必须检查：

#### 1. 修改范围

确认：

- [ ] 修改内容符合当前任务目标
- [ ] 没有包含无关修改
- [ ] 没有删除未确认的重要代码
- [ ] 没有提交临时文件

#### 2. 代码质量

确认：

- [ ] 代码可以正常运行
- [ ] 新增功能已有基本验证
- [ ] 没有明显 debug 输出
- [ ] 没有硬编码敏感信息

#### 3. 测试检查

如果项目存在测试：

- [ ] 已运行相关测试
- [ ] 测试结果通过
- [ ] 新功能添加必要测试

如果无法运行测试：

必须说明原因。

#### 4. 文档同步

如果修改涉及：

- 架构变化
- 新功能
- API变化
- 开发计划任务

必须同步更新：

- `@PROGRESS.md`
- `@DEVELOPMENT_PLAN.md`

#### 5. Git 状态检查

提交前执行：

```bash
git status
git diff

确认：

 只提交预期文件
 没有敏感信息
 没有大体积文件
 没有 IDE 配置垃圾文件
Commit 行为约束

Agent 不允许：

未检查 diff 直接 commit
未运行验证直接声明完成
将多个无关任务合并到一个 commit
自动 push 到远程仓库

除非用户明确要求，否则：

只创建 commit
不执行 push
不修改 Git 历史记录（rebase/reset 等）
