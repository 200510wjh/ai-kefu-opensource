import {useCallback, useEffect, useMemo, useState} from 'react';
import type {FormEvent, ReactNode} from 'react';
import {
  AlertTriangle,
  BarChart3,
  BookOpen,
  Bot,
  CheckCircle2,
  Clock3,
  Database,
  Headphones,
  MessageSquareText,
  PauseCircle,
  SendHorizontal,
  ShieldCheck,
  Sparkles,
  TimerReset,
  Users,
  Workflow,
  Zap
} from 'lucide-react';
import {internalGrowthApi} from './api';
import {Button, EmptyState, MetricCard, Panel, StatusBadge} from './design-system';
import type {
  AnalyticsReport,
  DashboardSummary,
  FollowUpTask,
  Lead,
  SalesAnalysis,
  AIBrainChannel,
  AIBrainChatResponse,
  AIBrainMessage,
  AIBrainProviderStatus,
  SOPMetrics,
  SOPRun,
  SOPTemplate
} from './types';
import './styles.css';

type ViewKey = 'dashboard' | 'brain' | 'service' | 'crm' | 'knowledge' | 'sop' | 'analytics' | 'settings';

const navItems: Array<{key: ViewKey; label: string; icon: ReactNode}> = [
  {key: 'dashboard', label: '首页', icon: <BarChart3 size={18} />},
  {key: 'brain', label: 'AI大脑', icon: <Bot size={18} />},
  {key: 'service', label: 'AI客服', icon: <Headphones size={18} />},
  {key: 'crm', label: '客户管理', icon: <Users size={18} />},
  {key: 'knowledge', label: '知识库', icon: <BookOpen size={18} />},
  {key: 'sop', label: 'SOP中心', icon: <Workflow size={18} />},
  {key: 'analytics', label: '数据分析', icon: <BarChart3 size={18} />},
  {key: 'settings', label: '设置', icon: <ShieldCheck size={18} />}
];

const emptyMetrics: SOPMetrics = {
  today_consultations: 0,
  ai_auto_replies: 0,
  saved_minutes: 0,
  high_intent_customers: 0,
  pending_followups: 0,
  handoff_count: 0,
  auto_reply_rate: 0,
  avg_response_ms: 0,
  conversion_customers: 0,
  sop_runs_today: 0,
  advice: [],
  recent_runs: []
};

const titleByView: Record<ViewKey, {eyebrow: string; title: string; subtitle: string}> = {
  dashboard: {
    eyebrow: 'AI运营驾驶舱',
    title: '今天的客服自动化闭环',
    subtitle: '从客户消息、AI回复、转人工到CRM沉淀，所有指标都来自后端真实数据。'
  },
  brain: {
    eyebrow: 'AI大脑',
    title: '统一对话与群聊问答',
    subtitle: '接入官方模型、OpenAI-compatible中转或自建网关，先生成可审计回复，再进入自动发送。'
  },
  service: {
    eyebrow: '实时接待',
    title: 'AI客服运行证据',
    subtitle: '查看最近一次客户消息触发后的意图、引用、风险和发送决策。'
  },
  crm: {
    eyebrow: '客户资产',
    title: '客户管理与跟进',
    subtitle: '高意向客户、待跟进任务和会话沉淀集中在这里。'
  },
  knowledge: {
    eyebrow: '知识命中',
    title: '知识库引用与缺口',
    subtitle: '每次AI回复都应能追溯到企业知识库；无答案问题进入人工维护。'
  },
  sop: {
    eyebrow: '流程编排',
    title: 'AI客服 SOP 中心',
    subtitle: '把客服接待、风控、发送和复盘做成可追踪的企业流程。'
  },
  analytics: {
    eyebrow: '经营分析',
    title: '自动化效果',
    subtitle: '关注自动回复率、节省时间、转人工率和成交线索。'
  },
  settings: {
    eyebrow: '安全控制',
    title: '企业与客户端设置',
    subtitle: '自动发送必须可暂停、可追踪、可撤销，并受频率和白名单控制。'
  }
};

function formatDateTime(value: string) {
  if (!value) return '暂无';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  });
}

function runTone(status: SOPRun['status']) {
  if (status === 'completed' || status === 'success') return 'success';
  if (status === 'needs_human') return 'warning';
  if (status === 'failed') return 'danger';
  return 'neutral';
}

