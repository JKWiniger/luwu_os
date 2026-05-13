# -*- coding: utf-8 -*-
"""H5 配置页面 HTML 模板"""

PAGE_HTML = """
<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>AI Chat Config</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { 
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; 
  background:#0a0a0f; 
  color:#e0e0e0; 
  padding:16px; 
  max-width:600px; 
  margin:0 auto; 
  background-image: radial-gradient(circle at 50% 0%, #150a20 0%, #0a0a0f 60%);
}
h1 { 
  text-align:center; 
  color:#39ff80; 
  font-size:22px; 
  margin:12px 0 20px; 
  text-shadow: 0 0 8px rgba(57,255,128,0.4);
  letter-spacing: 2px;
}
.tabs { 
  display:flex; 
  gap:6px; 
  margin-bottom:16px; 
  background: rgba(20,25,40,0.6);
  padding: 6px;
  border-radius: 12px;
  border: 1px solid rgba(57,255,128,0.15);
}
.tab { 
  flex:1; 
  padding:8px 4px; 
  text-align:center; 
  background:rgba(10,10,15,0.8); 
  border:1px solid rgba(57,255,128,0.1); 
  border-radius:8px; 
  cursor:pointer; 
  font-size:12px; 
  color:#667799; 
  transition:all .2s; 
  white-space:nowrap;
  overflow:hidden;
  text-overflow:ellipsis;
}
.tab.active { 
  background:rgba(57,255,128,0.08); 
  border-color:rgba(57,255,128,0.5); 
  color:#39ff80; 
  box-shadow: 0 0 6px rgba(57,255,128,0.2);
}
.panel { 
  display:none; 
  background:rgba(20,25,40,0.7); 
  border-radius:12px; 
  padding:16px; 
  border: 1px solid rgba(57,255,128,0.15);
}
.panel.active { display:block; }
label { 
  display:block; 
  font-size:13px; 
  color:#667799; 
  margin:10px 0 4px; 
}
label:first-child { margin-top:0; }
input,select,textarea { 
  width:100%; 
  padding:10px; 
  background:rgba(10,10,15,0.9); 
  border:1px solid rgba(57,255,128,0.15); 
  border-radius:8px; 
  color:#e0e0e0; 
  font-size:14px; 
  outline:none; 
  transition: all 0.2s;
}
input:focus,select:focus,textarea:focus { 
  border-color:rgba(57,255,128,0.5); 
  box-shadow: 0 0 6px rgba(57,255,128,0.2);
}
select { 
  appearance:none; 
  -webkit-appearance:none; 
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' fill='%2339ff80'%3E%3Cpath d='M6 8L1 3h10z'/%3E%3C/svg%3E"); 
  background-repeat:no-repeat; 
  background-position:right 10px center; 
}
textarea { resize:vertical; min-height:60px; }
.row { display:flex; gap:8px; }
.row > * { flex:1; }
.btn { 
  display:block; 
  width:100%; 
  padding:12px; 
  margin-top:16px; 
  border:2px solid rgba(57,255,128,0.6); 
  border-radius:10px; 
  font-size:16px; 
  font-weight:600; 
  cursor:pointer; 
  transition:all .2s; 
  background: rgba(57,255,128,0.08);
  color: #39ff80;
  text-shadow: 0 0 4px rgba(57,255,128,0.3);
}
.btn:hover {
  background: rgba(57,255,128,0.12);
  box-shadow: 0 0 10px rgba(57,255,128,0.3);
}
.btn-primary:active { transform:scale(0.98); opacity:0.9; }
.btn-test { 
  background:rgba(20,25,40,0.8); 
  color:#39ff80; 
  font-size:13px; 
  padding:8px; 
  margin-top:8px; 
  border-color: rgba(57,255,128,0.3);
}
.btn-test:active { background:#2a3560; }
.provider-link {
  display:inline-block;
  font-size:12px;
  color:#66aaff;
  text-decoration:none;
  margin:6px 0 10px 2px;
  transition:color .2s;
}
.provider-link:hover {
  color:#99ccff;
  text-decoration:underline;
}
.tip { 
  font-size:12px; 
  color:#556688; 
  margin-top:6px; 
  line-height:1.5; 
}
.tip.warn { 
  color:#cc8833; 
  background:rgba(40,35,25,0.8); 
  padding:8px; 
  border-radius:6px; 
  margin-top:10px; 
  border: 1px solid rgba(204,136,51,0.3);
}
.status { 
  text-align:center; 
  padding:8px; 
  margin-top:10px; 
  border-radius:6px; 
  font-size:13px; 
  display:none; 
  border: 1px solid;
}
.status.ok { 
  display:block; 
  background:rgba(20,45,25,0.8); 
  color:#33cc66; 
  border-color: rgba(51,204,102,0.3);
}
.status.err { 
  display:block; 
  background:rgba(45,20,20,0.8); 
  color:#cc5533; 
  border-color: rgba(204,85,51,0.3);
}
.tag-input { 
  display:flex; 
  flex-wrap:wrap; 
  gap:6px; 
  padding:8px; 
  background:rgba(10,10,15,0.9); 
  border:1px solid rgba(57,255,128,0.15); 
  border-radius:8px; 
  min-height:42px; 
}
.tag { 
  display:inline-flex; 
  align-items:center; 
  background:rgba(57,255,128,0.08); 
  color:#39ff80; 
  padding:4px 10px; 
  border-radius:16px; 
  font-size:13px; 
  border: 1px solid rgba(57,255,128,0.25);
}
.tag .x { 
  margin-left:6px; 
  cursor:pointer; 
  color:#667799; 
  font-weight:bold; 
}
.tag-add { display:flex; gap:6px; margin-top:6px; }
.tag-add input { flex:1; }
.tag-add button { 
  padding:8px 16px; 
  background:rgba(57,255,128,0.08); 
  color:#39ff80; 
  border:1px solid rgba(57,255,128,0.25); 
  border-radius:8px; 
  cursor:pointer; 
  white-space:nowrap; 
}
.switch { 
  display:flex; 
  align-items:center; 
  gap:8px; 
  margin:8px 0; 
}
.switch input[type=checkbox] { 
  width:40px; 
  height:22px; 
  appearance:none; 
  -webkit-appearance:none; 
  background:rgba(30,35,50,0.8); 
  border-radius:11px; 
  position:relative; 
  cursor:pointer; 
  border: 1px solid rgba(57,255,128,0.15);
}
.switch input[type=checkbox]::after { 
  content:''; 
  position:absolute; 
  top:2px; 
  left:2px; 
  width:18px; 
  height:18px; 
  background:#556688; 
  border-radius:50%; 
  transition:.2s; 
}
.switch input[type=checkbox]:checked { 
  background:rgba(57,255,128,0.15); 
  border-color: rgba(57,255,128,0.5);
}
.switch input[type=checkbox]:checked::after { 
  left:20px; 
  background:#39ff80; 
  box-shadow: 0 0 4px rgba(57,255,128,0.4);
}
.switch span { font-size:13px; color:#667799; }
.mbti-grid { 
  display:grid; 
  grid-template-columns:repeat(4,1fr); 
  gap:8px; 
  margin:8px 0; 
}
.mbti-card { 
  text-align:center; 
  padding:10px 4px; 
  border-radius:10px; 
  border:2px solid rgba(57,255,128,0.1); 
  cursor:pointer; 
  transition:all .2s; 
}
.mbti-card:active { transform:scale(0.95); }
.mbti-card.selected { 
  border-color:rgba(57,255,128,0.6); 
  transform:scale(1.05); 
  box-shadow:0 0 8px rgba(57,255,128,0.3); 
}
.mbti-card .code { 
  font-size:15px; 
  font-weight:700; 
  color:#e0e0e0; 
}
.mbti-card .name { 
  font-size:10px; 
  color:#8899aa; 
  margin-top:2px; 
}
.mbti-purple { background:rgba(35,25,60,0.8); }
.mbti-green { background:rgba(20,50,35,0.8); }
.mbti-blue { background:rgba(20,35,60,0.8); }
.mbti-yellow { background:rgba(50,45,25,0.8); }
.section-title { 
  font-size:14px; 
  font-weight:600; 
  color:#39ff80; 
  margin:14px 0 6px; 
  text-shadow: 0 0 3px rgba(57,255,128,0.2);
}
.section-title:first-child { margin-top:0; }
.collapse-header { 
  display:flex; 
  align-items:center; 
  justify-content:space-between; 
  background:rgba(10,10,15,0.9); 
  padding:10px 12px; 
  border-radius:8px; 
  cursor:pointer; 
  margin:8px 0 4px; 
  border:1px solid rgba(57,255,128,0.15); 
}
.collapse-header span { 
  font-size:13px; 
  color:#667799; 
}
.collapse-header .arrow { 
  transition:transform .2s; 
  color:#556688; 
}
.collapse-header.open .arrow { transform:rotate(90deg); }
.collapse-body { display:none; padding:4px 0; }
.collapse-body.open { display:block; }
.quiz-q { 
  font-size:13px; 
  color:#aabbcc; 
  margin:10px 0 6px; 
}
.quiz-opts { display:flex; gap:6px; }
.quiz-opt { 
  flex:1; 
  padding:8px 6px; 
  background:rgba(10,10,15,0.9); 
  border:1px solid rgba(57,255,128,0.15); 
  border-radius:8px; 
  cursor:pointer; 
  font-size:12px; 
  color:#667799; 
  text-align:center; 
  transition:all .2s; 
  line-height:1.4; 
}
.quiz-opt.selected { 
  background:rgba(57,255,128,0.08); 
  border-color:rgba(57,255,128,0.5); 
  color:#39ff80; 
}
.btn-generate { 
  display:flex; 
  align-items:center; 
  justify-content:center; 
  gap:8px; 
}
.btn-generate .spinner { 
  display:none; 
  width:16px; 
  height:16px; 
  border:2px solid rgba(57,255,128,0.2); 
  border-top-color:#39ff80; 
  border-radius:50%; 
  animation:spin .6s linear infinite; 
}
.btn-generate.loading .spinner { display:inline-block; }
@keyframes spin { to { transform:rotate(360deg); } }
.prompt-hint { 
  font-size:12px; 
  color:#445566; 
  margin-top:2px; 
  font-style:italic; 
}
</style>
</head>
<body>
<h1 id="page_title" style="display:none;"></h1>
<div class="tabs">
  <div class="tab active" id="tab_asr" onclick="showTab('asr')">语音识别</div>
  <div class="tab" id="tab_llm" onclick="showTab('llm')">AI 大脑</div>
  <div class="tab" id="tab_tts" onclick="showTab('tts')">语音合成</div>
  <div class="tab" id="tab_agent" onclick="showTab('agent')">角色</div>
</div>

<!-- Agent -->
<div id="agent" class="panel">
  <div class="section-title" id="sec_name">称呼设置</div>
  <div class="row">
    <div><label id="lbl_agent_name">智能体名字</label><input id="agent_name" placeholder="如：小陆、XGO"></div>
    <div><label id="lbl_user_nickname">叫我什么</label><input id="user_nickname" placeholder="如：主人、小朋友"></div>
  </div>

  <div class="section-title" id="sec_personality">选择您的性格类型</div>
  <div class="mbti-grid" id="mbti_grid"></div>

  <div class="collapse-header" id="quiz_header" onclick="toggleQuiz()">
    <span id="lbl_quick_test">快速测试</span><span class="arrow">▶</span>
  </div>
  <div class="collapse-body" id="quiz_body">
    <div class="quiz-q" id="quiz_q1">1. 和主人互动时，你更像...</div>
    <div class="quiz-opts">
      <div class="quiz-opt" id="quiz_q1_a" onclick="pickQuiz(0,0,this)">A: 热情话痨，主动找话题</div>
      <div class="quiz-opt" id="quiz_q1_b" onclick="pickQuiz(0,1,this)">B: 安静陪伴，等主人开口</div>
    </div>
    <div class="quiz-q" id="quiz_q2">2. 回答问题时，你更倾向...</div>
    <div class="quiz-opts">
      <div class="quiz-opt" id="quiz_q2_a" onclick="pickQuiz(1,0,this)">A: 讲故事、举例子、用比喻</div>
      <div class="quiz-opt" id="quiz_q2_b" onclick="pickQuiz(1,1,this)">B: 给知识、讲道理、列要点</div>
    </div>
    <div class="quiz-q" id="quiz_q3">3. 主人遇到困难时，你会...</div>
    <div class="quiz-opts">
      <div class="quiz-opt" id="quiz_q3_a" onclick="pickQuiz(2,0,this)">A: 温暖鼓励，给情感支持</div>
      <div class="quiz-opt" id="quiz_q3_b" onclick="pickQuiz(2,1,this)">B: 冷静分析，给解决方案</div>
    </div>
    <div class="quiz-q" id="quiz_q4">4. 你的说话风格是...</div>
    <div class="quiz-opts">
      <div class="quiz-opt" id="quiz_q4_a" onclick="pickQuiz(3,0,this)">A: 活泼跳跃，爱开玩笑</div>
      <div class="quiz-opt" id="quiz_q4_b" onclick="pickQuiz(3,1,this)">B: 沉稳有序，条理清晰</div>
    </div>
  </div>

  <div class="section-title" id="sec_requirements">需求描述</div>
  <textarea id="agent_requirements" rows="3" placeholder="描述你想要的机器人性格，如：一个爱讲冷笑话的机器人..."></textarea>

  <div class="section-title" id="sec_generate">生成与编辑</div>
  <button class="btn btn-primary btn-generate" id="btn_gen" onclick="generatePrompt()" style="margin-top:8px">
    <span class="spinner"></span><span class="btn-text" id="btn_gen_text">✨ 自动生成提示词</span>
  </button>
  <label style="margin-top:12px" id="lbl_current_prompt">当前提示词</label>
  <textarea id="agent_prompt" rows="7" placeholder="生成或手动编辑系统提示词..."></textarea>
  <p class="prompt-hint" id="hint_prompt">此提示词将作为 LLM 的 System Prompt</p>

  <div class="section-title" id="sec_memory">长期记忆</div>
  <div class="switch"><input type="checkbox" id="memory_enabled"><span id="lbl_memory_enable">启用长期记忆</span></div>
  <p class="tip" id="tip_memory">开启后，每次对话结束时会自动总结并记住用户偏好、习惯等信息，下次对话时会自动带入</p>
  <textarea id="memory_content" rows="5" placeholder="记忆内容会在对话后自动更新..." maxlength="1000"></textarea>
  <p class="tip" id="memory_char_count">0 / 1000 字</p>
  <button class="btn btn-test" id="btn_clear_memory" onclick="clearMemory()" style="background:#4a2020;color:#ff6644">清除记忆</button>
  <div id="memory_status" class="status"></div>
</div>

<!-- ASR -->
<div id="asr" class="panel active">
  <label id="lbl_asr_provider">Provider</label>
  <select id="asr_provider" onchange="toggleASR()">
    <option value="aliyun">阿里云 千问 Aliyun Qwen (China)</option>
    <option value="deepgram">Deepgram (Global, Real-time VAD)</option>
  </select>
  <a class="provider-link" id="asr_provider_link" href="https://bailian.console.aliyun.com/" target="_blank" rel="noopener">🔗 Visit Official Website →</a>
  <div id="asr_aliyun">
    <label id="lbl_asr_api_key">API Key</label>
    <input id="asr_aliyun_key" type="password" placeholder="sk-xxx">
    <div class="row">
      <div><label id="lbl_asr_model">Model</label><input id="asr_aliyun_model" value="qwen3-asr-flash-realtime"></div>
      <div><label id="lbl_asr_lang">Language</label><select id="asr_aliyun_lang"><option value="zh">中文</option><option value="en">English</option></select></div>
    </div>
    <div class="row">
      <div><label id="lbl_asr_vad">VAD Threshold</label><input id="asr_aliyun_vad" type="number" step="0.1" min="0" max="1" value="0.5"></div>
      <div><label id="lbl_asr_silence">Silence (ms)</label><input id="asr_aliyun_silence" type="number" value="800"></div>
    </div>
  </div>
  <div id="asr_deepgram" style="display:none">
    <label id="lbl_asr_dg_key">API Key</label>
    <input id="asr_dg_key" type="password" placeholder="Your Deepgram API Key">
    <div class="row">
      <div><label id="lbl_asr_dg_model">Model</label><select id="asr_dg_model"><option value="nova-3">Nova-3 (Recommended)</option><option value="nova-2">Nova-2</option><option value="enhanced">Enhanced</option><option value="base">Base</option></select></div>
      <div><label id="lbl_asr_dg_lang">Language</label><select id="asr_dg_lang"><option value="zh">中文</option><option value="zh-CN">中文（简体）</option><option value="en">English</option><option value="ja">日本語</option><option value="ko">한국어</option></select></div>
    </div>
    <div class="row">
      <div><label id="lbl_asr_dg_vad">VAD Silence (ms)</label><input id="asr_dg_vad" type="number" min="200" max="5000" value="1000"></div>
    </div>
    <p class="tip" id="tip_asr_dg">Deepgram ASR: Real-time WebSocket streaming with built-in VAD. Get API key at deepgram.com</p>
  </div>
  <button class="btn btn-test" id="btn_test_asr" onclick="testASR()">Test ASR Connection</button>
  <div id="asr_status" class="status"></div>
</div>

<!-- LLM -->
<div id="llm" class="panel">
  <label id="lbl_llm_provider">Provider Preset</label>
  <select id="llm_provider" onchange="selectLLMPreset()">
    <option value="aliyun">阿里云通义 / Alibaba Qwen</option>
    <option value="openai">OpenAI</option>
    <option value="google">Google Gemini</option>
    <option value="doubao">字节豆包 / Doubao</option>
    <option value="custom">Custom / 自定义</option>
  </select>
  <a class="provider-link" id="llm_provider_link" href="https://bailian.console.aliyun.com/" target="_blank" rel="noopener">🔗 Visit Official Website →</a>
  <label id="lbl_llm_api_key">API Key</label>
  <input id="llm_key" type="password" placeholder="sk-xxx">
  <label id="lbl_llm_base_url">Base URL (OpenAI Compatible)</label>
  <input id="llm_url" placeholder="https://api.openai.com/v1">
  <label id="lbl_llm_model">Model</label>
  <div class="row">
    <select id="llm_model_select" onchange="document.getElementById('llm_model').value=this.value" style="flex:1.2"></select>
    <input id="llm_model" placeholder="model-id" style="flex:1">
  </div>
  <p class="tip" style="margin-top:10px" id="tip_llm_prompt">💡 系统提示词请在「角色」标签页配置</p>
  <div class="switch"><input type="checkbox" id="llm_tools" checked><span id="lbl_llm_tools">Enable Function Call (Robot Control)</span></div>
  <div class="switch"><input type="checkbox" id="llm_search" checked><span id="lbl_llm_search">Enable Web Search</span></div>
  <p class="tip warn" id="tip_llm_vlm">📷 VLM (Vision): To enable photo recognition, select a vision-capable model above (e.g. qwen3.6-plus, gpt-5.5, gemini-3.1-pro-preview). No separate VLM config needed.</p>
  <button class="btn btn-test" id="btn_test_llm" onclick="testLLM()">Test LLM Connection</button>
  <div id="llm_status" class="status"></div>
</div>

<!-- TTS -->
<div id="tts" class="panel">
  <label id="lbl_tts_provider">Provider</label>
  <select id="tts_provider" onchange="toggleTTS()">
    <option value="aliyun">阿里云 千问 Aliyun Qwen (China)</option>
    <option value="deepgram">Deepgram (Global, Real-time Streaming)</option>
  </select>
  <a class="provider-link" id="tts_provider_link" href="https://bailian.console.aliyun.com/" target="_blank" rel="noopener">🔗 Visit Official Website →</a>
  <div id="tts_aliyun">
    <label id="lbl_tts_aliyun_key">API Key</label>
    <input id="tts_aliyun_key" type="password" placeholder="sk-xxx (same as ASR if Aliyun)">
    <label id="lbl_tts_voice">Voice</label>
    <select id="tts_aliyun_voice">
      <option value="Cherry">Cherry (Female)</option>
      <option value="Serena">Serena (Female)</option>
      <option value="Ethan">Ethan (Male)</option>
      <option value="Chelsie">Chelsie (Female)</option>
    </select>
  </div>
  <div id="tts_deepgram" style="display:none">
    <label id="lbl_tts_dg_key">API Key</label>
    <input id="tts_dg_key" type="password" placeholder="Your Deepgram API Key">
    <div class="row">
      <div><label id="lbl_tts_dg_model">Model / Voice</label><select id="tts_dg_model">
        <option value="aura-2-thalia-en">Aura-2 Thalia (Female)</option>
        <option value="aura-2-luna-en">Aura-2 Luna (Female)</option>
        <option value="aura-2-stella-en">Aura-2 Stella (Female)</option>
        <option value="aura-2-athena-en">Aura-2 Athena (Female)</option>
        <option value="aura-2-hera-en">Aura-2 Hera (Female)</option>
        <option value="aura-2-orion-en">Aura-2 Orion (Male)</option>
        <option value="aura-2-arcas-en">Aura-2 Arcas (Male)</option>
        <option value="aura-2-perseus-en">Aura-2 Perseus (Male)</option>
        <option value="aura-2-angus-en">Aura-2 Angus (Male)</option>
        <option value="aura-2-orpheus-en">Aura-2 Orpheus (Male)</option>
        <option value="aura-2-helios-en">Aura-2 Helios (Male)</option>
        <option value="aura-2-zeus-en">Aura-2 Zeus (Male)</option>
      </select></div>
      <div><label id="lbl_tts_dg_rate">Sample Rate</label><select id="tts_dg_rate"><option value="48000">48000 Hz</option><option value="24000">24000 Hz</option><option value="16000">16000 Hz</option></select></div>
    </div>
    <p class="tip" id="tip_tts_dg">Deepgram TTS: Real-time WebSocket streaming synthesis. Get API key at deepgram.com</p>
  </div>
  <button class="btn btn-test" id="btn_test_tts" onclick="testTTS()">Test TTS</button>
  <div id="tts_status" class="status"></div>
</div>

<button class="btn btn-primary" id="btn_save" onclick="saveConfig()">💾 Save Configuration</button>
<div id="save_status" class="status"></div>

<script>
const LANGS = %%LANGS%%;
const PRESETS = %%PRESETS%%;
let config = %%CONFIG%%;

const TAB_IDS = ['asr','llm','tts','agent'];
function showTab(id) {
  document.querySelectorAll('.tab').forEach((t,i)=>t.classList.toggle('active', TAB_IDS[i]===id));
  document.querySelectorAll('.panel').forEach(p=>p.classList.toggle('active', p.id===id));
}

// === MBTI Data ===
const MBTI_LIST = [
  {code:'INTJ',key:'MBTI_INTJ',cls:'mbti-purple'},{code:'INTP',key:'MBTI_INTP',cls:'mbti-purple'},{code:'ENTJ',key:'MBTI_ENTJ',cls:'mbti-purple'},{code:'ENTP',key:'MBTI_ENTP',cls:'mbti-purple'},
  {code:'INFJ',key:'MBTI_INFJ',cls:'mbti-green'},{code:'INFP',key:'MBTI_INFP',cls:'mbti-green'},{code:'ENFJ',key:'MBTI_ENFJ',cls:'mbti-green'},{code:'ENFP',key:'MBTI_ENFP',cls:'mbti-green'},
  {code:'ISTJ',key:'MBTI_ISTJ',cls:'mbti-blue'},{code:'ISFJ',key:'MBTI_ISFJ',cls:'mbti-blue'},{code:'ESTJ',key:'MBTI_ESTJ',cls:'mbti-blue'},{code:'ESFJ',key:'MBTI_ESFJ',cls:'mbti-blue'},
  {code:'ISTP',key:'MBTI_ISTP',cls:'mbti-yellow'},{code:'ISFP',key:'MBTI_ISFP',cls:'mbti-yellow'},{code:'ESTP',key:'MBTI_ESTP',cls:'mbti-yellow'},{code:'ESFP',key:'MBTI_ESFP',cls:'mbti-yellow'}
];
const MBTI_DESC = {};
MBTI_LIST.forEach(m => MBTI_DESC[m.code] = (LANGS.MBTI_DESC_TEMPLATE || 'My MBTI is {code} ({name}).').replace('{code}',m.code).replace('{name}', LANGS[m.key] || m.code));
let selectedMBTI = null;
let quizAnswers = [-1,-1,-1,-1];

// Provider official website URLs
const PROVIDER_URLS = {
  'asr': { 'aliyun': 'https://bailian.console.aliyun.com/', 'deepgram': 'https://console.deepgram.com/' },
  'llm': { 'aliyun': 'https://bailian.console.aliyun.com/', 'openai': 'https://platform.openai.com/', 'google': 'https://aistudio.google.com/', 'doubao': 'https://console.volcengine.com/ark/', 'custom': '#' },
  'tts': { 'aliyun': 'https://bailian.console.aliyun.com/', 'deepgram': 'https://console.deepgram.com/' }
};
function updateProviderLink(type, provider) {
  const link = document.getElementById(type + '_provider_link');
  if (link) {
    const url = (PROVIDER_URLS[type] || {})[provider] || '#';
    if (url === '#') {
      link.style.display = 'none';
    } else {
      link.style.display = '';
      link.href = url;
    }
  }
}

function renderMBTI() {
  const g = document.getElementById('mbti_grid');
  g.innerHTML = MBTI_LIST.map(m => `<div class="mbti-card ${m.cls} ${selectedMBTI===m.code?'selected':''}" onclick="pickMBTI('${m.code}')"><div class="code">${m.code}</div><div class="name">${LANGS[m.key] || m.code}</div></div>`).join('');
}
function pickMBTI(code) {
  selectedMBTI = selectedMBTI===code ? null : code;
  renderMBTI();
  fillRequirements();
}
function fillRequirements() {
  const ta = document.getElementById('agent_requirements');
  if (selectedMBTI) {
    ta.value = MBTI_DESC[selectedMBTI];
  }
}
function toggleQuiz() {
  const h = document.getElementById('quiz_header');
  const b = document.getElementById('quiz_body');
  h.classList.toggle('open'); b.classList.toggle('open');
}
function pickQuiz(q, val, el) {
  quizAnswers[q] = val;
  el.parentElement.querySelectorAll('.quiz-opt').forEach((o,i) => o.classList.toggle('selected', i===val));
  if (quizAnswers.every(a=>a>=0)) {
    const dims = ['EI','NS','FT','PJ'];
    let code = '';
    quizAnswers.forEach((a,i) => code += dims[i][a]);
    selectedMBTI = code;
    renderMBTI();
    fillRequirements();
  }
}
async function generatePrompt() {
  const btn = document.getElementById('btn_gen');
  const txt = btn.querySelector('.btn-text');
  btn.classList.add('loading'); txt.textContent = LANGS.GENERATING || 'Generating...';
  const reqs = document.getElementById('agent_requirements').value;
  const agentName = document.getElementById('agent_name').value;
  const userNickname = document.getElementById('user_nickname').value;
  try {
    const r = await fetch('/api/generate-prompt', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({requirements:reqs, agent_name:agentName, user_nickname:userNickname})});
    const d = await r.json();
    if (d.success && d.prompt) { document.getElementById('agent_prompt').value = d.prompt; }
    else { alert(d.error || (LANGS.GENERATE_FAIL || 'Generation failed')); }
  } catch(e) { alert((LANGS.GENERATE_NET_ERROR || 'Network error')+': '+e.message); }
  btn.classList.remove('loading'); txt.textContent = LANGS.GENERATE_PROMPT || '✨ Auto Generate Prompt';
}
function toggleASR() {
  const v = document.getElementById('asr_provider').value;
  document.getElementById('asr_aliyun').style.display = v==='aliyun'?'block':'none';
  document.getElementById('asr_deepgram').style.display = v==='deepgram'?'block':'none';
  updateProviderLink('asr', v);
  // Auto-fill Deepgram ASR key from TTS if empty
  if (v === 'deepgram' && !document.getElementById('asr_dg_key').value) {
    const ttsDgKey = document.getElementById('tts_dg_key').value;
    if (ttsDgKey) document.getElementById('asr_dg_key').value = ttsDgKey;
  }
}
function toggleTTS() {
  const v = document.getElementById('tts_provider').value;
  document.getElementById('tts_aliyun').style.display = v==='aliyun'?'block':'none';
  document.getElementById('tts_deepgram').style.display = v==='deepgram'?'block':'none';
  updateProviderLink('tts', v);
  // Auto-fill Deepgram TTS key from ASR if empty
  if (v === 'deepgram' && !document.getElementById('tts_dg_key').value) {
    const asrDgKey = document.getElementById('asr_dg_key').value;
    if (asrDgKey) document.getElementById('tts_dg_key').value = asrDgKey;
  }
}
function selectLLMPreset() {
  // Save current key & URL for old provider before switching (skip on first load when old==new)
  const oldProvider = document.getElementById('llm_provider').dataset.prevValue || '';
  const v = document.getElementById('llm_provider').value;
  updateProviderLink('llm', v);
  if (oldProvider && oldProvider !== v) {
    const currentKey = document.getElementById('llm_key').value;
    const savedKeys = JSON.parse(localStorage.getItem('llm_provider_keys') || '{}');
    if (currentKey) savedKeys[oldProvider] = currentKey;
    else delete savedKeys[oldProvider];
    localStorage.setItem('llm_provider_keys', JSON.stringify(savedKeys));
    // Save current URL for old provider
    const currentUrl = document.getElementById('llm_url').value;
    const savedUrls = JSON.parse(localStorage.getItem('llm_provider_urls') || '{}');
    if (currentUrl) savedUrls[oldProvider] = currentUrl;
    else delete savedUrls[oldProvider];
    localStorage.setItem('llm_provider_urls', JSON.stringify(savedUrls));
  }
  document.getElementById('llm_provider').dataset.prevValue = v;
  
  const sel = document.getElementById('llm_model_select');
  sel.innerHTML = '';
  const presetUrl = (v !== 'custom' && PRESETS[v]) ? PRESETS[v].base_url : '';
  if (v !== 'custom' && PRESETS[v]) {
    const p = PRESETS[v];
    p.models.forEach(m => { const o=document.createElement('option'); o.value=m; o.text=m; sel.appendChild(o); });
    document.getElementById('llm_model').value = p.models[0];
  } else {
    document.getElementById('llm_model').value = '';
  }
  
  // Restore URL: localStorage > config provider_urls > preset default
  const savedUrls = JSON.parse(localStorage.getItem('llm_provider_urls') || '{}');
  const configUrls = config.llm?.provider_urls || {};
  document.getElementById('llm_url').value = savedUrls[v] || configUrls[v] || presetUrl;
  
  // Auto-fill key for new provider: localStorage first, then config provider_keys
  const savedKeys = JSON.parse(localStorage.getItem('llm_provider_keys') || '{}');
  const configKeys = config.llm?.provider_keys || {};
  const restoredKey = savedKeys[v] || configKeys[v] || '';
  document.getElementById('llm_key').value = restoredKey;
}
function gatherConfig() {
  const asrP = document.getElementById('asr_provider').value;
  const ttsP = document.getElementById('tts_provider').value;
  return {
    role: {
      agent_name: document.getElementById('agent_name').value,
      user_nickname: document.getElementById('user_nickname').value,
      mbti: selectedMBTI || '',
      quiz_answers: quizAnswers,
      requirements: document.getElementById('agent_requirements').value
    },
    memory: {
      enabled: document.getElementById('memory_enabled').checked,
      content: document.getElementById('memory_content').value
    },
    asr: {
      provider: asrP,
      aliyun: { api_key:document.getElementById('asr_aliyun_key').value, model:document.getElementById('asr_aliyun_model').value, language:document.getElementById('asr_aliyun_lang').value, vad_threshold:parseFloat(document.getElementById('asr_aliyun_vad').value), silence_duration_ms:parseInt(document.getElementById('asr_aliyun_silence').value) },
      deepgram: { api_key:document.getElementById('asr_dg_key').value, model:document.getElementById('asr_dg_model').value, language:document.getElementById('asr_dg_lang').value, vad_silence_ms:parseInt(document.getElementById('asr_dg_vad').value) }
    },
    llm: {
      provider: document.getElementById('llm_provider').value,
      presets: PRESETS,
      api_key: document.getElementById('llm_key').value,
      provider_keys: buildProviderKeys(),
      provider_urls: buildProviderUrls(),
      base_url: document.getElementById('llm_url').value,
      model: document.getElementById('llm_model').value,
      system_prompt: document.getElementById('agent_prompt').value,
      enable_tools: document.getElementById('llm_tools').checked,
      enable_search: document.getElementById('llm_search').checked
    },
    tts: {
      provider: ttsP,
      aliyun: { api_key:document.getElementById('tts_aliyun_key').value, model:'qwen3-tts-flash-realtime', voice:document.getElementById('tts_aliyun_voice').value, voices:['Cherry','Serena','Ethan','Chelsie'] },
      deepgram: { api_key:document.getElementById('tts_dg_key').value, model:document.getElementById('tts_dg_model').value, sample_rate:parseInt(document.getElementById('tts_dg_rate').value), gain:2.0 }
    }
  };
}
function buildProviderKeys() {
  const keys = JSON.parse(localStorage.getItem('llm_provider_keys') || '{}');
  const currentProvider = document.getElementById('llm_provider').value;
  const currentKey = document.getElementById('llm_key').value;
  if (currentKey) keys[currentProvider] = currentKey;
  for (const p of ['aliyun','openai','google','doubao','custom']) {
    if (!(p in keys)) keys[p] = '';
  }
  return keys;
}
function buildProviderUrls() {
  const urls = JSON.parse(localStorage.getItem('llm_provider_urls') || '{}');
  const currentProvider = document.getElementById('llm_provider').value;
  const currentUrl = document.getElementById('llm_url').value;
  if (currentUrl) urls[currentProvider] = currentUrl;
  return urls;
}
async function saveConfig() {
  const st = document.getElementById('save_status');
  try {
    const r = await fetch('/api/config', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(gatherConfig()) });
    const d = await r.json();
    st.className = 'status ' + (d.ok?'ok':'err');
    st.textContent = d.msg || (d.ok ? (LANGS.SAVE_SUCCESS || 'Saved!') : (LANGS.SAVE_ERROR || 'Error'));
  } catch(e) { st.className='status err'; st.textContent=(LANGS.NETWORK_ERROR || 'Network error')+': '+e.message; }
}
async function testASR() {
  const st = document.getElementById('asr_status');
  st.className='status ok'; st.textContent=LANGS.TESTING || 'Testing...';
  try {
    const r = await fetch('/api/test/asr', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(gatherConfig().asr) });
    const d = await r.json();
    st.className = 'status '+(d.ok?'ok':'err'); st.textContent=d.msg;
  } catch(e) { st.className='status err'; st.textContent=e.message; }
}
async function testLLM() {
  const st = document.getElementById('llm_status');
  const btn = event.target;
  st.className='status ok'; st.textContent = LANGS.LLM_TESTING || 'Testing... (may take 10-30s for Google Gemini)';
  btn.disabled = true;
  btn.textContent = LANGS.TESTING || 'Testing...';
  try {
    // 添加前端超时控制
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 40000); // 40秒超时
    
    const r = await fetch('/api/test/llm', { 
      method:'POST', 
      headers:{'Content-Type':'application/json'}, 
      body:JSON.stringify(gatherConfig().llm),
      signal: controller.signal
    });
    clearTimeout(timeoutId);
    
    const text = await r.text();
    if (!text) {
      st.className='status err'; st.textContent = LANGS.LLM_EMPTY_RESPONSE || 'Empty response from server. Check server logs.';
      return;
    }
    let d;
    try { d = JSON.parse(text); } catch(pe) {
      st.className='status err'; st.textContent = (LANGS.LLM_INVALID_RESPONSE || 'Invalid response') + ': ' + text.substring(0, 100);
      return;
    }
    st.className = 'status '+(d.ok?'ok':'err'); 
    st.textContent = d.msg;
  } catch(e) { 
    st.className='status err'; 
    if (e.name === 'AbortError') {
      st.textContent = LANGS.LLM_REQUEST_TIMEOUT || 'Request timeout. Check network or API Key.';
    } else {
      st.textContent = e.message || (LANGS.GENERATE_FAIL || 'Test failed'); 
    }
  } finally {
    btn.disabled = false;
    btn.textContent = LANGS.LLM_TEST_BTN || 'Test LLM Connection';
  }
}
async function testTTS() {
  const st = document.getElementById('tts_status');
  st.className='status ok'; st.textContent=LANGS.TESTING || 'Testing...';
  try {
    const r = await fetch('/api/test/tts', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(gatherConfig().tts) });
    const d = await r.json();
    st.className = 'status '+(d.ok?'ok':'err'); st.textContent=d.msg;
  } catch(e) { st.className='status err'; st.textContent=e.message; }
}

function applyI18n() {
  // Helper to set text by id
  const set = (id, key, fb) => { const el = document.getElementById(id); if (el && LANGS[key]) el.textContent = LANGS[key]; else if (el && fb) el.textContent = fb; };
  const setHtml = (id, key, fb) => { const el = document.getElementById(id); if (el && LANGS[key]) el.innerHTML = LANGS[key]; else if (el && fb) el.innerHTML = fb; };
  const setPh = (id, key, fb) => { const el = document.getElementById(id); if (el && LANGS[key]) el.placeholder = LANGS[key]; else if (el && fb) el.placeholder = fb; };
  
  // Page title & tabs
  set('page_title', 'PAGE_TITLE', '小陆同学');
  set('tab_asr', 'TAB_ASR', '语音识别');
  set('tab_llm', 'TAB_LLM', 'AI 大脑');
  set('tab_tts', 'TAB_TTS', '语音合成');
  set('tab_agent', 'TAB_AGENT', '角色');
  
  // Agent panel
  set('sec_name', 'NAME_SECTION', '称呼设置');
  set('lbl_agent_name', 'AGENT_NAME_LABEL', '智能体名字');
  setPh('agent_name', 'AGENT_NAME_PLACEHOLDER', '如：小陆、XGO');
  set('lbl_user_nickname', 'USER_NICKNAME_LABEL', '叫我什么');
  setPh('user_nickname', 'USER_NICKNAME_PLACEHOLDER', '如：主人、小朋友');
  set('sec_personality', 'PERSONALITY_TYPE', '选择您的性格类型');
  set('lbl_quick_test', 'QUICK_TEST', '快速测试');
  set('quiz_q1', 'QUIZ_Q1'); set('quiz_q1_a', 'QUIZ_Q1_A'); set('quiz_q1_b', 'QUIZ_Q1_B');
  set('quiz_q2', 'QUIZ_Q2'); set('quiz_q2_a', 'QUIZ_Q2_A'); set('quiz_q2_b', 'QUIZ_Q2_B');
  set('quiz_q3', 'QUIZ_Q3'); set('quiz_q3_a', 'QUIZ_Q3_A'); set('quiz_q3_b', 'QUIZ_Q3_B');
  set('quiz_q4', 'QUIZ_Q4'); set('quiz_q4_a', 'QUIZ_Q4_A'); set('quiz_q4_b', 'QUIZ_Q4_B');
  set('sec_requirements', 'REQUIREMENTS', '需求描述');
  setPh('agent_requirements', 'REQUIREMENTS_PLACEHOLDER', '描述你想要的机器人性格...');
  set('sec_generate', 'GENERATE_EDIT_SECTION', '生成与编辑');
  set('btn_gen_text', 'GENERATE_PROMPT', '✨ 自动生成提示词');
  set('lbl_current_prompt', 'CURRENT_PROMPT', '当前提示词');
  set('hint_prompt', 'PROMPT_HINT', '此提示词将作为 LLM 的 System Prompt');
  set('sec_memory', 'MEMORY_SECTION', '长期记忆');
  set('lbl_memory_enable', 'MEMORY_ENABLE', '启用长期记忆');
  set('tip_memory', 'MEMORY_TIP', '开启后，每次对话结束时会自动总结并记住用户偏好...');
  setPh('memory_content', 'MEMORY_PLACEHOLDER', '记忆内容会在对话后自动更新...');
  set('btn_clear_memory', 'MEMORY_CLEAR_BTN', '清除记忆');
  
  // ASR panel
  set('lbl_asr_provider', 'ASR_PROVIDER_LABEL', 'Provider');
  set('lbl_asr_api_key', 'ASR_API_KEY_LABEL', 'API Key');
  setPh('asr_aliyun_key', 'ASR_API_KEY_PLACEHOLDER', 'sk-xxx');
  set('lbl_asr_model', 'ASR_MODEL_LABEL', 'Model');
  set('lbl_asr_lang', 'ASR_LANGUAGE_LABEL', 'Language');
  set('lbl_asr_vad', 'ASR_VAD_LABEL', 'VAD Threshold');
  set('lbl_asr_silence', 'ASR_SILENCE_LABEL', 'Silence (ms)');
  set('lbl_asr_dg_key', 'ASR_API_KEY_LABEL', 'API Key');
  setPh('asr_dg_key', 'ASR_DG_KEY_PLACEHOLDER', 'Your Deepgram API Key');
  set('lbl_asr_dg_model', 'ASR_MODEL_LABEL', 'Model');
  set('lbl_asr_dg_lang', 'ASR_LANGUAGE_LABEL', 'Language');
  set('lbl_asr_dg_vad', 'ASR_VAD_SILENCE_LABEL', 'VAD Silence (ms)');
  set('tip_asr_dg', 'ASR_DG_TIP', 'Deepgram ASR: Real-time WebSocket streaming...');
  set('btn_test_asr', 'ASR_TEST_BTN', 'Test ASR Connection');
  
  // LLM panel
  set('lbl_llm_provider', 'LLM_PROVIDER_LABEL', 'Provider Preset');
  set('lbl_llm_api_key', 'LLM_API_KEY_LABEL', 'API Key');
  setPh('llm_key', 'LLM_API_KEY_PLACEHOLDER', 'sk-xxx');
  set('lbl_llm_base_url', 'LLM_BASE_URL_LABEL', 'Base URL');
  set('lbl_llm_model', 'LLM_MODEL_LABEL', 'Model');
  setPh('llm_model', 'LLM_MODEL_PLACEHOLDER', 'model-id');
  set('tip_llm_prompt', 'PROMPT_MOVED_HINT', '💡 System prompt is configured in the Agent tab');
  set('lbl_llm_tools', 'LLM_TOOLS_LABEL', 'Enable Function Call');
  set('lbl_llm_search', 'LLM_SEARCH_LABEL', 'Enable Web Search');
  set('tip_llm_vlm', 'LLM_VLM_TIP', '📷 VLM...');
  set('btn_test_llm', 'LLM_TEST_BTN', 'Test LLM Connection');
  
  // TTS panel
  set('lbl_tts_provider', 'TTS_PROVIDER_LABEL', 'Provider');
  set('lbl_tts_aliyun_key', 'TTS_API_KEY_LABEL', 'API Key');
  setPh('tts_aliyun_key', 'TTS_ALIYUN_KEY_PLACEHOLDER', 'sk-xxx');
  set('lbl_tts_voice', 'TTS_VOICE_LABEL', 'Voice');
  set('lbl_tts_dg_key', 'TTS_API_KEY_LABEL', 'API Key');
  setPh('tts_dg_key', 'TTS_DG_KEY_PLACEHOLDER', 'Your Deepgram API Key');
  set('lbl_tts_dg_model', 'TTS_MODEL_LABEL', 'Model / Voice');
  set('lbl_tts_dg_rate', 'TTS_SAMPLE_RATE_LABEL', 'Sample Rate');
  set('tip_tts_dg', 'TTS_DG_TIP', 'Deepgram TTS: Real-time WebSocket...');
  set('btn_test_tts', 'TTS_TEST_BTN', 'Test TTS');
  set('btn_save', 'SAVE_BTN', '💾 Save Configuration');
  
  // ASR lang options
  const asrLangZh = document.querySelector('#asr_aliyun_lang option[value="zh"]');
  const asrLangEn = document.querySelector('#asr_aliyun_lang option[value="en"]');
  if (asrLangZh && LANGS.ASR_LANG_ZH) asrLangZh.textContent = LANGS.ASR_LANG_ZH;
  if (asrLangEn && LANGS.ASR_LANG_EN) asrLangEn.textContent = LANGS.ASR_LANG_EN;
  
  // ASR provider options
  const asrProvAli = document.querySelector('#asr_provider option[value="aliyun"]');
  const asrProvDg = document.querySelector('#asr_provider option[value="deepgram"]');
  if (asrProvAli && LANGS.ASR_PROVIDER_ALIYUN) asrProvAli.textContent = LANGS.ASR_PROVIDER_ALIYUN;
  if (asrProvDg && LANGS.ASR_PROVIDER_DEEPGRAM) asrProvDg.textContent = LANGS.ASR_PROVIDER_DEEPGRAM;
  
  // LLM provider options
  ['aliyun','openai','google','doubao','custom'].forEach(p => {
    const opt = document.querySelector('#llm_provider option[value="'+p+'"]');
    const key = 'LLM_PROVIDER_' + p.toUpperCase();
    if (opt && LANGS[key]) opt.textContent = LANGS[key];
  });
  
  // TTS provider options
  const ttsProvAli = document.querySelector('#tts_provider option[value="aliyun"]');
  const ttsProvDg = document.querySelector('#tts_provider option[value="deepgram"]');
  if (ttsProvAli && LANGS.TTS_PROVIDER_ALIYUN) ttsProvAli.textContent = LANGS.TTS_PROVIDER_ALIYUN;
  if (ttsProvDg && LANGS.TTS_PROVIDER_DEEPGRAM) ttsProvDg.textContent = LANGS.TTS_PROVIDER_DEEPGRAM;
  
  // Update memory char count (uses localized unit)
  updateMemoryCharCount();
}

// Init: load saved config into UI
function loadUI() {
  applyI18n();
  const c = config;
  // ASR
  document.getElementById('asr_provider').value = c.asr?.provider||'aliyun'; toggleASR();
  document.getElementById('asr_aliyun_key').value = c.asr?.aliyun?.api_key||'';
  document.getElementById('asr_aliyun_model').value = c.asr?.aliyun?.model||'qwen3-asr-flash-realtime';
  document.getElementById('asr_aliyun_lang').value = c.asr?.aliyun?.language||'zh';
  document.getElementById('asr_aliyun_vad').value = c.asr?.aliyun?.vad_threshold||0.5;
  document.getElementById('asr_aliyun_silence').value = c.asr?.aliyun?.silence_duration_ms||800;
  document.getElementById('asr_dg_key').value = c.asr?.deepgram?.api_key || c.tts?.deepgram?.api_key || '';
  document.getElementById('asr_dg_model').value = c.asr?.deepgram?.model || 'nova-3';
  document.getElementById('asr_dg_lang').value = c.asr?.deepgram?.language || 'zh';
  document.getElementById('asr_dg_vad').value = c.asr?.deepgram?.vad_silence_ms || 1000;
  // Agent / Role
  document.getElementById('agent_name').value = c.role?.agent_name || '';
  document.getElementById('user_nickname').value = c.role?.user_nickname || '';
  selectedMBTI = c.role?.mbti || null;
  quizAnswers = c.role?.quiz_answers || [-1,-1,-1,-1];
  document.getElementById('agent_requirements').value = c.role?.requirements || '';
  document.getElementById('agent_prompt').value = c.llm?.system_prompt || LANGS.DEFAULT_SYSTEM_PROMPT || '';
  renderMBTI();
  // Restore quiz UI
  quizAnswers.forEach((a,q) => {
    if (a >= 0) {
      const opts = document.querySelectorAll('#quiz_body .quiz-opts')[q];
      if (opts) opts.querySelectorAll('.quiz-opt').forEach((o,i) => o.classList.toggle('selected', i===a));
    }
  });
  // LLM
  const llmProv = c.llm?.provider||'aliyun';
  document.getElementById('llm_provider').value = llmProv;
  selectLLMPreset();
  // Load key: localStorage first, then config provider_keys, then legacy api_key
  const llmSavedKeys = JSON.parse(localStorage.getItem('llm_provider_keys') || '{}');
  const llmConfigKeys = c.llm?.provider_keys || {};
  document.getElementById('llm_key').value = llmSavedKeys[llmProv] || llmConfigKeys[llmProv] || c.llm?.api_key||'';
  // Restore URL: localStorage > config provider_urls > config base_url
  const llmSavedUrls = JSON.parse(localStorage.getItem('llm_provider_urls') || '{}');
  const llmConfigUrls = c.llm?.provider_urls || {};
  document.getElementById('llm_url').value = llmSavedUrls[llmProv] || llmConfigUrls[llmProv] || c.llm?.base_url||'';
  document.getElementById('llm_model').value = c.llm?.model||'';
  document.getElementById('llm_tools').checked = c.llm?.enable_tools!==false;
  document.getElementById('llm_search').checked = c.llm?.enable_search!==false;
  // TTS
  document.getElementById('tts_provider').value = c.tts?.provider||'aliyun'; toggleTTS();
  document.getElementById('tts_aliyun_key').value = c.tts?.aliyun?.api_key||'';
  document.getElementById('tts_aliyun_voice').value = c.tts?.aliyun?.voice||'Cherry';
  document.getElementById('tts_dg_key').value = c.tts?.deepgram?.api_key || c.asr?.deepgram?.api_key || '';
  document.getElementById('tts_dg_model').value = c.tts?.deepgram?.model || 'aura-2-thalia-en';
  document.getElementById('tts_dg_rate').value = c.tts?.deepgram?.sample_rate || 48000;
  // Memory
  document.getElementById('memory_enabled').checked = c.memory?.enabled||false;
  document.getElementById('memory_content').value = c.memory?.content||'';
  updateMemoryCharCount();
}
function updateMemoryCharCount() {
  const ta = document.getElementById('memory_content');
  const unit = LANGS.MEMORY_CHAR_COUNT || 'chars';
  document.getElementById('memory_char_count').textContent = ta.value.length + ' / 1000 ' + unit;
}
document.getElementById('memory_content').addEventListener('input', updateMemoryCharCount);
async function clearMemory() {
  if (!confirm(LANGS.MEMORY_CONFIRM || 'Are you sure you want to clear all long-term memory? This cannot be undone.')) return;
  document.getElementById('memory_content').value = '';
  updateMemoryCharCount();
  try {
    const r = await fetch('/api/memory/clear', { method:'POST' });
    const d = await r.json();
    const st = document.getElementById('memory_status');
    st.className = 'status ' + (d.ok?'ok':'err');
    st.textContent = d.msg || (LANGS.MEMORY_CLEARED || 'Memory cleared');
  } catch(e) {
    const st = document.getElementById('memory_status');
    st.className='status err'; st.textContent=e.message;
  }
}
// Initialize provider links on load
updateProviderLink('asr', document.getElementById('asr_provider').value);
updateProviderLink('llm', document.getElementById('llm_provider').value);
updateProviderLink('tts', document.getElementById('tts_provider').value);
loadUI();
</script>
</body>
</html>
"""
