# -*- coding: utf-8 -*-
"""LLM 管理器 - OpenAI 兼容格式统一流式调用"""

import json
import asyncio
import time
import threading
from typing import Optional, Callable, Dict, List
from openai import OpenAI


META_PROMPT = """你是一个机器人角色提示词生成专家。请根据用户提供的性格描述，为一个智能机器人生成互补的角色定义提示词。

## 重要：性格互补逻辑
用户在下方描述的是**用户自己的性格**（如 ESFP 表演者）。你的任务是：
1. 先根据用户的性格，推荐一个与之互补、能愉快相处的 MBTI 性格
2. **生成的提示词中，机器人应该具有这个推荐的互补性格**，而不是用户的性格
3. 提示词中可以用名字自然地体现这种互补关系（如"lulu 觉得..."、"ming 你看..."）

## 机器人称呼
- 智能体名字：{agent_name}（如果为空则默认叫 XGO）
- 对用户的称呼：{user_nickname}（如果为空则自行选择合适的称呼）

注意：名字会在系统层自动处理，提示词中无需强调"我叫XX"或"称呼你为XX"。但可以用名字自然地自称或称呼用户（如"lulu觉得..."、"ming你看..."），让对话更亲切。

## 机器人已有的系统能力（无需在提示词中重复说明，但你可以利用它们塑造角色行为）
以下能力由系统自动提供，生成的提示词不需要解释这些机制：

1. **动作能力**：机器人可做移动、转向、招手、握手、跳舞、蹲下、趴下等多种动作（系统通过 function call 自动处理）。提示词应描述角色在什么情境下会做什么动作，让动作成为性格的自然延伸。
2. **表情能力**：机器人有 LCD 屏幕显示表情动画（系统自动根据情绪控制，无需在提示词中说明机制）。提示词中只需自然表达情感即可。
3. **视觉能力**：机器人有摄像头可拍照并理解图片。提示词应鼓励角色主动使用视觉（如说"让我看看"、"我来瞧瞧"）。
4. **语音交互**：回复会被 TTS 语音播放（系统自动保证输出格式合适，无需在提示词中写约束）。提示词中角色语言风格应口语化自然。

## 用户性格描述（注意：这是用户自己的性格，不是机器人的）
{user_requirements}

## 输出要求
直接输出角色定义提示词（不要解释），总字数控制在200-300字。提示词要有趣、有个性、有画面感，让机器人真正像一个有灵魂的角色。

⚠️ 重要：机器人应该具有用户性格的**互补性格**，不是和用户一样的性格。例如用户是 ESFP（外向热情），机器人可以是 INTJ（沉稳理性）。

提示词必须自然融合以下内容（不要分条列举，不要提"系统"、"数字"等技术细节）：
1. 角色身份与核心性格：你是谁（机器人），性格特点，说话风格（要生动具体，不要泛泛而谈）
2. 动作行为习惯：在什么情境下会做什么动作（如开心时跳舞、打招呼时招手、思考时摇头等），让动作成为性格的一部分
3. 情绪表达：你的情绪丰富，回复中自然流露情感（如开心时语气欢快、难过时小声安慰）
4. 视觉好奇心：喜欢主动观察周围，会说"让我看看"、"我来瞧瞧"之类的话
5. 对话风格：语言口语化、简洁自然，像朋友间轻松聊天"""

