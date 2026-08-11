import React, { useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { BarChart3, Boxes, Clapperboard, FileText, Globe2, Image, Layers3, LogIn, UploadCloud, WandSparkles } from 'lucide-react';
import './styles.css';

type Locale = 'zh-CN' | 'en-US';

const messages = {
  'zh-CN': {
    title: '企业级商品素材工厂',
    subtitle: '一张图进来，自动生成主图、详情页、文案、短视频与多平台版本。',
    login: '企业登录',
    product: '商品管理',
    upload: '图片上传',
    generate: '一键生成素材包',
    history: '历史记录 / 版本',
    stats: '统计',
    video: '15s / 30s / 60s 短视频',
    workflow: 'Workflow 自动化',
    engine: 'AI Engine 统一入口'
  },
  'en-US': {
    title: 'Enterprise Product Material Factory',
    subtitle: 'Upload one product image and generate listing assets, copy, videos, and platform variants.',
    login: 'Enterprise Login',
    product: 'Product Management',
    upload: 'Image Upload',
    generate: 'Generate Full Pack',
    history: 'History / Versions',
    stats: 'Analytics',
    video: '15s / 30s / 60s Videos',
    workflow: 'Workflow Automation',
    engine: 'Unified AI Engine'
  }
};

const stages = [
  { icon: UploadCloud, key: 'upload', body: 'Source image, product data, brand constraints' },
  { icon: Image, key: 'product', body: 'Main images and detail-page visual structure' },
  { icon: FileText, key: 'engine', body: 'Titles, descriptions, selling points, platform copy' },
  { icon: Clapperboard, key: 'video', body: 'Subtitles, voiceover and BGM interface-ready renders' },
  { icon: Layers3, key: 'history', body: 'Versioned assets, rollback, export packages' }
] as const;

function App() {
  const [locale, setLocale] = useState<Locale>('zh-CN');
  const t = messages[locale];
  const mockStats = useMemo(() => [
    ['Products', '128'],
    ['Assets', '2,846'],
    ['Workflow Runs', '931'],
    ['Exports', '417']
  ], []);

  return (
    <main>
      <header className="topbar">
        <div className="brand">
          <Boxes size={24} />
          <span>Material Factory</span>
        </div>
        <button className="locale" onClick={() => setLocale(locale === 'zh-CN' ? 'en-US' : 'zh-CN')}>
          <Globe2 size={18} />
          {locale}
        </button>
      </header>

      <section className="hero">
        <div className="heroText">
          <p className="eyebrow">V1 Enterprise Workflow</p>
          <h1>{t.title}</h1>
          <p>{t.subtitle}</p>
          <div className="actions">
            <button><LogIn size={18} />{t.login}</button>
            <button className="secondary"><WandSparkles size={18} />{t.generate}</button>
          </div>
        </div>
        <div className="pipeline" aria-label="workflow pipeline">
          {stages.map((stage) => {
            const Icon = stage.icon;
            return (
              <article key={stage.key}>
                <Icon size={22} />
                <h2>{t[stage.key]}</h2>
                <p>{stage.body}</p>
              </article>
            );
          })}
        </div>
      </section>

      <section className="workspace">
        <div className="panel productPanel">
          <div className="sectionHeader">
            <span>{t.product}</span>
            <button>{t.upload}</button>
          </div>
          <div className="productPreview">
            <div className="imageSlot">PRODUCT IMAGE</div>
            <div>
              <h3>Chiffon Floral Dress</h3>
              <p>V-neckline, waist tie, transparent sleeves, premium editorial campaign.</p>
              <div className="chips">
                <span>Douyin</span>
                <span>Taobao</span>
                <span>Amazon</span>
              </div>
            </div>
          </div>
        </div>
        <div className="panel">
          <div className="sectionHeader">
            <span>{t.stats}</span>
            <BarChart3 size={18} />
          </div>
          <div className="stats">
            {mockStats.map(([label, value]) => (
              <div key={label}>
                <strong>{value}</strong>
                <span>{label}</span>
              </div>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}

createRoot(document.getElementById('root')!).render(<App />);
