import React, {useEffect, useMemo, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {
  Bot,
  Brain,
  Cable,
  Clipboard,
  Code2,
  Database,
  FileText,
  Headphones,
  Inbox,
  LogIn,
  MessageCircle,
  RefreshCw,
  Save,
  Send,
  ShieldAlert,
  Sparkles,
  UserRoundCog
} from 'lucide-react';
import './styles.css';

const API_PREFIX = import.meta.env.BASE_URL === '/' ? '' : import.meta.env.BASE_URL.replace(/\/$/, '');
const apiUrl = (path: string) => `${API_PREFIX}${path.startsWith('/') ? path : `/${path}`}`;

type Section = 'cockpit' | 'scripts' | 'channels' | 'knowledge' | 'inbox' | 'desktop' | 'widget';

type FAQItem = {
  question: string;
  answer: string;
};

type MerchantProfile = {
  id?: number | null;
  username: string;
  merchant_code: string;
  business_name: string;
  industry: string;
  business_intro: string;
  products_services: string;
  pricing: string;
  promotions: string;
  hours: string;
  contact: string;
  faq: FAQItem[];
  welcome_message: string;
};

type DashboardOverview = {
  today_conversations: number;
  auto_replies: number;
  leads: number;
  handoff_needed: number;
  ai_mode: string;
  knowledge_items: number;
  enabled_channels: number;
};

type ChannelConfig = {
  channel: string;
  display_name: string;
  mode: 'assist' | 'official_api' | 'manual';
  status: 'draft' | 'ready' | 'connected' | 'blocked';
  official_api_url: string;
  webhook_url: string;
  auto_reply_enabled: boolean;
  handoff_required: boolean;
  notes: string;
};

type KnowledgeItem = {
  id?: number | null;
  title: string;
  content: string;
  source_type: string;
  tags: string;
  created_at: string;
};

type ServiceScriptStep = {
  title: string;
  message: string;
  goal: string;
};

type ServiceScriptResult = {
  title: string;
  channel: string;
  scenario: string;
  opening: string;
  steps: ServiceScriptStep[];
  objection_replies: ServiceScriptStep[];
  closing: string;
  knowledge_imported: number;
};

type ConversationSummary = {
  session_id: string;
  customer_id?: number | null;
  visitor_name: string;
  last_query: string;
  last_response: string;
  intent_score: number;
  need_followup: boolean;
  message_count: number;
  updated_at: string;
};

type ConversationDetail = {
  session_id: string;
  messages: Array<{
    role: 'visitor' | 'assistant';
    text: string;
    created_at: string;
    intent_score?: number;
    need_followup?: boolean;
  }>;
};

const emptyProfile: MerchantProfile = {
  username: '',
  merchant_code: '',
  business_name: '',
  industry: '通用服务',
  business_intro: '',
  products_services: '',
  pricing: '',
  promotions: '',
  hours: '',
  contact: '',
  faq: [
    {question: '你们能做什么？', answer: '我们可以自动回复客户咨询，并把高意向客户标记出来。'},
    {question: '怎么联系人工？', answer: '留下电话或微信后，人工顾问会继续跟进。'}
  ],
  welcome_message: '您好，我是 AI 客服。请问有什么可以帮您？'
};

const channelNames: Record<string, string> = {
  web_widget: '网页客服',
  wechat: '微信',
  douyin: '抖音',
  taobao: '淘宝',
  pdd: '拼多多'
};

const statusNames: Record<string, string> = {
  draft: '未配置',
  ready: '待联调',
  connected: '已接入',
  blocked: '缺权限'
};

function authHeaders(token: string) {
  return {Authorization: `Bearer ${token}`};
}

function App() {
  const [token, setToken] = useState(() => localStorage.getItem('cs_token') || '');
  const [section, setSection] = useState<Section>('cockpit');
  const [profile, setProfile] = useState<MerchantProfile>(emptyProfile);
  const [overview, setOverview] = useState<DashboardOverview | null>(null);
  const [channels, setChannels] = useState<ChannelConfig[]>([]);
  const [knowledge, setKnowledge] = useState<KnowledgeItem[]>([]);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState('');
  const [detail, setDetail] = useState<ConversationDetail | null>(null);
  const [loginDraft, setLoginDraft] = useState({username: 'ai_kefu_demo', password: 'admin123'});
  const [importDraft, setImportDraft] = useState({
    title: '商家客服话术',
    source_type: 'script',
    tags: '客服,成交',
    content: 'Q: 你们怎么收费？\nA: Starter 99 元/月，Pro 299 元/月，定制部署按需求报价。\nQ: 可以接入官网吗？\nA: 可以，复制后台生成的 script 到网站即可出现客服气泡。'
  });
  const [knowledgeFile, setKnowledgeFile] = useState<File | null>(null);
  const [scriptDraft, setScriptDraft] = useState({
    channel: 'wechat',
    scenario: 'full_pack',
    product_name: '',
    customer_pain: '',
    offer: '',
    tone: 'natural',
    save_to_knowledge: true
  });
  const [scriptResult, setScriptResult] = useState<ServiceScriptResult | null>(null);
  const [replyDraft, setReplyDraft] = useState({
    channel: 'wechat',
    customer_name: '',
    message: '客户问：可以优惠吗？多久能接入？',
    reply: ''
  });
  const [status, setStatus] = useState('');
  const [loading, setLoading] = useState(false);

  const selectedConversation = useMemo(
    () => conversations.find((item) => item.session_id === selectedSessionId) ?? conversations[0],
    [conversations, selectedSessionId]
  );

  useEffect(() => {
    if (!token) return;
    void refreshAll(token);
  }, [token]);

  useEffect(() => {
    if (!token || !selectedConversation?.session_id) {
      setDetail(null);
      return;
    }
    void loadConversation(selectedConversation.session_id);
  }, [token, selectedConversation?.session_id]);

  async function apiGet<T>(path: string, nextToken = token): Promise<T> {
    const response = await fetch(apiUrl(path), {headers: authHeaders(nextToken)});
    if (!response.ok) throw new Error(await response.text());
    return response.json() as Promise<T>;
  }

  async function refreshAll(nextToken = token) {
    setLoading(true);
    setStatus('');
    try {
      const [profileData, overviewData, channelData, knowledgeData, conversationData] = await Promise.all([
        apiGet<MerchantProfile>('/api/merchant/profile', nextToken),
        apiGet<DashboardOverview>('/api/dashboard/overview', nextToken),
        apiGet<ChannelConfig[]>('/api/channels', nextToken),
        apiGet<KnowledgeItem[]>('/api/knowledge', nextToken),
        apiGet<ConversationSummary[]>('/api/conversations', nextToken)
      ]);
      setProfile({...emptyProfile, ...profileData});
      setOverview(overviewData);
      setChannels(Array.isArray(channelData) ? channelData : []);
      setKnowledge(Array.isArray(knowledgeData) ? knowledgeData : []);
      setConversations(Array.isArray(conversationData) ? conversationData : []);
      if (Array.isArray(conversationData) && conversationData[0]) setSelectedSessionId(conversationData[0].session_id);
    } catch {
      setStatus('登录已失效或服务暂不可用，请重新登录。');
      localStorage.removeItem('cs_token');
      setToken('');
    } finally {
      setLoading(false);
    }
  }

  async function login() {
    setLoading(true);
    setStatus('');
    try {
      const response = await fetch(apiUrl('/api/auth/login'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(loginDraft)
      });
      if (!response.ok) throw new Error('login failed');
      const data = await response.json();
      localStorage.setItem('cs_token', data.token);
      setToken(data.token);
      setProfile({...emptyProfile, ...data.merchant});
      setStatus('登录成功');
    } catch {
      setStatus('登录失败，请检查商户账号和密码。');
    } finally {
      setLoading(false);
    }
  }

  async function saveProfile() {
    setLoading(true);
    setStatus('');
    try {
      const response = await fetch(apiUrl('/api/merchant/profile'), {
        method: 'PUT',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify(profile)
      });
      if (!response.ok) throw new Error('save failed');
      setProfile(await response.json());
      setStatus('商家资料已保存，AI 会按新资料回复。');
      await refreshAll();
    } catch {
      setStatus('保存失败，请稍后重试。');
    } finally {
      setLoading(false);
    }
  }

  async function saveChannel(channel: ChannelConfig) {
    setLoading(true);
    setStatus('');
    try {
      const response = await fetch(apiUrl(`/api/channels/${channel.channel}`), {
        method: 'PUT',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify(channel)
      });
      if (!response.ok) throw new Error('channel failed');
      setStatus(`${channel.display_name || channelNames[channel.channel]} 配置已保存。`);
      await refreshAll();
    } catch {
      setStatus('渠道保存失败，请检查配置。');
    } finally {
      setLoading(false);
    }
  }

  async function importKnowledge() {
    setLoading(true);
    setStatus('');
    try {
      const response = await fetch(apiUrl('/api/knowledge/import'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({...importDraft, sync_to_faq: true})
      });
      if (!response.ok) throw new Error('import failed');
      const data = await response.json();
      setStatus(`已导入 ${data.imported} 条知识，追加 ${data.faq_added} 条 FAQ。`);
      await refreshAll();
    } catch {
      setStatus('导入失败，请检查话术内容。');
    } finally {
      setLoading(false);
    }
  }

  async function uploadKnowledgeFile() {
    if (!knowledgeFile) {
      setStatus('请先选择 txt、md、csv 或 json 文档。');
      return;
    }
    setLoading(true);
    setStatus('');
    try {
      const form = new FormData();
      form.append('file', knowledgeFile);
      const query = new URLSearchParams({
        title: importDraft.title || knowledgeFile.name,
        source_type: importDraft.source_type,
        tags: importDraft.tags || '文档导入',
        sync_to_faq: 'true'
      });
      const response = await fetch(apiUrl(`/api/knowledge/upload?${query.toString()}`), {
        method: 'POST',
        headers: authHeaders(token),
        body: form
      });
      if (!response.ok) throw new Error(await response.text());
      const data = await response.json();
      setStatus(`已从 ${data.filename || knowledgeFile.name} 导入 ${data.imported} 条知识，追加 ${data.faq_added} 条 FAQ。`);
      setKnowledgeFile(null);
      await refreshAll();
    } catch {
      setStatus('文档导入失败。目前仅支持 txt/md/csv/json，PDF/Word 后续再接解析。');
    } finally {
      setLoading(false);
    }
  }

  async function generateServiceScript() {
    setLoading(true);
    setStatus('');
    try {
      const response = await fetch(apiUrl('/api/service-scripts/generate'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify(scriptDraft)
      });
      if (!response.ok) throw new Error('script failed');
      const data = await response.json();
      setScriptResult(data);
      setStatus(data.knowledge_imported ? '客服脚本已生成，并保存到知识库。' : '客服脚本已生成。');
      await refreshAll();
    } catch {
      setStatus('生成客服脚本失败，请检查 AI 配置或稍后重试。');
    } finally {
      setLoading(false);
    }
  }

  async function generateReplyDraft() {
    setLoading(true);
    setStatus('');
    try {
      const response = await fetch(apiUrl('/api/reply/draft'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify(replyDraft)
      });
      if (!response.ok) throw new Error('draft failed');
      const data = await response.json();
      setReplyDraft((current) => ({...current, reply: data.reply}));
      setStatus(data.need_followup ? '已生成回复草稿，当前消息建议人工确认。' : '已生成回复草稿。');
    } catch {
      setStatus('生成回复失败，请检查 AI 配置。');
    } finally {
      setLoading(false);
    }
  }

  async function loadConversation(sessionId: string) {
    try {
      setDetail(await apiGet<ConversationDetail>(`/api/conversations/${sessionId}`));
    } catch {
      setDetail(null);
    }
  }

  async function markHandoff(sessionId: string) {
    await fetch(apiUrl(`/api/conversations/${sessionId}/handoff`), {method: 'POST', headers: authHeaders(token)});
    await refreshAll();
    await loadConversation(sessionId);
  }

  function updateProfile<Key extends keyof MerchantProfile>(key: Key, value: MerchantProfile[Key]) {
    setProfile((current) => ({...current, [key]: value}));
  }

  function updateFaq(index: number, patch: Partial<FAQItem>) {
    setProfile((current) => ({
      ...current,
      faq: current.faq.map((item, itemIndex) => itemIndex === index ? {...item, ...patch} : item)
    }));
  }

  function addFaq() {
    setProfile((current) => ({...current, faq: [...current.faq, {question: '', answer: ''}]}));
  }

  function updateChannel(index: number, patch: Partial<ChannelConfig>) {
    setChannels((current) => current.map((item, itemIndex) => itemIndex === index ? {...item, ...patch} : item));
  }

  const widgetOrigin = typeof window === 'undefined' ? '' : window.location.origin;
  const widgetCode = `<script src="${widgetOrigin}${apiUrl(`/api/widget.js?merchant_code=${encodeURIComponent(profile.merchant_code || 'WJDEMO001')}`)}"></script>`;
  const testUrl = `${widgetOrigin}${apiUrl(`/api/widget-test?merchant_code=${encodeURIComponent(profile.merchant_code || 'WJDEMO001')}`)}`;
  const desktopAutoCommand = 'npm run desktop:auto';
  const desktopSafeCommand = 'npm run desktop:listen -- --platform auto --source auto --paste';
  const desktopTargetCommand = 'npm run desktop:listen -- --platform wechat --target-title "微信|WeChat|企业微信" --source auto --paste';
  const desktopKnowledgeCommand = 'npm run desktop:listen -- --platform auto --source auto --paste --knowledge-file docs/examples/merchant_knowledge.example.txt';
  const desktopDiagnoseCommand = 'npm run desktop:diagnose';
  const desktopDiagnoseBat = 'scripts/start_desktop_diagnostics.bat';
  const desktopOcrSetupCommand = 'powershell -ExecutionPolicy Bypass -File scripts/setup_desktop_ocr.ps1';
  const acceptanceCommand = 'npm run acceptance:check';

  if (!token) {
    return (
      <main className="loginShell">
        <section className="loginCard">
          <div className="brandMark"><Brain size={30} /></div>
          <p>Merchant Brain</p>
          <h1>商家 AI 客服大脑</h1>
          <span>网页气泡先自动回复；微信、抖音、淘宝、拼多多先做人工辅助和官方 API 接入配置。</span>
          <label>商户账号<input value={loginDraft.username} onChange={(event) => setLoginDraft({...loginDraft, username: event.target.value})} /></label>
          <label>密码<input type="password" value={loginDraft.password} onChange={(event) => setLoginDraft({...loginDraft, password: event.target.value})} /></label>
          <button className="primaryButton" onClick={login} disabled={loading}>{loading ? <RefreshCw className="spin" size={18} /> : <LogIn size={18} />}登录后台</button>
          {status && <div className="statusText">{status}</div>}
        </section>
      </main>
    );
  }

  return (
    <main className="brainShell">
      <div className="starField" />
      <aside className="brainSidebar">
        <div className="csBrand">
          <span><Brain size={22} /></span>
          <div>
            <strong>{profile.business_name || 'AI 客服大脑'}</strong>
            <small>{profile.merchant_code || '未配置商户码'}</small>
          </div>
        </div>
        <nav>
          <button className={section === 'cockpit' ? 'active' : ''} onClick={() => setSection('cockpit')}><Sparkles size={18} />商家大脑</button>
          <button className={section === 'scripts' ? 'active' : ''} onClick={() => setSection('scripts')}><FileText size={18} />客服脚本</button>
          <button className={section === 'channels' ? 'active' : ''} onClick={() => setSection('channels')}><Cable size={18} />渠道接入</button>
          <button className={section === 'knowledge' ? 'active' : ''} onClick={() => setSection('knowledge')}><Database size={18} />知识库导入</button>
          <button className={section === 'inbox' ? 'active' : ''} onClick={() => setSection('inbox')}><Inbox size={18} />会话收件箱</button>
          <button className={section === 'desktop' ? 'active' : ''} onClick={() => setSection('desktop')}><Headphones size={18} />桌面自动客服</button>
          <button className={section === 'widget' ? 'active' : ''} onClick={() => setSection('widget')}><Code2 size={18} />网页气泡</button>
        </nav>
        <button className="ghostButton" onClick={() => refreshAll()} disabled={loading}>{loading ? <RefreshCw className="spin" size={16} /> : <RefreshCw size={16} />}刷新真实数据</button>
        <button className="ghostButton" onClick={() => { localStorage.removeItem('cs_token'); setToken(''); }}>退出登录</button>
        {status && <div className="statusText">{status}</div>}
      </aside>

      <section className="brainMain">
        {section === 'cockpit' && (
          <div className="pageStack">
            <PageTitle eyebrow="Second Brain" title="把商家的话术、渠道、会话都收进一个大脑" desc="第一阶段不偷跑平台私信，只做网页自动回复、渠道配置、人工辅助草稿和知识库落库。" />
            <div className="metricGrid six">
              <Metric label="今日会话" value={overview?.today_conversations ?? 0} />
              <Metric label="自动回复" value={overview?.auto_replies ?? 0} />
              <Metric label="线索客户" value={overview?.leads ?? 0} />
              <Metric label="待人工接管" value={overview?.handoff_needed ?? 0} warn />
              <Metric label="知识条目" value={overview?.knowledge_items ?? 0} />
              <Metric label="启用渠道" value={overview?.enabled_channels ?? 0} />
            </div>
            <div className="cosmosPanel">
              <div>
                <small>AI 模式</small>
                <h2>{overview?.ai_mode === 'ai' ? 'API2D 已接入，网页客服可自动回复' : '当前是模板兜底模式'}</h2>
                <p>微信、抖音、淘宝、拼多多先生成“像人工”的回复草稿，等官方 API 权限到位后再切自动发送。</p>
              </div>
              <Bot size={42} />
            </div>
            <section className="operatorGrid">
              <div className="panel">
                <div className="panelHeader"><strong>商家资料</strong><button onClick={() => setSection('knowledge')}><UserRoundCog size={16} />编辑</button></div>
                <p>{profile.business_intro || '还没有填写业务介绍。'}</p>
                <small>{profile.products_services || '还没有填写商品/服务。'}</small>
              </div>
              <div className="panel">
                <div className="panelHeader"><strong>客服脚本</strong><button onClick={() => setSection('scripts')}><FileText size={16} />生成</button></div>
                <p>{scriptResult?.title || '先生成一套微信/抖音/淘宝/拼多多客服成交脚本。'}</p>
                <small>{scriptResult?.opening || '脚本会自动保存到知识库，后续 AI 回复也能用。'}</small>
              </div>
            </section>
          </div>
        )}

        {section === 'scripts' && (
          <div className="pageStack">
            <PageTitle eyebrow="Scripts" title="先把客服脚本做扎实，再谈自动化" desc="按渠道和场景生成开场、跟进、异议处理、收口留资，生成后自动沉淀进知识库。" />
            <div className="scriptWorkbench">
              <div className="panel scriptForm">
                <div className="panelHeader"><strong>生成参数</strong><button onClick={generateServiceScript} disabled={loading}><Send size={16} />生成脚本</button></div>
                <div className="formGrid">
                  <label>渠道
                    <select value={scriptDraft.channel} onChange={(event) => setScriptDraft({...scriptDraft, channel: event.target.value})}>
                      {channels.map((channel) => <option key={channel.channel} value={channel.channel}>{channel.display_name}</option>)}
                    </select>
                  </label>
                  <label>场景
                    <select value={scriptDraft.scenario} onChange={(event) => setScriptDraft({...scriptDraft, scenario: event.target.value})}>
                      <option value="full_pack">完整成交脚本</option>
                      <option value="new_customer">新客开场</option>
                      <option value="price">价格咨询</option>
                      <option value="objection">异议处理</option>
                      <option value="after_sale">售后安抚</option>
                      <option value="lead_capture">留资转化</option>
                    </select>
                  </label>
                  <label>语气
                    <select value={scriptDraft.tone} onChange={(event) => setScriptDraft({...scriptDraft, tone: event.target.value})}>
                      <option value="natural">自然真人</option>
                      <option value="professional">专业克制</option>
                      <option value="friendly">亲和热情</option>
                      <option value="urgent">强调转化</option>
                    </select>
                  </label>
                  <label>保存到知识库
                    <select value={scriptDraft.save_to_knowledge ? 'yes' : 'no'} onChange={(event) => setScriptDraft({...scriptDraft, save_to_knowledge: event.target.value === 'yes'})}>
                      <option value="yes">生成后保存</option>
                      <option value="no">只生成预览</option>
                    </select>
                  </label>
                  <label>产品/服务<input value={scriptDraft.product_name} onChange={(event) => setScriptDraft({...scriptDraft, product_name: event.target.value})} placeholder={profile.products_services || '例如：AI 客服系统'} /></label>
                  <label>客户痛点<input value={scriptDraft.customer_pain} onChange={(event) => setScriptDraft({...scriptDraft, customer_pain: event.target.value})} placeholder="例如：咨询多、回复慢、线索漏跟" /></label>
                  <label className="wide">优惠/边界<textarea value={scriptDraft.offer} onChange={(event) => setScriptDraft({...scriptDraft, offer: event.target.value})} placeholder={profile.promotions || '例如：可先试用一个场景；不承诺平台私信自动发送，需官方 API 权限'} /></label>
                </div>
              </div>
              <div className="scriptPreview">
                {!scriptResult && <div className="emptyState">生成后这里会出现完整客服 SOP。</div>}
                {scriptResult && (
                  <article className="scriptResult">
                    <div className="scriptHero">
                      <small>{channelNames[scriptResult.channel] || scriptResult.channel}</small>
                      <h2>{scriptResult.title}</h2>
                      <p>{scriptResult.opening}</p>
                    </div>
                    <div className="scriptStepList">
                      {scriptResult.steps.map((step, index) => (
                        <section className="scriptStep" key={`${step.title}-${index}`}>
                          <em>{String(index + 1).padStart(2, '0')}</em>
                          <div>
                            <strong>{step.title}</strong>
                            <p>{step.message}</p>
                            <small>{step.goal}</small>
                          </div>
                        </section>
                      ))}
                    </div>
                    <div className="objectionGrid">
                      {scriptResult.objection_replies.map((step, index) => (
                        <section className="knowledgeItem" key={`${step.title}-${index}`}>
                          <strong>{step.title}</strong>
                          <p>{step.message}</p>
                          <small>{step.goal}</small>
                        </section>
                      ))}
                    </div>
                    <div className="cosmosPanel compactPanel">
                      <div>
                        <small>收口</small>
                        <p>{scriptResult.closing}</p>
                      </div>
                      <Clipboard size={24} />
                    </div>
                  </article>
                )}
              </div>
            </div>
          </div>
        )}

        {section === 'channels' && (
          <div className="pageStack">
            <PageTitle eyebrow="Channels" title="多平台客服接入，不做违规模拟发送" desc="网页客服已支持自动回复；微信/抖音/淘宝/拼多多先走回复草稿，拿到官方 API 权限后再切自动化。" />
            <div className="channelGrid">
              {channels.map((channel, index) => (
                <div className="channelPanel" key={channel.channel}>
                  <div className="channelTop">
                    <div>
                      <strong>{channel.display_name || channelNames[channel.channel]}</strong>
                      <small>{channel.channel}</small>
                    </div>
                    <em className={`pill ${channel.status}`}>{statusNames[channel.status]}</em>
                  </div>
                  <label>模式
                    <select value={channel.mode} onChange={(event) => updateChannel(index, {mode: event.target.value as ChannelConfig['mode']})}>
                      <option value="assist">人工辅助草稿</option>
                      <option value="official_api">官方 API 自动化</option>
                      <option value="manual">纯人工接管</option>
                    </select>
                  </label>
                  <label>状态
                    <select value={channel.status} onChange={(event) => updateChannel(index, {status: event.target.value as ChannelConfig['status']})}>
                      <option value="draft">未配置</option>
                      <option value="ready">待联调</option>
                      <option value="connected">已接入</option>
                      <option value="blocked">缺权限</option>
                    </select>
                  </label>
                  <label>官方 API / 回调地址<input value={channel.official_api_url} onChange={(event) => updateChannel(index, {official_api_url: event.target.value})} placeholder="拿到平台权限后填写" /></label>
                  <label>内部备注<textarea value={channel.notes} onChange={(event) => updateChannel(index, {notes: event.target.value})} /></label>
                  <div className="switchRow">
                    <label><input type="checkbox" checked={channel.auto_reply_enabled} onChange={(event) => updateChannel(index, {auto_reply_enabled: event.target.checked})} />自动回复</label>
                    <label><input type="checkbox" checked={channel.handoff_required} onChange={(event) => updateChannel(index, {handoff_required: event.target.checked})} />人工确认</label>
                  </div>
                  <button className="primaryButton fit" onClick={() => saveChannel(channel)} disabled={loading}><Save size={16} />保存渠道</button>
                </div>
              ))}
            </div>
            <div className="panel">
              <div className="panelHeader"><strong>人工风格回复草稿</strong><button onClick={generateReplyDraft} disabled={loading}><Send size={16} />生成</button></div>
              <div className="formGrid">
                <label>渠道
                  <select value={replyDraft.channel} onChange={(event) => setReplyDraft({...replyDraft, channel: event.target.value})}>
                    {channels.map((channel) => <option key={channel.channel} value={channel.channel}>{channel.display_name}</option>)}
                  </select>
                </label>
                <label>客户名<input value={replyDraft.customer_name} onChange={(event) => setReplyDraft({...replyDraft, customer_name: event.target.value})} placeholder="可选" /></label>
                <label className="wide">客户原话<textarea value={replyDraft.message} onChange={(event) => setReplyDraft({...replyDraft, message: event.target.value})} /></label>
                <label className="wide">回复草稿<textarea value={replyDraft.reply} onChange={(event) => setReplyDraft({...replyDraft, reply: event.target.value})} placeholder="点击生成后出现，可人工复制或接官方 API 使用" /></label>
              </div>
            </div>
          </div>
        )}

        {section === 'knowledge' && (
          <div className="pageStack">
            <PageTitle eyebrow="Knowledge" title="导入商家的话术、FAQ、商品和政策" desc="商家把已有客服话术贴进来，系统会拆成知识条目，并同步到 AI 回复的 FAQ 里。" />
            <div className="formGrid">
              <label>商家名称<input value={profile.business_name} onChange={(event) => updateProfile('business_name', event.target.value)} /></label>
              <label>行业<input value={profile.industry} onChange={(event) => updateProfile('industry', event.target.value)} /></label>
              <label>营业时间<input value={profile.hours} onChange={(event) => updateProfile('hours', event.target.value)} /></label>
              <label>联系方式<input value={profile.contact} onChange={(event) => updateProfile('contact', event.target.value)} /></label>
              <label className="wide">欢迎语<textarea value={profile.welcome_message} onChange={(event) => updateProfile('welcome_message', event.target.value)} /></label>
              <label className="wide">业务介绍<textarea value={profile.business_intro} onChange={(event) => updateProfile('business_intro', event.target.value)} /></label>
              <label className="wide">商品/服务<textarea value={profile.products_services} onChange={(event) => updateProfile('products_services', event.target.value)} /></label>
              <label>价格/套餐<textarea value={profile.pricing} onChange={(event) => updateProfile('pricing', event.target.value)} /></label>
              <label>优惠活动<textarea value={profile.promotions} onChange={(event) => updateProfile('promotions', event.target.value)} /></label>
            </div>
            <button className="primaryButton fit" onClick={saveProfile} disabled={loading}><Save size={18} />保存商家资料</button>
            <div className="panel">
              <div className="panelHeader"><strong>话术导入</strong><button onClick={importKnowledge} disabled={loading}><Database size={16} />导入知识库</button></div>
              <div className="formGrid">
                <label>标题<input value={importDraft.title} onChange={(event) => setImportDraft({...importDraft, title: event.target.value})} /></label>
                <label>标签<input value={importDraft.tags} onChange={(event) => setImportDraft({...importDraft, tags: event.target.value})} /></label>
                <label>类型
                  <select value={importDraft.source_type} onChange={(event) => setImportDraft({...importDraft, source_type: event.target.value})}>
                    <option value="script">客服话术</option>
                    <option value="faq">FAQ</option>
                    <option value="product">商品资料</option>
                    <option value="policy">售后政策</option>
                    <option value="manual">手动资料</option>
                  </select>
                </label>
                <label className="wide">内容<textarea className="largeText" value={importDraft.content} onChange={(event) => setImportDraft({...importDraft, content: event.target.value})} /></label>
              </div>
              <div className="uploadStrip">
                <div>
                  <strong>添加文档到知识库</strong>
                  <small>支持 txt、md、csv、json。把客服 FAQ、商品说明、售后政策放进去，AI 回复会读取这些知识。</small>
                </div>
                <label className="filePicker">
                  <input
                    type="file"
                    accept=".txt,.md,.csv,.json,text/plain,text/markdown,application/json"
                    onChange={(event) => setKnowledgeFile(event.target.files?.[0] ?? null)}
                  />
                  {knowledgeFile ? knowledgeFile.name : '选择文档'}
                </label>
                <button className="primaryButton fit" onClick={uploadKnowledgeFile} disabled={loading || !knowledgeFile}>
                  <Database size={16} />上传并解析
                </button>
              </div>
            </div>
            <div className="knowledgeList">
              {knowledge.length === 0 && <div className="emptyState">还没有知识条目。先导入一段商家话术。</div>}
              {knowledge.map((item) => (
                <article className="knowledgeItem" key={item.id ?? `${item.title}-${item.created_at}`}>
                  <strong>{item.title}</strong>
                  <p>{item.content}</p>
                  <small>{item.source_type} · {item.tags || '未打标签'} · {item.created_at}</small>
                </article>
              ))}
            </div>
            <div className="panel">
              <div className="panelHeader"><strong>FAQ</strong><button onClick={addFaq}>添加问题</button></div>
              {profile.faq.map((item, index) => (
                <div className="faqRow" key={index}>
                  <input placeholder="客户常问问题" value={item.question} onChange={(event) => updateFaq(index, {question: event.target.value})} />
                  <textarea placeholder="标准答案" value={item.answer} onChange={(event) => updateFaq(index, {answer: event.target.value})} />
                </div>
              ))}
            </div>
          </div>
        )}

        {section === 'inbox' && (
          <div className="inboxLayout">
            <div className="conversationList">
              <PageTitle eyebrow="Inbox" title="会话收件箱" desc="AI 自动回复后，每轮对话都会落库。" compact />
              {conversations.length === 0 && <div className="emptyState">还没有真实会话。先到“网页气泡”打开测试页发一条消息。</div>}
              {conversations.map((item) => (
                <button className={`conversationItem ${item.session_id === selectedConversation?.session_id ? 'active' : ''}`} key={item.session_id} onClick={() => setSelectedSessionId(item.session_id)}>
                  <strong>{item.visitor_name}</strong>
                  <span>{item.last_query}</span>
                  <small>{item.message_count} 轮 · 意向 {item.intent_score} · {item.updated_at}</small>
                  {item.need_followup && <em><ShieldAlert size={14} />需接管</em>}
                </button>
              ))}
            </div>
            <div className="conversationDetail">
              {selectedConversation ? (
                <>
                  <div className="detailHeader">
                    <div><small>Session</small><strong>{selectedConversation.session_id}</strong></div>
                    <button onClick={() => markHandoff(selectedConversation.session_id)}><ShieldAlert size={16} />标记人工接管</button>
                  </div>
                  <div className="messageStream">
                    {(detail?.messages ?? []).map((message, index) => (
                      <div className={`chatBubble ${message.role}`} key={`${message.created_at}-${index}`}>
                        <small>{message.role === 'visitor' ? '访客' : 'AI 客服'} · {message.created_at}</small>
                        <span>{message.text}</span>
                      </div>
                    ))}
                  </div>
                </>
              ) : <div className="emptyState">请选择一个会话</div>}
            </div>
          </div>
        )}

        {section === 'desktop' && (
          <div className="pageStack">
            <PageTitle eyebrow="Desktop Agent" title="打开微信、抖音、千牛、拼多多窗口就能辅助回复" desc="桌面助手会自动识别当前客服窗口，读取聊天内容，结合商家知识库生成回复；默认只粘贴候选回复，不自动按 Enter。" />
            <div className="desktopHero">
              <div>
                <small>一键启动</small>
                <h2>双击 scripts/start_desktop_auto_listener.bat</h2>
                <p>保持客服窗口在前台，脚本会自动监听当前窗口。微信、抖音、淘宝/千牛、拼多多共用同一套 AI 回复引擎。</p>
              </div>
              <Headphones size={42} />
            </div>
            <div className="desktopGrid">
              <article className="panel">
                <div className="panelHeader"><strong>安全启动</strong><button onClick={() => navigator.clipboard?.writeText(desktopAutoCommand)}><Clipboard size={16} />复制</button></div>
                <pre className="miniCode">{desktopAutoCommand}</pre>
                <small>自动读取当前客服窗口并粘贴回复，不会自动发送。</small>
              </article>
              <article className="panel">
                <div className="panelHeader"><strong>命令启动</strong><button onClick={() => navigator.clipboard?.writeText(desktopSafeCommand)}><Clipboard size={16} />复制</button></div>
                <pre className="miniCode">{desktopSafeCommand}</pre>
                <small>适合测试窗口识别和读取效果。默认先读 UIA，读不到会尝试 OCR，再退回剪贴板。</small>
              </article>
              <article className="panel">
                <div className="panelHeader"><strong>锁定窗口</strong><button onClick={() => navigator.clipboard?.writeText(desktopTargetCommand)}><Clipboard size={16} />复制</button></div>
                <pre className="miniCode">{desktopTargetCommand}</pre>
                <small>不想依赖前台窗口时，用窗口标题正则绑定微信、千牛或拼多多客服窗口。</small>
              </article>
              <article className="panel">
                <div className="panelHeader"><strong>带本地知识库</strong><button onClick={() => navigator.clipboard?.writeText(desktopKnowledgeCommand)}><Clipboard size={16} />复制</button></div>
                <pre className="miniCode">{desktopKnowledgeCommand}</pre>
                <small>把商家 FAQ、价格、售后政策放进 txt/md/csv/json 文件，桌面助手会一起交给 AI。</small>
              </article>
              <article className="panel">
                <div className="panelHeader"><strong>窗口诊断</strong><button onClick={() => navigator.clipboard?.writeText(desktopDiagnoseCommand)}><Clipboard size={16} />复制</button></div>
                <pre className="miniCode">{desktopDiagnoseCommand}</pre>
                <small>也可以双击 {desktopDiagnoseBat}。打开真实平台客服窗口后运行，能看到 UIA、OCR、剪贴板分别读到了什么。</small>
              </article>
              <article className="panel">
                <div className="panelHeader"><strong>安装 OCR</strong><button onClick={() => navigator.clipboard?.writeText(desktopOcrSetupCommand)}><Clipboard size={16} />复制</button></div>
                <pre className="miniCode">{desktopOcrSetupCommand}</pre>
                <small>如果平台窗口读不到控件文字，就安装 Tesseract OCR 和中文语言包。</small>
              </article>
              <article className="panel">
                <div className="panelHeader"><strong>一键验收</strong><button onClick={() => navigator.clipboard?.writeText(acceptanceCommand)}><Clipboard size={16} />复制</button></div>
                <pre className="miniCode">{acceptanceCommand}</pre>
                <small>检查后台、构建、四个平台回复接口、桌面诊断脚本和文档配置。</small>
              </article>
            </div>
            <div className="channelGrid">
              {[
                ['微信/企业微信', '窗口标题包含 微信、WeChat、企业微信 时自动识别。'],
                ['抖音私信', '窗口标题包含 抖音、巨量、Douyin 时自动识别。'],
                ['淘宝/千牛', '窗口标题包含 千牛、淘宝、旺旺、Qianniu 时自动识别。'],
                ['拼多多', '窗口标题包含 拼多多、PDD、商家后台 时自动识别。']
              ].map(([name, desc]) => (
                <section className="knowledgeItem" key={name}>
                  <strong>{name}</strong>
                  <p>{desc}</p>
                  <small>当前阶段是桌面辅助。真正后台无人值守需要平台官方 API 或授权。</small>
                </section>
              ))}
            </div>
            <div className="cosmosPanel compactPanel">
              <div>
                <small>验收方式</small>
                <p>先打开对应平台客服窗口，再运行桌面助手。看到终端打印 should_reply=true 且输入框出现候选回复，就说明读取、生成、粘贴链路跑通。OCR 需要安装 Tesseract。</p>
              </div>
              <ShieldAlert size={24} />
            </div>
          </div>
        )}

        {section === 'widget' && (
          <div className="pageStack">
            <PageTitle eyebrow="Widget" title="把这段代码放到客户网站" desc="访客在网站右下角聊天，AI 自动回复，后台收件箱能看到全部会话。" />
            <div className="codePanel">
              <pre>{widgetCode}</pre>
              <button onClick={() => navigator.clipboard?.writeText(widgetCode)}><Clipboard size={16} />复制接入代码</button>
            </div>
            <div className="cosmosPanel">
              <div>
                <small>测试入口</small>
                <h2>先打开测试页，右下角会出现客服气泡</h2>
                <p>{testUrl}</p>
              </div>
              <a className="primaryLink" href={testUrl} target="_blank" rel="noreferrer">打开测试页</a>
            </div>
          </div>
        )}
      </section>
    </main>
  );
}

function PageTitle({eyebrow, title, desc, compact = false}: {eyebrow: string; title: string; desc: string; compact?: boolean}) {
  return (
    <div className={`pageTitle ${compact ? 'compact' : ''}`}>
      <p>{eyebrow}</p>
      <h1>{title}</h1>
      <span>{desc}</span>
    </div>
  );
}

function Metric({label, value, warn = false}: {label: string; value: number; warn?: boolean}) {
  return (
    <div className={`metricCard ${warn ? 'warn' : ''}`}>
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

createRoot(document.getElementById('root')!).render(<App />);