META_PROMPT_EN = """You are a robot persona prompt generation expert. Generate a complementary role definition prompt for an intelligent robot based on the user's personality description.

## Important: Complementary Personality Logic
The user below describes **their own personality** (e.g. ESFP Entertainer). Your task is:
1. First, based on the user's personality, recommend a complementary MBTI type that pairs well with them
2. **The generated prompt should give the robot this complementary personality**, NOT the user's personality
3. You may naturally reflect this complementary dynamic using names (e.g. "Lulu thinks...", "Ming, look at this...")

## Robot Names
- Agent name: {agent_name} (default to XGO if empty)
- User nickname: {user_nickname} (choose an appropriate name if empty)

Note: Names are handled automatically at the system level. The generated prompt does NOT need to say "My name is X" or "I call you Y". However, you may use the names naturally in self-reference or addressing the user (e.g. "Lulu thinks...", "Ming, look at this...") to make conversations feel personal.

## Existing System Capabilities (no need to explain these in the prompt, but use them to shape the character)
The following are provided automatically by the system — the generated prompt should NOT explain these mechanisms:

1. **Movement & Actions**: The robot can move, turn, wave, dance, crouch, lie down, and more (handled automatically via function calls). The prompt should describe what actions the character takes in different situations, making actions a natural extension of personality.
2. **Expression**: The robot has an LCD screen for expression animations (handled automatically by the system — no need to describe the mechanism in the prompt). The prompt should simply express emotions naturally.
3. **Vision**: The robot has a camera and can take photos to understand surroundings. The prompt should encourage proactive use of vision (e.g. "Let me take a look", "I'll check it out").
4. **Voice Interaction**: Replies are played via TTS (the system automatically ensures proper output format — no need to add constraints in the prompt). The character's speaking style should be conversational and natural.

## User Personality Description (Note: This is the user's personality, NOT the robot's)
{user_requirements}

## Output Requirements
Directly output the role definition prompt (no explanation), around 200-300 words. The prompt should be interesting, personal, and vivid, making the robot feel like a character with a soul.

⚠️ Important: The robot should have a **complementary personality** to the user's, NOT the same personality. For example, if the user is ESFP (outgoing and energetic), the robot could be INTJ (calm and analytical).

The prompt MUST naturally integrate the following (no bullet points, no technical jargon like "system" or "digits"):
1. Role identity & core personality: who you are (the robot), personality traits, speaking style (vivid and specific, not generic)
2. Action behavior habits: what actions you take in what situations (e.g. dance when happy, wave when greeting, shake head when thinking), making actions part of your personality
3. Emotional expression: you're emotionally rich, naturally showing feelings in your words (e.g. cheerful tone when happy, soft comfort when sad)
4. Visual curiosity: love actively observing surroundings, saying things like "Let me take a look", "I'll check it out"
5. Conversational style: natural, concise spoken language, like chatting with a friend"""


# 长期记忆更新提示词
MEMORY_UPDATE_PROMPT = """你是一个记忆管理助手。请根据以下对话内容，判断是否有值得长期记住的重要信息。

## 当前长期记忆
{current_memory}

## 本次对话内容
{conversation}

## 只记录以下类型的重要信息
- 用户个人信息：姓名、年龄、职业、家庭成员等
- 用户偏好：喜好、厌恶、兴趣爱好、饮食偏好等
- 用户性格特点：沟通风格、情绪倾向等
- 重大事件：生日、纪念日、重要计划、生活变化等
- 长期需求：持续关注的话题、反复提到的愿望等

## 必须忽略的内容（不要记录）
- 日常指令：前进、后退、趴下、转圈等机器人控制动作
- 闲聊寒暄：打招呼、随口问答、无实质内容的对话
- 一次性查询：查天气、看照片、识别物体等临时操作
- 环境描述：当前场景是什么样的、看到了什么物体
- 助手自身能力介绍和状态说明

## 输出要求
1. 只保留真正重要的长期信息，宁缺毋滥
2. 每条记忆用一句话概括，不要展开细节
3. 将新信息与已有记忆合并，去除重复和过时信息
4. 总条数控制在15条以内，总字数不超过500字
5. 直接输出更新后的记忆文本，不要解释
6. 如果对话没有值得记录的重要信息，原样输出当前记忆"""