function stepTone(status: string) {
  if (status === 'success') return 'success';
  if (status === 'needs_human' || status === 'skipped') return 'warning';
  if (status === 'failed') return 'danger';
  return 'neutral';
}

function intentLabel(score: number) {
  if (score >= 70) return '高意向';
  if (score >= 40) return '中意向';
  return '待判断';
}

function ProgressBar({value}: {value: number}) {
  const safeValue = Math.max(0, Math.min(100, value));
  return (
    <div className="igProgressTrack" aria-label={`${safeValue}%`}>
      <span style={{width: `${safeValue}%`}} />
    </div>
  );
}

function RunList({
  runs,
  selectedId,
  onSelect
}: {
  runs: SOPRun[];
  selectedId: string;
  onSelect: (id: string) => void;
}) {
  if (!runs.length) {
    return <EmptyState title="暂无SOP运行记录" body="完成一次真实客户消息测试后，这里会出现运行证据。" />;
  }
  return (
    <div className="igRunList">
      {runs.map((run) => (
        <button
          type="button"
          key={run.id}
          className={run.id === selectedId ? 'active' : ''}
          onClick={() => onSelect(run.id)}
        >
          <span>
            <strong>{run.customer_name || run.platform || '客户会话'}</strong>
            <small>{run.template_name}</small>
          </span>
          <StatusBadge tone={runTone(run.status)}>{run.status}</StatusBadge>
        </button>
      ))}
    </div>
  );
}

function StepTimeline({run}: {run: SOPRun | undefined}) {
  if (!run?.steps.length) {
    return <EmptyState title="暂无步骤证据" body="收到客户消息并触发SOP后，会显示每一步耗时和结果。" />;
  }
  return (
    <div className="igTimeline">
      {run.steps.map((step, index) => (
        <div className="igTimelineStep" key={step.id}>
          <span className="igTimelineIndex">{index + 1}</span>
          <div>
            <div className="igTimelineTitle">
              <strong>{step.name}</strong>
              <StatusBadge tone={stepTone(step.status)}>{step.status}</StatusBadge>
            </div>
            <p>{step.evidence || '已执行'}</p>
            <small>{step.duration_ms} ms</small>
          </div>
        </div>
      ))}
    </div>
  );
}

function CustomerRows({leads}: {leads: Lead[]}) {
  if (!leads.length) {
    return <EmptyState title="暂无客户" body="新客户消息落库后，会自动出现在客户管理中。" />;
  }
  return (
    <div className="igStackList">
      {leads.slice(0, 8).map((lead) => (
        <article className="igListItem" key={lead.id}>
          <div>
            <strong>{lead.customer_name}</strong>
            <p>{lead.demand}</p>
          </div>
          <div className="igListMeta">
            <StatusBadge tone={lead.intent_level === 'high' ? 'success' : lead.intent_level === 'medium' ? 'warning' : 'neutral'}>
              {lead.intent_level}
            </StatusBadge>
            <small>{lead.stage}</small>
          </div>
        </article>
      ))}
    </div>
  );
}

function FollowUpRows({tasks}: {tasks: FollowUpTask[]}) {
  const openTasks = tasks.filter((task) => task.status === 'open');
  if (!openTasks.length) {
    return <EmptyState title="暂无待跟进任务" body="高意向或转人工客户会沉淀为跟进任务。" />;
  }
  return (
    <div className="igStackList">
      {openTasks.slice(0, 8).map((task) => (
        <article className="igListItem" key={task.id}>
          <div>
            <strong>{task.title}</strong>
            <p>{task.due_at || '未设置截止时间'}</p>
          </div>
          <StatusBadge tone={task.priority === 'high' ? 'danger' : task.priority === 'normal' ? 'warning' : 'neutral'}>
            {task.priority}
          </StatusBadge>
        </article>
      ))}
    </div>
  );
}

