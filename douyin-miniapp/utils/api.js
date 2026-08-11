const API_BASE = 'https://wjhai.cn/merchant-admin/api';
const API_ORIGIN = 'https://wjhai.cn/merchant-admin';
const z = decodeURIComponent;

function pointList(brief) {
  return String(brief && brief.selling_points ? brief.selling_points : z('%E6%A0%B8%E5%BF%83%E5%8D%96%E7%82%B9'))
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

function buildFallbackScripts(brief = {}) {
  const product = brief.product_name || z('%E6%9C%AC%E5%9C%B0%E5%95%86%E5%AE%B6%E5%A2%9E%E9%95%BF%E6%96%B9%E6%A1%88');
  const industry = brief.industry || z('%E5%95%86%E5%AE%B6');
  const cta = brief.call_to_action || z('%E7%A7%81%E4%BF%A1%E9%A2%84%E7%BA%A6%E4%BD%93%E9%AA%8C');
  const points = pointList(brief);
  const firstPoint = points[0] || z('%E6%A0%B8%E5%BF%83%E5%8D%96%E7%82%B9');

  return [
    {
      id: 'mini-fallback-1',
      name: z('%E5%90%8C%E5%9F%8E%E8%8E%B7%E5%AE%A2%E7%89%88'),
      hook: z('%E5%88%AB%E5%85%88%E5%BF%99%E7%9D%80%E5%89%AA%E8%A7%86%E9%A2%91%EF%BC%8C%E5%85%88%E6%8A%8A%E8%BF%99%E6%9D%A1%E6%8A%96%E9%9F%B3%E6%96%B9%E6%A1%88%E8%B7%91%E9%80%9A'),
      voiceover: `${industry}${z('%E8%80%81%E6%9D%BF%E5%8F%AA%E8%A6%81%E5%8F%91%E4%B8%80%E5%8F%A5%E9%9C%80%E6%B1%82%EF%BC%8C%E7%B3%BB%E7%BB%9F%E5%85%88%E7%BB%99')} ${product} ${z('%E7%94%9F%E6%88%90%E8%84%9A%E6%9C%AC%E3%80%81%E5%88%86%E9%95%9C%E3%80%81%E5%AE%A2%E6%9C%8D%E8%AF%9D%E6%9C%AF%E5%92%8C%E7%95%99%E8%B5%84%E9%93%BE%E8%B7%AF%E3%80%82')}`,
      estimated_cost: 0,
      scenes: [
        {
          id: 'scene-1',
          title: z('%E8%80%81%E6%9D%BF%E5%8F%91%E9%9C%80%E6%B1%82'),
          caption: `${z('%E6%88%91%E6%83%B3%E6%8E%A8')} ${product}`,
          visual: z('%E9%97%A8%E5%BA%97%E7%85%A7%E7%89%87%E3%80%81%E5%95%86%E5%93%81%E5%9B%BE%E3%80%81%E8%81%8A%E5%A4%A9%E9%9C%80%E6%B1%82%E5%90%8C%E6%97%B6%E5%87%BA%E7%8E%B0'),
          duration: 3.2,
          accent: '#22d3ee'
        },
        {
          id: 'scene-2',
          title: z('%E7%B3%BB%E7%BB%9F%E5%87%BA%E6%96%B9%E6%A1%88'),
          caption: `${z('%E4%B8%BB%E6%89%93')} ${firstPoint}`,
          visual: z('%E8%84%9A%E6%9C%AC%E3%80%81%E5%88%86%E9%95%9C%E3%80%81%E4%B8%BB%E5%9B%BEprompt%E3%80%81%E5%AE%A2%E6%9C%8D%E8%AF%9D%E6%9C%AF%E5%9B%9B%E5%BC%A0%E5%8D%A1%E7%89%87%E5%BC%B9%E5%87%BA'),
          duration: 3.8,
          accent: '#facc15'
        },
        {
          id: 'scene-3',
          title: z('%E7%BA%BF%E7%B4%A2%E6%89%BF%E6%8E%A5'),
          caption: cta,
          visual: z('%E7%A7%81%E4%BF%A1%E3%80%81%E8%A1%A8%E5%8D%95%E3%80%81%E9%A2%84%E7%BA%A6%E5%85%A5%E5%BA%93%EF%BC%8C%E5%AE%A2%E6%9C%8D%E8%AF%9D%E6%9C%AF%E8%B7%9F%E8%BF%9B'),
          duration: 3.8,
          accent: '#fb7185'
        }
      ]
    }
  ];
}

function request(path, options = {}) {
  const url = API_BASE + path;
  return new Promise((resolve, reject) => {
    tt.request({
      url,
      method: options.method || 'GET',
      data: options.data || {},
      header: {
        'content-type': 'application/json'
      },
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data);
          return;
        }
        reject(new Error(`request failed: ${res.statusCode}`));
      },
      fail(error) {
        reject(error);
      }
    });
  });
}

