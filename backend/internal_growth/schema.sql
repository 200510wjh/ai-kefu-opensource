CREATE TABLE IF NOT EXISTS demand_signals (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  source_type TEXT NOT NULL,
  source_detail TEXT NOT NULL DEFAULT '',
  industry TEXT NOT NULL DEFAULT '',
  keywords JSONB NOT NULL DEFAULT '[]'::jsonb,
  pain_points TEXT NOT NULL,
  raw_text TEXT NOT NULL DEFAULT '',
  buying_possibility INTEGER NOT NULL DEFAULT 50,
  recommended_action TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS opportunities (
  id TEXT PRIMARY KEY,
  demand_id TEXT NOT NULL REFERENCES demand_signals(id) ON DELETE CASCADE,
  demand_strength INTEGER NOT NULL,
  deal_probability INTEGER NOT NULL,
  average_order_value INTEGER NOT NULL,
  delivery_difficulty INTEGER NOT NULL,
  fit_score INTEGER NOT NULL,
  total_score INTEGER NOT NULL,
  reasoning TEXT NOT NULL,
  recommended_decision TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS content_tasks (
  id TEXT PRIMARY KEY,
  demand_id TEXT NOT NULL REFERENCES demand_signals(id) ON DELETE CASCADE,
  opportunity_id TEXT NOT NULL DEFAULT '',
  platform TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft',
  title TEXT NOT NULL,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  review_note TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS publishing_records (
  id TEXT PRIMARY KEY,
  content_task_id TEXT NOT NULL REFERENCES content_tasks(id) ON DELETE CASCADE,
  platform TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft',
  scheduled_at TEXT NOT NULL DEFAULT '',
  published_at TEXT NOT NULL DEFAULT '',
  views INTEGER NOT NULL DEFAULT 0,
  favorites INTEGER NOT NULL DEFAULT 0,
  consultations INTEGER NOT NULL DEFAULT 0,
  deals INTEGER NOT NULL DEFAULT 0,
  revenue NUMERIC(14,2) NOT NULL DEFAULT 0,
  notes TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS leads (
  id TEXT PRIMARY KEY,
  customer_name TEXT NOT NULL,
  source_platform TEXT NOT NULL DEFAULT 'manual',
  industry TEXT NOT NULL DEFAULT '',
  demand TEXT NOT NULL,
  contact TEXT NOT NULL DEFAULT '',
  intent_level TEXT NOT NULL DEFAULT 'medium',
  stage TEXT NOT NULL DEFAULT 'new',
  next_followup_at TEXT NOT NULL DEFAULT '',
  next_action TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS customer_interactions (
  id TEXT PRIMARY KEY,
  lead_id TEXT NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  channel TEXT NOT NULL DEFAULT 'manual',
  direction TEXT NOT NULL DEFAULT 'note',
  content TEXT NOT NULL,
  ai_summary TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS follow_up_tasks (
  id TEXT PRIMARY KEY,
  lead_id TEXT NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  due_at TEXT NOT NULL DEFAULT '',
  priority TEXT NOT NULL DEFAULT 'normal',
  status TEXT NOT NULL DEFAULT 'open',
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS sales_analyses (
  id TEXT PRIMARY KEY,
  lead_id TEXT NOT NULL DEFAULT '',
  customer_profile TEXT NOT NULL,
  real_need TEXT NOT NULL,
  purchase_probability INTEGER NOT NULL,
  next_strategy TEXT NOT NULL,
  reply_suggestion TEXT NOT NULL,
  risk_flags JSONB NOT NULL DEFAULT '[]'::jsonb,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS analytics_reports (
  id TEXT PRIMARY KEY,
  report_type TEXT NOT NULL DEFAULT 'weekly',
  period_start TEXT NOT NULL DEFAULT '',
  period_end TEXT NOT NULL DEFAULT '',
  summary TEXT NOT NULL,
  best_platforms JSONB NOT NULL DEFAULT '[]'::jsonb,
  best_content JSONB NOT NULL DEFAULT '[]'::jsonb,
  best_services JSONB NOT NULL DEFAULT '[]'::jsonb,
  stop_list JSONB NOT NULL DEFAULT '[]'::jsonb,
  next_actions JSONB NOT NULL DEFAULT '[]'::jsonb,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_workflow_runs (
  id TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  trigger TEXT NOT NULL,
  started_at TIMESTAMPTZ NOT NULL,
  finished_at TEXT NOT NULL DEFAULT '',
  demand_count INTEGER NOT NULL DEFAULT 0,
  opportunity_count INTEGER NOT NULL DEFAULT 0,
  generated_content_tasks INTEGER NOT NULL DEFAULT 0,
  publishing_records_created INTEGER NOT NULL DEFAULT 0,
  followup_tasks_created INTEGER NOT NULL DEFAULT 0,
  needs_human_confirmation BOOLEAN NOT NULL DEFAULT TRUE,
  logs JSONB NOT NULL DEFAULT '[]'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_opportunities_demand_id ON opportunities(demand_id);
CREATE INDEX IF NOT EXISTS idx_content_tasks_demand_id ON content_tasks(demand_id);
CREATE INDEX IF NOT EXISTS idx_publishing_records_task_id ON publishing_records(content_task_id);
CREATE INDEX IF NOT EXISTS idx_leads_stage_intent ON leads(stage, intent_level);
CREATE INDEX IF NOT EXISTS idx_follow_up_tasks_lead_status ON follow_up_tasks(lead_id, status);

