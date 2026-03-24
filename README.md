# jike-profile-persona

一个用于 Claw/Codex 的即刻分析 skill，支持：

- 抓取即刻主页最近最多 200 条动态
- 生成人物侧写
- 结合用户择偶偏好，生成朋友视角的关系适配分析

## 目录说明

- `SKILL.md`：skill 的主说明和元数据
- `scripts/jike_profile_persona.py`：登录、抓取、语料整理、提示词输入文件生成
- `references/persona-prompt.md`：基础人物侧写提示词
- `references/compatibility-prompt.md`：关系适配提示词

## 说明

- 依赖 `python3`
- 通过即刻 Web 的登录态接口抓取数据，需要扫码登录
- `2026-03-23` 已尝试发布到 ClawHub，但被 ClawHub 后端错误阻塞，所以当前公开分发方式以 GitHub 仓库为准