function generateScripts(brief) {
  return request('/scripts', {
    method: 'POST',
    data: brief
  }).catch(() => buildFallbackScripts(brief));
}

function splitPoints(text) {
  return String(text || '核心卖点')
    .split(/[,，/、\n]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function buildFallbackListingDraft(brief = {}) {
  const product = brief.product_name || '补水保湿精华液';
  const category = brief.category || '美妆护肤';
  const platform = {
    douyin: '抖音小店',
    taobao: '淘宝',
    pdd: '拼多多',
    xianyu: '闲鱼',
    xiaohongshu: '小红书店铺'
  }[brief.platform || 'douyin'];
  const points = splitPoints(brief.selling_points || '高保湿,清爽不粘,敏感肌可用');
  const primary = points[0] || '高转化卖点';
  const secondary = points[1] || '提升下单转化';
  const price = brief.price || '129.00';
  const style = brief.visual_style || '蓝紫霓虹科技风';

  return {
    draft_id: `local-${Date.now()}`,
    platform,
    product_name: product,
    titles: [
      `${product} ${primary} ${category}`,
      `${product} ${secondary} 现货可拍`,
      `${brief.audience || '抖音用户'}适用 ${product}`
    ],
    short_title: `${product} ${primary}`.slice(0, 30),
    selling_points: points,
    main_image_prompts: [
      `竖版9:16电商主图，${style}，商品为${product}，主体居中，蓝紫发光商业海报质感，大标题写“${primary}”，副标题写“￥${price}”，包含商品卡片、价格标签、AI生成按钮，高清，适合抖音封面。`,
      `商品详情页长图首屏，${style}，${product}真实产品展示，包含卖点模块：${points.slice(0, 3).join(' / ')}，视觉高级、干净、转化感强，移动端安全边距。`,
      `多平台上架宣传图，展示上传商品资料、AI生成图片、生成标题卖点、保存平台草稿四步流程，风格参考赛博霓虹电商SaaS后台。`
    ],
    detail_sections: [
      `首屏：${product} + ${primary} + 价格/活动入口`,
      `痛点：展示${brief.audience || '目标用户'}为什么需要这个商品`,
      `卖点：${points.join(' / ')}`,
      `规格：${brief.sku_options || '标准款'}，价格${price}，库存${brief.stock || '待确认'}`,
      '收口：售后承诺、评价截图、下单提醒，发布前人工确认'
    ],
    sku_table: String(brief.sku_options || '标准款').split(/[,，/]+/).filter(Boolean).map((sku) => ({
      sku: sku.trim(),
      price,
      stock: brief.stock || '待确认'
    })),
    listing_fields: {
      platform,
      category,
      title: `${product} ${primary} ${category}`,
      short_title: `${product} ${primary}`.slice(0, 30),
      price,
      shipping: brief.shipping || '按店铺实际承诺填写',
      after_sales: brief.after_sales || '按平台售后规则执行'
    },
    customer_faq: [
      { question: '这个适合我吗？', answer: `如果你主要关注${primary}，这款${product}可以优先看。` },
      { question: '多久发货？', answer: brief.shipping || '按店铺实际承诺填写。' },
      { question: '售后怎么处理？', answer: brief.after_sales || '按平台售后规则执行。' }
    ],
    risk_checks: [
      '只生成商品草稿，不自动发布。',
      '价格、库存、售后、发货承诺必须由商家最终确认。',
      '避免第一、最强、永久有效、100%成交等绝对化承诺。',
      '食品、美妆、医疗、功效类商品需要补齐平台资质。'
    ],
    publish_boundary: 'save_draft_only',
    next_action: '复制主图提示词生成图片，再把字段填入平台草稿，最终发布前人工确认。'
  };
}

function generateListingDraft(brief) {
  return request('/ecommerce/listing-draft', {
    method: 'POST',
    data: brief
  }).catch(() => buildFallbackListingDraft(brief));
}

function normalizeAssetUrl(url) {
  if (!url) return '';
  if (/^https?:\/\//.test(url)) return url;
  return API_ORIGIN + url;
}

function generateImageFromPrompt(brief, prompt) {
  const payload = {
    brief: {
      industry: brief.category || '电商商品',
      product_name: brief.product_name || '商品',
      selling_points: brief.selling_points || '核心卖点',
      platform: '抖音',
      video_type: 'ecommerce',
      segment: 'ecommerce_seller',
      generation_kind: 'product_image',
      style: brief.visual_style || 'clean',
      budget_mode: 'balanced',
      audience: brief.audience || '电商用户',
      call_to_action: '保存上架草稿'
    },
    image_kind: 'main_image',
    prompt
  };
  return request('/images/generate', {
    method: 'POST',
    data: payload
  }).then((result) => ({
    ...result,
    display_url: normalizeAssetUrl(result.image_url || result.artifact_url)
  }));
}

function buildFallbackProductMediaPack(brief = {}) {
  const draft = buildFallbackListingDraft(brief);
  return {
    pack_id: `local-pack-${Date.now()}`,
    product_name: draft.product_name,
    main_image_url: '',
    detail_image_url: '',
    video_preview_url: '',
    video_url: '',
    video_status: 'needs_ffmpeg',
    listing_draft: draft,
    scenes: [
      { title: '商品主图', visual: '商品主体居中，价格和核心卖点大字展示', asset_url: '' },
      { title: '详情图', visual: '卖点拆解、适用人群、发布前确认', asset_url: '' },
      { title: '商品短视频', visual: '主图 -> 详情卖点 -> 上架草稿三段式', asset_url: '' }
    ],
    test_checklist: [
      '主图和详情图需要服务器接口返回。',
      '视频需要服务器渲染运行时。',
      '上架草稿必须人工确认发布。'
    ],
    next_action: '当前使用本地兜底草稿；请检查服务器接口或网络。'
  };
}

function generateProductMediaPack(brief) {
  return request('/product-media/pack', {
    method: 'POST',
    data: {
      product_name: brief.product_name,
      category: brief.category || '电商商品',
      platform: brief.platform || 'douyin',
      price: brief.price || '129.00',
      selling_points: brief.selling_points,
      audience: brief.audience || '电商用户',
      visual_style: brief.visual_style || '蓝紫霓虹科技风',
      call_to_action: '保存上架草稿',
      product_image_data_url: brief.product_image_data_url || null,
      render_video: true
    }
  }).then((pack) => ({
    ...pack,
    main_image_url: normalizeAssetUrl(pack.main_image_url),
    detail_image_url: normalizeAssetUrl(pack.detail_image_url),
    video_preview_url: normalizeAssetUrl(pack.video_preview_url),
    video_url: normalizeAssetUrl(pack.video_url)
  })).catch(() => buildFallbackProductMediaPack(brief));
}

function buildFallbackManagedOpsPlan(brief = {}, packId = '') {
  const product = brief.product_name || '补水保湿精华液';
  const category = brief.category || '电商商品';
  const platform = {
    douyin: '抖音小店',
    taobao: '淘宝',
    pdd: '拼多多',
    xianyu: '闲鱼',
    xiaohongshu: '小红书店铺'
  }[brief.platform || 'douyin'];
  const points = splitPoints(brief.selling_points || '高转化卖点,客服承接,快速上架');
  const primary = points[0] || '高转化卖点';
  return {
    plan_id: `miniapp-plan-${Date.now()}`,
    source: 'miniapp_template',
    pack_id: packId,
    product_name: product,
    platform,
    positioning: `面向${brief.audience || '电商用户'}，主打“${primary}”的${category}上架和客服承接方案。`,
    sellable_offer: 'AI 店铺运营增长包：商家给商品资料，系统生成上架素材、平台草稿、客服话术和7天复盘计划，人工确认后发布。',
    price_packages: [
      { name: '启动包', price: '299-599/批', scope: '10个商品上架素材、标题卖点、客服 FAQ。' },
      { name: '增长包', price: '999-1999/月', scope: '每周素材更新、客服话术优化、线索复盘。' },
      { name: '托管包', price: '3000+/月', scope: '商品上新、素材制作、客服承接、周报复盘。' }
    ],
    launch_tasks: [
      { day: 'D1', owner: 'merchant', task: '提交商品资料、价格库存和发货规则', output: '商品档案', confirmation_required: true },
      { day: 'D1', owner: 'ai', task: '生成标题、卖点、主图、详情图和短视频草稿', output: '上架素材包', confirmation_required: false },
      { day: 'D2', owner: 'operator', task: `创建${platform}商品草稿`, output: '平台草稿', confirmation_required: true },
      { day: 'D3', owner: 'operator', task: '导入客服 FAQ 和人工接管词', output: '客服承接 SOP', confirmation_required: true },
      { day: 'D4-D7', owner: 'ai', task: '复盘曝光、点击、咨询和转化', output: '优化建议', confirmation_required: false }
    ],
    publishing_queue: [
      { status: 'draft_ready', item: `${product} 标题/短标题/卖点`, next_operator_action: '复制到平台草稿并检查类目、品牌、规格。' },
      { status: 'asset_ready', item: `${product} 主图/详情图/短视频`, next_operator_action: '人工确认不侵权、不虚假宣传，再上传素材。' },
      { status: 'service_ready', item: `${product} 客服 FAQ`, next_operator_action: '导入知识库，先用草稿模式辅助回复。' }
    ],
    customer_service_flow: [
      'AI 判断客户意向、预算、疑虑和是否需要人工接管。',
      '常规问题生成候选回复，客服人工确认后发送。',
      '高意向客户进入线索表，按2小时、24小时、3天跟进。'
    ],
    risk_boundaries: [
      '只创建草稿和候选回复，不自动发布、改价、退款或发货。',
      '价格、库存、发货、售后、资质必须由商家最终确认。',
      '禁止盗图铺货、虚假评价、刷单和无授权私信骚扰。'
    ],
    closing_script: `老板，您不用先招运营。先给我${product}这类商品资料，我用 AI 帮您做一批${platform}上架素材、客服话术和7天跟进复盘。发布前您确认价格库存和合规内容，跑通后再按月托管。`,
    next_action: '先收一单启动包，跑通后升级增长包。'
  };
}

function generateManagedOpsPlan(brief, packId = '') {
  return Promise.resolve(buildFallbackManagedOpsPlan(brief, packId));
}

function createLead(lead) {
  return request('/leads', {
    method: 'POST',
    data: lead
  });
}

module.exports = {
  buildFallbackScripts,
  buildFallbackListingDraft,
  buildFallbackManagedOpsPlan,
  buildFallbackProductMediaPack,
  createLead,
  fallbackScripts: buildFallbackScripts(),
  generateImageFromPrompt,
  generateListingDraft,
  generateManagedOpsPlan,
  generateProductMediaPack,
  generateScripts
};