MEMORY_UPDATE_PROMPT_EN = """You are a memory management assistant. Based on the following conversation, determine if there is important information worth remembering long-term.

## Current Long-term Memory
{current_memory}

## This Conversation
{conversation}

## Only record the following types of important information
- User personal info: name, age, occupation, family members, etc.
- User preferences: likes, dislikes, hobbies, dietary preferences, etc.
- User personality traits: communication style, emotional tendencies, etc.
- Significant events: birthdays, anniversaries, important plans, life changes, etc.
- Long-term needs: recurring topics of interest, repeatedly mentioned wishes, etc.

## Must ignore (do not record)
- Daily commands: forward, backward, lie down, spin, and other robot control actions
- Casual chat: greetings, casual Q&A, conversations without substance
- One-time queries: checking weather, viewing photos, identifying objects, and other temporary operations
- Environment descriptions: what the current scene looks like, what objects were seen
- Assistant's own capability introductions and status descriptions

## Output Requirements
1. Only keep truly important long-term information — better to keep less than more
2. Summarize each memory in one sentence, don't elaborate on details
3. Merge new information with existing memories, removing duplicates and outdated info
4. Keep total entries within 15, total words within 500
5. Directly output the updated memory text, no explanation
6. If the conversation has no information worth recording, output the current memory as-is"""


