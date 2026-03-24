---
name: jike-profile-persona
description: 获取即刻主页最近动态，处理 web.okjike.com 登录二维码，并生成两类分析结果：直接做人物侧写，或结合用户择偶偏好做关系适配分析。适用于用户提供即刻主页链接，并希望看看这个人大概是什么类型，或他是否贴合自己找对象需求的场景。
version: 0.1.0
metadata:
  openclaw:
    requires:
      bins:
        - python3
---

# 即刻主页分析小玩具

## 概览

这是一个偏小玩具性质的 skill。

它的核心能力很直接：给我一个即刻主页，我去抓最近的动态；抓到之后，再拿这些文本做分析。

目前默认有两个场景：

1. 直接看人
用户只给一个即刻主页链接，我就根据对方最近的动态，写一份人物侧写。重点是看这个人大概是什么气质、怎么说话、在意什么、有没有明显的反差感。

2. 红娘模式
用户除了给链接，还会补一段自己的择偶要求，比如想找什么样的人、受不了什么、最想要什么相处感。我就站在“朋友帮你把关”的角度，看这个人和用户的需求贴不贴，吸引点在哪里，风险点又在哪里。

无论是哪种模式，本质上都只是基于公开动态做文本观察，不是心理诊断，也不是强行算姻缘。

## 场景说明

- 基础侧写更适合“我想看看这个人大概是什么类型”。
- 红娘模式更适合“你帮我看看，这个人像不像我会喜欢、也适合相处的那种人”。
- 这两个场景都鼓励写得有人味一点，但判断必须能落回具体动态证据。

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

如果只是基础侧写，到这里就够了。

如果用户想走“红娘模式”，还需要把他对理想伴侣的描述一起传给脚本。可选两种方式：

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

不要把它理解成“机械打标签”的工具。脚本负责抓取和整理，真正的分析应该读语料、带点人味，但也别离开证据乱飞。

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
