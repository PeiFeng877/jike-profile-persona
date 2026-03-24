---
name: jike-profile-persona
description: 获取即刻主页最近动态，处理 web.okjike.com 登录二维码，并生成两类分析结果：基于文本证据的人物侧写，或结合用户择偶偏好的关系适配分析。适用于用户提供即刻主页链接，并希望抓取、总结、画像或判断是否适合接触的场景。
version: 0.1.0
metadata:
  openclaw:
    requires:
      bins:
        - python3
---

# 即刻主页人物分析

## 概览

运行内置脚本，抓取一个即刻主页最近最多 200 条动态，整理成标准化语料，并生成可直接用于分析的提示词输入文件。

这个 skill 支持两种分析场景：
- 基础侧写：输出一份有画面感、但有证据的人物画像
- 关系适配：结合用户自己的择偶要求，给出朋友视角的适配建议

这两种分析都只是基于文本内容的推断，不是心理诊断，也不是“算姻缘”。

## 工作流

1. 规范化输入。
支持：
- `https://m.okjike.com/users/<id>`
- `https://web.okjike.com/u/<username>`
- 即刻用户名或 id 原文

2. 选择输出目录。
默认使用当前任务目录下的 `<cwd>/jike-profile-output`，除非用户明确指定了别的位置。

3. 运行抓取脚本。

```bash
python3 /Users/Icarus/.codex/skills/jike-profile-persona/scripts/jike_profile_persona.py "<profile-url-or-username>" --limit 200 --out-dir "<output-dir>"
```

如果用户还提供了自己的理想对象要求、期待、雷点或关系顾虑，就把这些内容一起传给脚本。可选两种方式：

```bash
python3 /Users/Icarus/.codex/skills/jike-profile-persona/scripts/jike_profile_persona.py "<profile-url-or-username>" --limit 200 --out-dir "<output-dir>" --match-brief "<用户偏好描述>"
```

或者：

```bash
python3 /Users/Icarus/.codex/skills/jike-profile-persona/scripts/jike_profile_persona.py "<profile-url-or-username>" --limit 200 --out-dir "<output-dir>" --match-brief-file "<偏好描述文件的绝对路径>"
```

4. 处理登录。
如果脚本打印出 `Login required`，说明需要即刻登录态。脚本会在输出目录生成二维码图片。
在 app 里把这个本地图片展示给用户：

```markdown
![Jike login QR](/absolute/path/to/jike-login-qr.png)
```

提醒用户使用即刻 App 内置扫一扫，不要用系统相机或微信扫码。如果用户反馈一直加载中，就生成新的二维码再扫一次。

5. 返回产物。
脚本会写出：
- `<username>.updates.json`
- `<username>.updates.corpus.md`
- `<username>.analysis-input.md`
- `<username>.match-analysis-input.md`：只有在传入 `--match-brief` 或 `--match-brief-file` 时才会生成
- `jike-session.json`：用于复用 refresh token
- `jike-login-qr.png`：仅在需要登录时生成

6. 选择正确的提示词输入文件。
用：
- `<username>.analysis-input.md` 做基础人物侧写
- `<username>.match-analysis-input.md` 做关系适配/择偶判断

这些输入文件里已经包含：
- 分析语气和写法约束
- 主页元信息
- 标准化后的动态语料
- 在关系适配场景下，用户自己的偏好描述

不要再退回到旧的“正则分类 + 固定模板”思路。脚本负责抓取和打包，最终分析由模型完成。

7. 清楚说明样本限制。
如果结果少于 200 条，要明确告诉用户：当前抓到的就是这个账号此时主页流里可拿到的动态，不要暗示是脚本提前停了，除非确实发生错误。

## 输出规则

- 尽量引用生成出来的语料文件或提示词输入文件，不要凭记忆复述。
- 结论必须有证据，优先引用具体动态片段和日期。
- 要明确说明：这是内容风格/人物外观层面的推断，不是临床或心理诊断，也不是确定性的婚恋结论。
- 如果用户想要更严谨或更收敛的分析边界，读取 [analysis-rubric.md](references/analysis-rubric.md)。
- 如果用户想调整基础侧写的风格、锐度或画面感，改 [persona-prompt.md](references/persona-prompt.md)，不要改抓取逻辑。
- 如果用户想让关系适配分析更俏皮、更毒舌或更克制，改 [compatibility-prompt.md](references/compatibility-prompt.md)。

## 说明

- 脚本在扫码登录后，使用即刻 Web 的认证接口抓取数据。
- 当前实现基于用户主页动态流抓取；如果账号本身主页动态不足 200 条，返回数量会少于请求值。
- 如果输出目录里已经有 `jike-session.json`，优先复用；只有 refresh 失败时才重新登录。

## 资源

- `scripts/jike_profile_persona.py`：登录、抓取、语料生成、提示词输入文件生成
- `references/analysis-rubric.md`：分析边界和证据规则
- `references/persona-prompt.md`：基础人物侧写提示词
- `references/compatibility-prompt.md`：关系适配提示词