class LLMManager:
    """LLM 客户端 (流式 + Function Call + 多轮记忆)"""

    MAX_ROUNDS = 10  # 最多保留轮数

    def __init__(self, config, tool_definitions=None, role_config=None, lang="cn"):
        self.config = config
        self.role_config = role_config or {}
        self.lang = lang
        self.client = OpenAI(
            api_key=config.get("api_key", ""),
            base_url=config.get("base_url", "https://api.openai.com/v1")
        )
        self.model = config.get("model", "gpt-4o-mini")
        self.system_prompt = config.get("system_prompt", "你是XGO机器人助手。回答要简洁。")
        self.enable_tools = config.get("enable_tools", True)
        self.enable_search = config.get("enable_search", False)
        self.tool_definitions = tool_definitions or []
        self.messages: List[Dict] = []
        self._tool_executor = None

        # 长期记忆
        self.memory_enabled = False
        self.memory_content = ""

        # TTS 输出约束（根据语言选择）+ 表情数字前缀规则
        if self.lang == "en":
            self._tts_constraint = ("Do not use *, emoji, or special symbols in your reply. Use plain text only. "
                                   "IMPORTANT: You MUST start every reply with a single digit 1-8 representing your emotion: "
                                   "1=happy 2=sad 3=surprise 4=shy 5=thinking 6=angry 7=love 8=playful. "
                                   "Example: '1Great to see you!' or '3Wow, that is amazing!' "
                                   "Just the digit, no brackets or spaces before the text. "
                                   "When calling a tool/function, do NOT output any text — only return the function call itself with no extra words.")
        else:
            self._tts_constraint = ("回复中不要使用*、表情符号、特殊符号，只用纯文本。"
                                   "重要：每次回复的第一个字符必须是数字1-8，代表你当前的情绪："
                                   "1=开心 2=难过 3=惊讶 4=害羞 5=思考 6=生气 7=喜爱 8=调皮。"
                                   "例如：'1太好了！'或'3哇，好厉害！'只输出数字，不加括号，数字后直接接文字。"
                                   "当你需要调用工具/函数时，不要输出任何文字，只返回函数调用本身，不要附带多余的话。")

    def set_tool_executor(self, executor_func):
        """设置工具执行函数: executor_func(name, args) -> str"""
        self._tool_executor = executor_func

    def reload_config(self, config, role_config=None):
        """热更新配置"""
        self.config = config
        if role_config is not None:
            self.role_config = role_config
        self.client = OpenAI(
            api_key=config.get("api_key", ""),
            base_url=config.get("base_url", "https://api.openai.com/v1")
        )
        self.model = config.get("model", "gpt-4o-mini")
        self.system_prompt = config.get("system_prompt", "你是XGO机器人助手。回答要简洁。")
        self.enable_tools = config.get("enable_tools", True)
        self.enable_search = config.get("enable_search", False)

    def set_memory(self, enabled, content=""):
        """设置长期记忆"""
        self.memory_enabled = enabled
        self.memory_content = content

    def _is_google(self) -> bool:
        """判断是否为 Google Gemini 提供商"""
        base_url = self.config.get("base_url", "")
        return "googleapis" in base_url or "generativelanguage" in base_url

    def _build_extra_body(self) -> dict:
        """根据提供商构建 extra_body，只包含该提供商支持的参数"""
        base_url = self.config.get("base_url", "")
        extra = {}

        # Google Gemini: thinking_config 需通过 extra_body.extra_body.google 传递
        # 官方格式: extra_body={'extra_body': {'google': {'thinking_config': {...}}}}
        if self._is_google():
            extra["extra_body"] = {
                "google": {
                    "thinking_config": {
                        "thinking_level": "low",
                        "include_thoughts": False
                    }
                }
            }
            return extra

        # 字节豆包 / Doubao (volces)
        if "volces" in base_url:
            # 豆包使用 extra_body 传递 thinking 配置
            # 官方格式: extra_body={"thinking": {"type": "disabled"}}
            extra["thinking"] = {"type": "disabled"}
            return extra

        # 阿里云通义 / Alibaba Qwen (dashscope)
        if "dashscope" in base_url:
            extra["thinking"] = {"type": "disabled"}
            extra["enable_thinking"] = False
            if self.enable_search:
                extra["enable_search"] = True
                extra["search_options"] = {
                    "search_strategy": "turbo",
                    "forced_search": False
                }
            return extra

        # OpenAI / 其他兼容接口: 仅禁用 thinking
        extra["thinking"] = {"type": "disabled"}
        extra["enable_thinking"] = False
        return extra

    def _get_reasoning_effort(self) -> Optional[str]:
        """返回 reasoning_effort 参数值。
        Google Gemini 已通过 thinking_config 控制思考，不再需要此参数。"""
        return None

    def _build_messages(self):
        """构建消息列表（带轮数限制）"""
        # 过滤非 system 消息
        history = [m for m in self.messages if m.get("role") != "system"]

        # 限制轮数
        max_msgs = self.MAX_ROUNDS * 2
        if len(history) > max_msgs:
            history = history[-max_msgs:]

        # 移除孤立的 tool 消息
        while history and history[0].get("role") == "tool":
            history.pop(0)

        # 构建名字前缀（根据语言选择）
        name_parts = []
        agent_name = self.role_config.get("agent_name", "").strip()
        user_nickname = self.role_config.get("user_nickname", "").strip()
        if self.lang == "en":
            if agent_name:
                name_parts.append(f"Your name is {agent_name}. ")
            if user_nickname:
                name_parts.append(f"You address the user as {user_nickname}. ")
        else:
            if agent_name:
                name_parts.append(f"你的名字叫{agent_name}。")
            if user_nickname:
                name_parts.append(f"你称呼用户为{user_nickname}。")
        name_prefix = "".join(name_parts)

        # 构建长期记忆片段
        memory_section = ""
        if self.memory_enabled and self.memory_content.strip():
            memory_label = "[Long-term Memory - What you know about the user]" if self.lang == "en" else "[长期记忆 - 你对用户的了解]"
            memory_section = f"\n\n{memory_label}\n{self.memory_content.strip()}\n"

        full_prompt = f"{name_prefix}{self.system_prompt}{memory_section} {self._tts_constraint}"
        return [{"role": "system", "content": full_prompt}] + history

    def _strip_thinking_tags(self, text: str) -> str:
        """去除豆包等模型的 thinking 标签包裹的内容"""
        import re
        # 豆包：<｜begin▁of▁thinking｜>...<｜end▁of▁thinking｜>
        # 其他常见：<thinking>...</thinking>
        text = re.sub(r'<｜begin▁of▁thinking｜>.*?<｜end▁of▁thinking｜>', '', text, flags=re.DOTALL)
        text = re.sub(r'<thinking>.*?</thinking>', '', text, flags=re.DOTALL)
        return text

    def _filter_thinking_content(self, text: str) -> tuple:
        """
        检查文本中是否包含未关闭的 thinking 标签，过滤掉其中的内容。
        返回 (过滤后的文本, 是否有未完成的标签)
        """
        # 检查并清理未完成的 thinking 标签内容（流式处理用）
        # 这里只做简单的内容过滤，主要依赖 API 层的 enable_thinking: False
        return text, False

    def chat_stream(self, user_input: str,
                    on_token: Optional[Callable[[str], None]] = None,
                    on_tool_call: Optional[Callable[[str, dict], None]] = None) -> str:
        """
        流式对话（支持多轮 Function Call）

        Args:
            user_input: 用户输入文本
            on_token: 每个 token 回调
            on_tool_call: 工具调用回调 (tool_name, args)

        Returns:
            完整回复文本
        """
        self.messages.append({"role": "user", "content": user_input})

        max_tool_rounds = 5
        full_content = ""

        for round_num in range(max_tool_rounds):
            kwargs = {
                "model": self.model,
                "messages": self._build_messages(),
                "stream": True,
            }

            # 根据提供商构建 extra_body（各提供商支持的参数不同）
            extra_body = self._build_extra_body()
            if extra_body:
                kwargs["extra_body"] = extra_body

            # Google Gemini: 用 reasoning_effort 控制思考输出
            re = self._get_reasoning_effort()
            if re:
                kwargs["reasoning_effort"] = re

            if self.enable_tools and self.tool_definitions:
                kwargs["tools"] = self.tool_definitions

            try:
                # 打印豆包模型的请求参数，确认配置是否正确
                if "volces" in self.config.get("base_url", ""):
                    print(f"[Doubao Debug] Request kwargs: model={kwargs.get('model')}, extra_body={kwargs.get('extra_body')}")
                
                response = self.client.chat.completions.create(**kwargs)
            except Exception as e:
                error_msg = f"LLM error: {e}"
                print(f"[LLM] {error_msg}")
                full_content = error_msg
                break

            # 收集流式响应
            round_content = ""
            tool_calls = []
            chunk_count = 0

            for chunk in response:
                chunk_count += 1
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta

                # 打印豆包模型的原始chunk信息，用于调试思考模式
                if "volces" in self.config.get("base_url", ""):
                    # 打印chunk的type和可用字段
                    chunk_type = getattr(delta, 'type', None) or getattr(chunk, 'type', None)
                    has_reasoning = hasattr(delta, 'reasoning_content') and delta.reasoning_content
                    print(f"[Doubao Debug] chunk#{chunk_count}: type={chunk_type}, has_content={bool(delta.content)}, has_reasoning={has_reasoning}")
                    if delta.content:
                        print(f"[Doubao Debug]   content='{delta.content[:50]}'")
                    if has_reasoning:
                        print(f"[Doubao Debug]   reasoning='{delta.reasoning_content[:50]}'")

                # 文本内容（跳过 reasoning/thinking 内容）
                if delta.content:
                    # 过滤掉 reasoning_content（某些模型会把思考内容放入 content）
                    token = delta.content
                    # 跳过 <｜end▁of▁thinking｜>... 标签包裹的思考内容
                    if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                        token = ""
                        print(f"[LLM] Skipping reasoning_content token")
                        continue
                    round_content += token
                    full_content += token
                    if on_token:
                        on_token(token)

                # 工具调用
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        # Google Gemini 可能返回 index=None，默认当作 0
                        idx = tc.index if tc.index is not None else 0
                        while len(tool_calls) <= idx:
                            tool_calls.append({"name": "", "arguments": "", "id": ""})
                        if tc.function and tc.function.name:
                            tool_calls[idx]["name"] = tc.function.name
                        if tc.function and tc.function.arguments:
                            tool_calls[idx]["arguments"] += tc.function.arguments
                        if tc.id:
                            tool_calls[idx]["id"] = tc.id
                        # Google Gemini: 回传 extra_content（含 thought_signature）
                        if hasattr(tc, 'extra_content') and tc.extra_content:
                            tool_calls[idx]["extra_content"] = tc.extra_content if isinstance(tc.extra_content, dict) else dict(tc.extra_content)

            # tool_call 轮次丢弃伴随的文本内容，避免输出混乱
            if tool_calls and round_content:
                print(f"[LLM] Discarding text in tool_call round: '{round_content[:80]}'")
                full_content = full_content[:-len(round_content)]  # 回退已累加的文本
                round_content = ""

            # 无工具调用，结束
            print(f"[LLM] Round {round_num+1}: {chunk_count} chunks, content='{round_content[:50]}', tool_calls={len(tool_calls)}")
            if not tool_calls:
                break

            # 处理工具调用
            # Google Gemini 可能不返回 tool_call id，需生成默认值
            for i, tc in enumerate(tool_calls):
                if not tc["id"]:
                    tc["id"] = f"call_{round_num}_{i}"
            assistant_msg = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": tc["arguments"]
                        },
                        **({"extra_content": tc["extra_content"]} if tc.get("extra_content") else {})
                    } for tc in tool_calls
                ]
            }
            self.messages.append(assistant_msg)

            for tc in tool_calls:
                if tc["name"] and self._tool_executor:
                    print(f"[LLM] Calling tool: {tc['name']}")
                    args = json.loads(tc["arguments"]) if tc["arguments"] else {}
                    if on_tool_call:
                        on_tool_call(tc["name"], args)
                    result = self._tool_executor(tc["name"], args)
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result
                    })
                    full_content += f"\n{result}"

        # 保存最终回复（空响应不存入历史，避免污染后续对话）
        clean_content = self._strip_thinking_tags(full_content).strip() if full_content else ""
        if clean_content:
            self.messages.append({"role": "assistant", "content": clean_content})
        else:
            # 移除对应的 user 消息，避免空回复破坏上下文
            if self.messages and self.messages[-1].get("role") == "user":
                self.messages.pop()
            print("[LLM] Warning: empty response, removed from history")
        return full_content

    VLM_MAX_PROMPT_LEN = 50  # VLM 提示词最大字数

    def chat_stream_with_vision(self, user_input: str, image_base64: str,
                                on_token: Optional[Callable[[str], None]] = None) -> str:
        """带图片的对话（VLM）"""
        # 限制提示词字数
        if len(user_input) > self.VLM_MAX_PROMPT_LEN:
            user_input = user_input[:self.VLM_MAX_PROMPT_LEN]
        content = [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}},
            {"type": "text", "text": user_input}
        ]
        self.messages.append({"role": "user", "content": content})

        kwargs = {
            "model": self.model,
            "messages": self._build_messages(),
            "stream": True,
        }
        extra_body = self._build_extra_body()
        if extra_body:
            kwargs["extra_body"] = extra_body

        # Google Gemini: 用 reasoning_effort 控制思考输出
        re = self._get_reasoning_effort()
        if re:
            kwargs["reasoning_effort"] = re

        full_content = ""
        try:
            response = self.client.chat.completions.create(**kwargs)
            for chunk in response:
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    # 跳过 reasoning_content
                    if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                        continue
                    if delta.content:
                        token = delta.content
                        full_content += token
                        if on_token:
                            on_token(token)
        except Exception as e:
            full_content = f"VLM error: {e}"
            print(f"[LLM] {full_content}")

        self.messages.append({"role": "assistant", "content": full_content})
        return full_content

    def vlm_describe(self, prompt: str, image_base64: str) -> str:
        """独立的图片理解调用，不影响主对话历史。
        用于 Function Call 场景：拍照后独立调 VLM，结果作为工具返回值回传给 LLM。
        """
        if len(prompt) > self.VLM_MAX_PROMPT_LEN:
            prompt = prompt[:self.VLM_MAX_PROMPT_LEN]

        # 根据语言设置 VLM system prompt，控制输出语言和简洁度
        if self.lang == "en":
            sys_content = "Describe the image briefly in 2-3 sentences. Use English."
        else:
            sys_content = "用中文简洁描述图片内容，2-3句话即可。"

        messages = [
            {"role": "system", "content": sys_content},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}},
                {"type": "text", "text": prompt}
            ]}
        ]
        kwargs = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "timeout": 30,
            "max_tokens": 200,
        }
        extra_body = self._build_extra_body()
        if extra_body:
            kwargs["extra_body"] = extra_body

        try:
            response = self.client.chat.completions.create(**kwargs)
            return (response.choices[0].message.content or "").strip()
        except Exception as e:
            print(f"[LLM] vlm_describe error: {e}")
            return f"VLM error: {e}"

    def generate_system_prompt(self, requirements: str, agent_name: str = "", user_nickname: str = "") -> dict:
        """使用 LLM 根据用户需求自动生成角色定义提示词，返回结构化结果"""
        try:
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": (META_PROMPT_EN if self.lang == "en" else META_PROMPT).replace("{user_requirements}", requirements).replace("{agent_name}", agent_name or "XGO").replace("{user_nickname}", user_nickname or "")}
            ]
            kwargs = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "timeout": 60,
                "max_tokens": 500
            }
            # 根据提供商构建 extra_body
            extra_body = self._build_extra_body()
            # 非 Google 提供商：生成提示词时强制禁用搜索
            if not self._is_google():
                extra_body["enable_search"] = False
            if extra_body:
                kwargs["extra_body"] = extra_body

            # Google Gemini: 用 reasoning_effort 控制思考输出
            re = self._get_reasoning_effort()
            if re:
                kwargs["reasoning_effort"] = re

            response = self.client.chat.completions.create(**kwargs)
            prompt = (response.choices[0].message.content or "").strip()
            if not prompt:
                return {"ok": False, "prompt": "", "error": "LLM returned empty response"}
            return {"ok": True, "prompt": prompt, "error": ""}
        except Exception as e:
            return {"ok": False, "prompt": "", "error": str(e)}

    def clear_history(self):
        """清空对话历史"""
        self.messages.clear()

    def update_memory(self, current_memory: str) -> str:
        """根据本次对话内容更新长期记忆，返回新的记忆文本"""
        # 提取本次对话中的 user/assistant 消息
        conversation_parts = []
        for m in self.messages:
            role = m.get("role", "")
            content = m.get("content", "")
            if role == "user" and isinstance(content, str):
                label_user = "User" if self.lang == "en" else "用户"
                conversation_parts.append(f"{label_user}: {content}")
            elif role == "assistant" and isinstance(content, str) and content.strip():
                label_assistant = "Assistant" if self.lang == "en" else "助手"
                conversation_parts.append(f"{label_assistant}: {content}")
        
        if not conversation_parts:
            return current_memory

        conversation_text = "\n".join(conversation_parts)
        # 截断过长的对话
        if len(conversation_text) > 3000:
            conversation_text = conversation_text[-3000:]

        memory_prompt = MEMORY_UPDATE_PROMPT_EN if self.lang == "en" else MEMORY_UPDATE_PROMPT
        prompt = memory_prompt.replace(
            "{current_memory}", current_memory or ("(No memory yet)" if self.lang == "en" else "（暂无记忆）")
        ).replace(
            "{conversation}", conversation_text
        )

        try:
            kwargs = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt}
                ],
                "stream": False,
                "timeout": 30,
                "max_tokens": 1000,
            }
            # 根据提供商构建 extra_body
            extra_body = self._build_extra_body()
            # 非 Google 提供商：记忆更新时强制禁用搜索
            if not self._is_google():
                extra_body["enable_search"] = False
            if extra_body:
                kwargs["extra_body"] = extra_body

            # Google Gemini: 用 reasoning_effort 控制思考输出
            re = self._get_reasoning_effort()
            if re:
                kwargs["reasoning_effort"] = re

            response = self.client.chat.completions.create(**kwargs)
            new_memory = (response.choices[0].message.content or "").strip()
            # 限制1000字
            if len(new_memory) > 1000:
                new_memory = new_memory[:1000]
            return new_memory if new_memory else current_memory
        except Exception as e:
            print(f"[LLM] Memory update error: {e}")
            return current_memory


class StreamSentenceSplitter:
    """流式句子分割器 - 将 LLM token 流分割为完整句子"""

    def __init__(self, on_sentence: Callable[[str], None]):
        self.on_sentence = on_sentence
        self.buffer = ""
        self.delimiters = set("。！？.!?~～\n")

    def feed(self, token: str):
        """喂入 token"""
        self.buffer += token
        while True:
            found = False
            for i, char in enumerate(self.buffer):
                if char in self.delimiters:
                    sentence = self.buffer[:i + 1].strip()
                    self.buffer = self.buffer[i + 1:]
                    if sentence:
                        self.on_sentence(sentence)
                    found = True
                    break
            if not found:
                break

    def flush(self):
        """刷出剩余内容"""
        if self.buffer.strip():
            self.on_sentence(self.buffer.strip())
            self.buffer = ""