export function InternalGrowthApp() {
  const [activeView, setActiveView] = useState<ViewKey>('dashboard');
  const [dashboard, setDashboard] = useState<DashboardSummary | null>(null);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [followUps, setFollowUps] = useState<FollowUpTask[]>([]);
  const [salesAnalyses, setSalesAnalyses] = useState<SalesAnalysis[]>([]);
  const [reports, setReports] = useState<AnalyticsReport[]>([]);
  const [sopTemplates, setSopTemplates] = useState<SOPTemplate[]>([]);
  const [sopRuns, setSopRuns] = useState<SOPRun[]>([]);
  const [sopMetrics, setSopMetrics] = useState<SOPMetrics>(emptyMetrics);
  const [brainProviders, setBrainProviders] = useState<AIBrainProviderStatus[]>([]);
  const [brainProviderId, setBrainProviderId] = useState('default');
  const [brainChannel, setBrainChannel] = useState<AIBrainChannel>('direct');
  const [brainQuestion, setBrainQuestion] = useState('');
  const [brainMessages, setBrainMessages] = useState<AIBrainMessage[]>([]);
  const [brainResult, setBrainResult] = useState<AIBrainChatResponse | null>(null);
  const [brainLoading, setBrainLoading] = useState(false);
  const [selectedTemplateId, setSelectedTemplateId] = useState('');
  const [selectedRunId, setSelectedRunId] = useState('');
  const [fetchError, setFetchError] = useState('');

  const loadData = useCallback(async () => {
    setFetchError('');
    try {
      const [dashboardData, leadData, followUpData, analysisData, reportData, templateData, runData, metricData, providerData] =
        await Promise.all([
          internalGrowthApi.dashboard(),
          internalGrowthApi.leads(),
          internalGrowthApi.followUpTasks(),
          internalGrowthApi.salesAnalyses(),
          internalGrowthApi.reports(),
          internalGrowthApi.sopTemplates(),
          internalGrowthApi.sopRuns(),
          internalGrowthApi.sopMetrics(),
          internalGrowthApi.aiBrainProviders()
        ]);
      setDashboard(dashboardData);
      setLeads(leadData);
      setFollowUps(followUpData);
      setSalesAnalyses(analysisData);
      setReports(reportData);
      setSopTemplates(templateData);
      setSopRuns(runData);
      setSopMetrics(metricData);
      setBrainProviders(providerData);
      setSelectedTemplateId((current) => current || templateData[0]?.id || '');
      setSelectedRunId((current) => current || runData[0]?.id || '');
      setBrainProviderId((current) => current || providerData.find((provider) => provider.configured)?.id || 'default');
    } catch (error) {
      setFetchError(error instanceof Error ? error.message : '数据加载失败');
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const selectedTemplate = useMemo(
    () => sopTemplates.find((template) => template.id === selectedTemplateId) || sopTemplates[0],
    [selectedTemplateId, sopTemplates]
  );
  const selectedRun = useMemo(
    () => sopRuns.find((run) => run.id === selectedRunId) || sopRuns[0],
    [selectedRunId, sopRuns]
  );
  const selectedBrainProvider = useMemo(
    () => brainProviders.find((provider) => provider.id === brainProviderId) || brainProviders[0],
    [brainProviderId, brainProviders]
  );
  const page = titleByView[activeView];
  const knowledgeRuns = sopRuns.filter((run) => run.knowledge_citations.length || run.reason.includes('知识库'));
  const latestAnalysis = salesAnalyses[0];

  const submitBrainQuestion = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const question = brainQuestion.trim();
    if (!question || brainLoading) return;
    const userMessage: AIBrainMessage = {
      role: 'user',
      content: question,
      sender_name: brainChannel === 'internal' ? '运营' : brainChannel === 'direct' ? '我' : '群成员',
      created_at: new Date().toISOString()
    };
    setBrainQuestion('');
    setBrainLoading(true);
    setBrainMessages((current) => [...current, userMessage]);
    try {
      const response = await internalGrowthApi.aiBrainChat({
        question,
        messages: [...brainMessages, userMessage],
        channel: brainChannel,
        provider_id: brainProviderId,
        group_name: brainChannel.includes('group') ? '白名单测试群' : '',
        member_name: userMessage.sender_name,
        merchant_id: null,
        use_knowledge: true,
        allow_auto_answer: false,
        temperature: 0.45
      });
      setBrainResult(response);
      setBrainMessages((current) => [
        ...current,
        {
          role: 'assistant',
          content: response.answer,
          sender_name: response.provider_name,
          created_at: new Date().toISOString()
        }
      ]);
      void loadData();
    } catch (error) {
      setFetchError(error instanceof Error ? error.message : 'AI大脑请求失败');
    } finally {
      setBrainLoading(false);
    }
  };

  const dashboardView = (
    <>
      <div className="igMetrics five">
        <MetricCard label="今日客户咨询" value={sopMetrics.today_consultations} icon={<MessageSquareText size={18} />} />
        <MetricCard label="AI自动回复" value={sopMetrics.ai_auto_replies} icon={<Bot size={18} />} helper={`${sopMetrics.auto_reply_rate}% 自动化`} />
        <MetricCard label="人工节省时间" value={`${sopMetrics.saved_minutes}分`} icon={<TimerReset size={18} />} />
        <MetricCard label="高意向客户" value={sopMetrics.high_intent_customers} icon={<Zap size={18} />} />
        <MetricCard label="待跟进客户" value={sopMetrics.pending_followups} icon={<Clock3 size={18} />} />
      </div>
      <div className="igTwoColumn">
        <Panel title="AI今日经营建议" eyebrow="老板视角">
          <div className="igAdviceList">
            {(sopMetrics.advice.length ? sopMetrics.advice : ['暂无经营建议，等待真实客服数据进入后生成。']).map((item) => (
              <article key={item}>
                <Sparkles size={16} />
                <span>{item}</span>
              </article>
            ))}
          </div>
        </Panel>
        <Panel title="SOP运行状态" eyebrow="今日流程">
          <div className="igMiniMetrics">
            <div>
              <span>今日运行</span>
              <strong>{sopMetrics.sop_runs_today}</strong>
            </div>
            <div>
              <span>转人工</span>
              <strong>{sopMetrics.handoff_count}</strong>
            </div>
            <div>
              <span>平均耗时</span>
              <strong>{sopMetrics.avg_response_ms} ms</strong>
            </div>
          </div>
          <ProgressBar value={sopMetrics.auto_reply_rate} />
        </Panel>
      </div>
      <div className="igTwoColumn">
        <Panel title="最近会话" eyebrow="AI客服">
          <RunList runs={sopRuns.slice(0, 6)} selectedId={selectedRun?.id || ''} onSelect={setSelectedRunId} />
        </Panel>
        <Panel title="待跟进客户" eyebrow="CRM">
          <FollowUpRows tasks={followUps} />
        </Panel>
      </div>
    </>
  );

  const brainView = (
    <div className="igBrainLayout">
      <Panel title="AI大脑对话框" eyebrow="Chat">
        <div className="igBrainToolbar">
          <label>
            <span>模型路由</span>
            <select value={brainProviderId} onChange={(event) => setBrainProviderId(event.target.value)}>
              {brainProviders.map((provider) => (
                <option value={provider.id} key={provider.id}>
                  {provider.name}{provider.configured ? '' : '（未配置）'}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>对话场景</span>
            <select value={brainChannel} onChange={(event) => setBrainChannel(event.target.value as AIBrainChannel)}>
              <option value="direct">内部对话</option>
              <option value="wechat_group">微信群问答</option>
              <option value="douyin_group">抖音群问答</option>
              <option value="website_chat">网页客服</option>
              <option value="internal">运营分析</option>
            </select>
          </label>
        </div>
        <div className="igChatSurface">
          {brainMessages.length ? (
            brainMessages.map((message, index) => (
              <article className={`igChatMessage ${message.role}`} key={`${message.created_at}-${index}`}>
                <small>{message.sender_name || message.role}</small>
                <p>{message.content}</p>
              </article>
            ))
          ) : (
            <EmptyState title="还没有对话" body="可以直接问AI大脑，也可以切到微信群/抖音群模式测试回复口吻。" />
          )}
        </div>
        <form className="igBrainComposer" onSubmit={submitBrainQuestion}>
          <textarea
            value={brainQuestion}
            onChange={(event) => setBrainQuestion(event.target.value)}
            placeholder="输入要问AI大脑的问题，例如：客户在群里问价格和售后政策怎么回？"
          />
          <Button type="submit" disabled={brainLoading || !brainQuestion.trim()}>
            <SendHorizontal size={16} /> {brainLoading ? '生成中' : '发送'}
          </Button>
        </form>
      </Panel>
      <section className="igBrainSide">
        <Panel title="供应商与中转" eyebrow="Gateway">
          {selectedBrainProvider ? (
            <div className="igProviderCard">
              <div>
                <strong>{selectedBrainProvider.name}</strong>
                <StatusBadge tone={selectedBrainProvider.configured ? 'success' : 'warning'}>
                  {selectedBrainProvider.configured ? '已配置' : '未配置'}
                </StatusBadge>
              </div>
              <p>{selectedBrainProvider.cost_note}</p>
              <small>{selectedBrainProvider.safety_note}</small>
              <code>{selectedBrainProvider.env_key}</code>
            </div>
          ) : (
            <EmptyState title="暂无供应商配置" />
          )}
          <div className="igProviderList">
            {brainProviders.map((provider) => (
              <button
                type="button"
                key={provider.id}
                className={provider.id === brainProviderId ? 'active' : ''}
                onClick={() => setBrainProviderId(provider.id)}
              >
                <span>{provider.name}</span>
                <StatusBadge tone={provider.configured ? 'success' : 'neutral'}>{provider.kind}</StatusBadge>
              </button>
            ))}
          </div>
        </Panel>
        <Panel title="本次运行证据" eyebrow="Trace">
          {brainResult ? (
            <div className="igBrainTrace">
              <div>
                <span>模型</span>
                <strong>{brainResult.model || '未调用模型'}</strong>
              </div>
              <div>
                <span>动作</span>
                <StatusBadge tone={brainResult.suggested_action === 'send' ? 'success' : brainResult.suggested_action === 'handoff' ? 'warning' : 'neutral'}>
                  {brainResult.suggested_action}
                </StatusBadge>
              </div>
              <div>
                <span>耗时</span>
                <strong>{brainResult.latency_ms} ms</strong>
              </div>
              <div>
                <span>SOP</span>
                <strong>{brainResult.sop_run_ids.length}</strong>
              </div>
              {brainResult.risk_flags.length > 0 && (
                <div className="igBrainWide">
                  <span>风险</span>
                  <p>{brainResult.risk_flags.join('、')}</p>
                </div>
              )}
              <div className="igBrainWide">
                <span>知识库引用</span>
                {brainResult.citations.length ? (
                  <div className="igChipList">
                    {brainResult.citations.map((item, index) => (
                      <span key={`${String(item.title || item.id)}-${index}`}>{String(item.title || item.id)}</span>
                    ))}
                  </div>
                ) : (
                  <p>未命中引用，客户可见场景会进入人工确认。</p>
                )}
              </div>
            </div>
          ) : (
            <EmptyState title="暂无运行证据" body="发送一次问题后会展示模型、风险、引用和SOP记录。" />
          )}
        </Panel>
      </section>
    </div>
  );

  const serviceView = (
    <div className="igServiceLayout">
      <Panel title="实时会话" eyebrow="会话列表">
        <RunList runs={sopRuns} selectedId={selectedRun?.id || ''} onSelect={setSelectedRunId} />
      </Panel>
      <section className="igServiceMain">
        <Panel
          title={selectedRun?.customer_name || '客户画像'}
          eyebrow={selectedRun?.platform || 'AI客服'}
          action={
            <Button variant="secondary" size="sm" disabled>
              <PauseCircle size={16} /> 人工接管
            </Button>
          }
        >
          {selectedRun ? (
            <div className="igEvidenceGrid">
              <div>
                <span>当前意图</span>
                <strong>{intentLabel(selectedRun.intent_score)}</strong>
                <p>意向评分 {selectedRun.intent_score}</p>
              </div>
              <div>
                <span>推荐动作</span>
                <strong>{selectedRun.action || (selectedRun.status === 'needs_human' ? '转人工' : '继续观察')}</strong>
                <p>{selectedRun.reason || '等待下一条客户消息'}</p>
              </div>
              <div>
                <span>发送结果</span>
                <strong>{selectedRun.status}</strong>
                <p>{formatDateTime(selectedRun.updated_at)}</p>
              </div>
            </div>
          ) : (
            <EmptyState title="暂无客服会话" />
          )}
        </Panel>
        <Panel title="AI回复建议" eyebrow="回复内容">
          {selectedRun?.reply_text ? (
            <div className="igReplyBox">{selectedRun.reply_text}</div>
          ) : (
            <EmptyState title="暂无回复建议" body="有真实客户消息触发AI后，会显示建议内容。" />
          )}
        </Panel>
        <div className="igTwoColumn">
          <Panel title="知识库引用来源" eyebrow="RAG证据">
            {selectedRun?.knowledge_citations.length ? (
              <div className="igChipList">
                {selectedRun.knowledge_citations.map((item) => (
                  <span key={item}>{item}</span>
                ))}
              </div>
            ) : (
              <EmptyState title="未返回引用来源" body="无引用时应进入人工确认，避免编造价格或政策。" />
            )}
          </Panel>
          <Panel title="风险判断" eyebrow="Guardrail">
            {selectedRun?.risk_flags.length ? (
              <div className="igRiskList">
                {selectedRun.risk_flags.map((flag) => (
                  <span key={flag}>
                    <AlertTriangle size={15} /> {flag}
                  </span>
                ))}
              </div>
            ) : (
              <div className="igQuietState">
                <CheckCircle2 size={18} />
                <span>当前记录未发现强制转人工风险</span>
              </div>
            )}
          </Panel>
        </div>
        <Panel title="SOP当前步骤" eyebrow="运行证据">
          <StepTimeline run={selectedRun} />
        </Panel>
      </section>
    </div>
  );

  const crmView = (
    <div className="igTwoColumn">
      <Panel title="客户列表" eyebrow="CRM">
        <CustomerRows leads={leads} />
      </Panel>
      <Panel title="跟进任务" eyebrow="Next Step">
        <FollowUpRows tasks={followUps} />
      </Panel>
      <Panel title="客户洞察" eyebrow="Sales AI" className="igFullPanel">
        {latestAnalysis ? (
          <div className="igInsightBlock">
            <strong>{latestAnalysis.customer_profile}</strong>
            <p>{latestAnalysis.real_need}</p>
            <ProgressBar value={latestAnalysis.purchase_probability} />
            <small>成交概率 {latestAnalysis.purchase_probability}%</small>
          </div>
        ) : (
          <EmptyState title="暂无客户洞察" body="销售分析完成后会在这里展示客户画像和下一步策略。" />
        )}
      </Panel>
    </div>
  );

  const knowledgeView = (
    <div className="igTwoColumn">
      <Panel title="引用命中" eyebrow="知识库">
        {knowledgeRuns.length ? (
          <div className="igStackList">
            {knowledgeRuns.slice(0, 8).map((run) => (
              <article className="igListItem" key={run.id}>
                <div>
                  <strong>{run.customer_name || run.template_name}</strong>
                  <p>{run.knowledge_citations.join('、') || run.reason}</p>
                </div>
                <StatusBadge tone={run.knowledge_citations.length ? 'success' : 'warning'}>
                  {run.knowledge_citations.length ? '有引用' : '需补充'}
                </StatusBadge>
              </article>
            ))}
          </div>
        ) : (
          <EmptyState title="暂无引用记录" body="真实AI回复返回引用来源后，会在这里汇总。" />
        )}
      </Panel>
      <Panel title="无答案问题" eyebrow="维护队列">
        <div className="igAdviceList">
          {sopRuns
            .filter((run) => !run.knowledge_citations.length && run.reason)
            .slice(0, 6)
            .map((run) => (
              <article key={run.id}>
                <Database size={16} />
                <span>{run.reason}</span>
              </article>
            ))}
          {!sopRuns.some((run) => !run.knowledge_citations.length && run.reason) && (
            <article>
              <CheckCircle2 size={16} />
              <span>暂无明确知识库缺口。</span>
            </article>
          )}
        </div>
      </Panel>
    </div>
  );

  const sopView = (
    <div className="igSopLayout">
      <Panel title="SOP模板" eyebrow="Template">
        <div className="igTemplateList">
          {sopTemplates.map((template) => (
            <button
              type="button"
              key={template.id}
              className={template.id === selectedTemplate?.id ? 'active' : ''}
              onClick={() => setSelectedTemplateId(template.id)}
            >
              <strong>{template.name}</strong>
              <small>{template.module}</small>
            </button>
          ))}
          {!sopTemplates.length && <EmptyState title="暂无SOP模板" />}
        </div>
      </Panel>
      <Panel title={selectedTemplate?.name || '流程步骤'} eyebrow="Timeline">
        {selectedTemplate ? (
          <div className="igTimeline">
            {selectedTemplate.steps.map((step, index) => (
              <div className="igTimelineStep" key={step.id}>
                <span className="igTimelineIndex">{index + 1}</span>
                <div>
                  <div className="igTimelineTitle">
                    <strong>{step.name}</strong>
                    <StatusBadge tone={step.requires_human_confirmation ? 'warning' : 'neutral'}>{step.action_type}</StatusBadge>
                  </div>
                  <p>{step.description}</p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState title="请选择SOP模板" />
        )}
      </Panel>
      <Panel title="触发与规则" eyebrow="Guardrail">
        {selectedTemplate ? (
          <div className="igRulePanel">
            <div>
              <span>触发条件</span>
              <strong>{selectedTemplate.trigger}</strong>
            </div>
            <div>
              <span>启用状态</span>
              <StatusBadge tone={selectedTemplate.enabled ? 'success' : 'neutral'}>
                {selectedTemplate.enabled ? '已启用' : '未启用'}
              </StatusBadge>
            </div>
            <h3>转人工规则</h3>
            <ul>
              {selectedTemplate.guardrails.map((rule) => (
                <li key={rule}>{rule}</li>
              ))}
            </ul>
            <h3>频率限制</h3>
            <ul>
              {selectedTemplate.frequency_limits.map((rule) => (
                <li key={rule}>{rule}</li>
              ))}
            </ul>
          </div>
        ) : (
          <EmptyState title="暂无规则" />
        )}
      </Panel>
      <Panel title="最近运行日志" eyebrow="Evidence" className="igFullPanel">
        <RunList runs={sopRuns.slice(0, 8)} selectedId={selectedRun?.id || ''} onSelect={setSelectedRunId} />
      </Panel>
    </div>
  );

  const analyticsView = (
    <>
      <div className="igMetrics">
        <MetricCard label="自动回复率" value={`${sopMetrics.auto_reply_rate}%`} icon={<Bot size={18} />} />
        <MetricCard label="转人工次数" value={sopMetrics.handoff_count} icon={<AlertTriangle size={18} />} />
        <MetricCard label="成交客户" value={sopMetrics.conversion_customers} icon={<CheckCircle2 size={18} />} />
        <MetricCard label="平均响应" value={`${sopMetrics.avg_response_ms}ms`} icon={<Clock3 size={18} />} />
      </div>
      <Panel title="经营复盘" eyebrow="Reports">
        {reports.length ? (
          <div className="igStackList">
            {reports.slice(0, 6).map((report) => (
              <article className="igListItem" key={report.id}>
                <div>
                  <strong>{report.summary}</strong>
                  <p>{report.next_actions.join(' / ')}</p>
                </div>
                <small>{formatDateTime(report.created_at)}</small>
              </article>
            ))}
          </div>
        ) : (
          <EmptyState title="暂无复盘报告" body="生成经营复盘后，这里会展示真实分析结果。" />
        )}
      </Panel>
    </>
  );

  const settingsView = (
    <div className="igSettingsGrid">
      {[
        ['全局紧急暂停', '自动发送前必须检查全局暂停状态'],
        ['会话级人工接管', '指定会话暂停后不得继续自动回复'],
        ['客户端令牌', '令牌需要过期、可撤销，并绑定企业和设备'],
        ['频率限制', '同一会话间隔、每日上限和重复消息限制必须生效'],
        ['企业隔离', '知识库、会话、客户和日志按 Enterprise ID 隔离'],
        ['敏感问题转人工', '退款、投诉、付款、承诺和隐私信息不自动发送']
      ].map(([title, body]) => (
        <Panel title={title} eyebrow="Safety" key={title}>
          <div className="igQuietState">
            <ShieldCheck size={18} />
            <span>{body}</span>
          </div>
        </Panel>
      ))}
    </div>
  );

  const viewMap: Record<ViewKey, ReactNode> = {
    dashboard: dashboardView,
    brain: brainView,
    service: serviceView,
    crm: crmView,
    knowledge: knowledgeView,
    sop: sopView,
    analytics: analyticsView,
    settings: settingsView
  };

  return (
    <div className="igShell">
      <aside className="igSidebar">
        <div className="igBrand">
          <Workflow size={22} />
          <span>AI SOP OS</span>
        </div>
        <nav aria-label="AI客服产品导航">
          {navItems.map((item) => (
            <button
              type="button"
              key={item.key}
              className={activeView === item.key ? 'active' : ''}
              onClick={() => setActiveView(item.key)}
            >
              {item.icon}
              <span>{item.label}</span>
            </button>
          ))}
        </nav>
      </aside>
      <main className="igMain">
        <header className="igTopbar">
          <div>
            <p>{page.eyebrow}</p>
            <h1>{page.title}</h1>
            <span>{page.subtitle}</span>
          </div>
          <div className="igTopbarStatus">
            <StatusBadge tone={dashboard ? 'success' : 'neutral'}>{dashboard ? '后端已连接' : '等待数据'}</StatusBadge>
          </div>
        </header>
        {fetchError && <div className="igError">{fetchError}</div>}
        {viewMap[activeView]}
      </main>
    </div>
  );
}

export default InternalGrowthApp;
