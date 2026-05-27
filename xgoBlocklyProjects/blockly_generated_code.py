from agents import xgo_chat

a = None

a = xgo_chat('趴下', model_type='xgo-mini', api_key="sk-a3b3f016971145b2b7dd561d4fead667", model_id='qwen-plus', system_prompt='你是一个功能全面的AI助手，具备代码执行、文件操作、联网搜索、XGO机器人控制等能力。请根据用户需求灵活使用这些工具。对于XGO机器人，你可以控制它的运动、姿态、查看电池等，还可以使用屏幕显示图片文字、语音识别和播放音频，支持播放HTTP音频和显示HTTP图片，同时支持AI拍照理解、语音合成和图片生成功能，实现完整的多模态交互体验。', long_term_memory=True, user_name='user', knowledge_base='', tools_enabled=True, mcp_websearch=False)
print('Hello World1111111111')
print(a)
