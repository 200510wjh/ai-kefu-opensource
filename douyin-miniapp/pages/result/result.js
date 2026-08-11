const {
  buildFallbackListingDraft,
  buildFallbackManagedOpsPlan,
  buildFallbackProductMediaPack,
  generateImageFromPrompt,
  generateManagedOpsPlan,
  generateProductMediaPack,
  generateListingDraft
} = require('../../utils/api');

function rows(items) {
  return (items || []).map((text, index) => ({
    id: `row-${index}`,
    index: index + 1,
    text
  }));
}

function faqRows(items) {
  return (items || []).map((item, index) => ({
    id: `faq-${index}`,
    question: item.question,
    answer: item.answer
  }));
}

function skuRows(items) {
  return (items || []).map((item, index) => ({
    id: `sku-${index}`,
    sku: item.sku,
    price: item.price,
    stock: item.stock
  }));
}

function buildPackageText(draft) {
  const skuText = (draft.sku_table || [])
    .map((item, index) => `${index + 1}. ${item.sku} / ￥${item.price} / 库存 ${item.stock}`)
    .join('\n');
  const faqText = (draft.customer_faq || [])
    .map((item, index) => `${index + 1}. Q：${item.question}\nA：${item.answer}`)
    .join('\n');

  return [
    `商品：${draft.product_name}`,
    `平台：${draft.platform}`,
    `短标题：${draft.short_title}`,
    '',
    '标题方案：',
    (draft.titles || []).map((item, index) => `${index + 1}. ${item}`).join('\n'),
    '',
    '主图/详情图提示词：',
    (draft.main_image_prompts || []).map((item, index) => `${index + 1}. ${item}`).join('\n'),
    '',
    '详情页结构：',
    (draft.detail_sections || []).map((item, index) => `${index + 1}. ${item}`).join('\n'),
    '',
    'SKU：',
    skuText,
    '',
    '客服FAQ：',
    faqText,
    '',
    '风险检查：',
    (draft.risk_checks || []).map((item, index) => `${index + 1}. ${item}`).join('\n'),
    '',
    `边界：${draft.publish_boundary}`,
    `下一步：${draft.next_action}`
  ].join('\n');
}

function managedPlanText(plan) {
  if (!plan) return '';
  const packages = (plan.price_packages || [])
    .map((item) => `${item.name}：${item.price}\n${item.scope}`)
    .join('\n\n');
  const tasks = (plan.launch_tasks || [])
    .map((item) => `${item.day} ${item.task}\n产出：${item.output}${item.confirmation_required ? '（需确认）' : ''}`)
    .join('\n\n');
  return [
    plan.sellable_offer,
    '',
    '报价套餐：',
    packages,
    '',
    '7天执行计划：',
    tasks,
    '',
    '成交话术：',
    plan.closing_script,
    '',
    '边界：',
    (plan.risk_boundaries || []).map((item, index) => `${index + 1}. ${item}`).join('\n')
  ].join('\n');
}

Page({
  data: {
    draft: null,
    brief: {},
    mediaPack: null,
    managedPlan: null,
    detailRows: [],
    faqRows: [],
    generatedImageUrl: '',
    imageStatus: '',
    promptRows: [],
    riskRows: [],
    skuRows: [],
    titleRows: [],
    packageText: '',
    planText: ''
  },

  hydrate(draft, brief = {}, mediaPack = null, managedPlan = null) {
    this.setData({
      brief,
      draft,
      mediaPack,
      managedPlan,
      detailRows: rows(draft.detail_sections),
      faqRows: faqRows(draft.customer_faq),
      promptRows: rows(draft.main_image_prompts),
      riskRows: rows(draft.risk_checks),
      skuRows: skuRows(draft.sku_table),
      titleRows: rows(draft.titles),
      packageText: buildPackageText(draft),
      planText: managedPlanText(managedPlan)
    });
  },

  onShow() {
    const brief = tt.getStorageSync('ecommerce_brief') || {};
    const mediaPack = tt.getStorageSync('product_media_pack') || null;
    const storedPlan = tt.getStorageSync('managed_ops_plan') || null;
    const draft = (mediaPack && mediaPack.listing_draft) || tt.getStorageSync('ecommerce_draft') || buildFallbackListingDraft(brief);
    const managedPlan = storedPlan || buildFallbackManagedOpsPlan(brief, mediaPack && mediaPack.pack_id);
    this.hydrate(draft, brief, mediaPack, managedPlan);
  },

  copyPackage() {
    tt.setClipboardData({
      data: this.data.packageText,
      success() {
        tt.showToast({ title: '已复制', icon: 'success' });
      },
      fail() {
        tt.showToast({ title: '复制失败', icon: 'none' });
      }
    });
  },

  copyPlan() {
    tt.setClipboardData({
      data: this.data.planText,
      success() {
        tt.showToast({ title: '托管方案已复制', icon: 'success' });
      }
    });
  },

  copyPrompt(event) {
    const index = Number(event.currentTarget.dataset.index || 0);
    const row = this.data.promptRows[index];
    if (!row) return;
    tt.setClipboardData({
      data: row.text,
      success() {
        tt.showToast({ title: '提示词已复制', icon: 'success' });
      }
    });
  },

  async generateImage() {
    const prompt = this.data.promptRows[0] && this.data.promptRows[0].text;
    if (!prompt) {
      tt.showToast({ title: '没有可用提示词', icon: 'none' });
      return;
    }
    this.setData({ imageStatus: '正在请求图片模型...', generatedImageUrl: '' });
    tt.showLoading({ title: '生成主图中' });
    try {
      const result = await generateImageFromPrompt(this.data.brief, prompt);
      if (result.display_url) {
        this.setData({
          generatedImageUrl: result.display_url,
          imageStatus: '真实图片已生成，可以保存或继续换提示词。'
        });
      } else {
        this.setData({
          imageStatus: result.next_action || '图片模型未配置，已保留提示词。'
        });
      }
    } catch (error) {
      this.setData({ imageStatus: '图片接口暂不可用，先复制提示词生成。' });
    } finally {
      tt.hideLoading();
    }
  },

  async regenerate() {
    const brief = tt.getStorageSync('ecommerce_brief') || {};
    tt.showLoading({ title: '重新生成中' });
    try {
      const pack = await generateProductMediaPack(brief);
      const plan = await generateManagedOpsPlan(brief, pack.pack_id);
      tt.setStorageSync('product_media_pack', pack);
      tt.setStorageSync('managed_ops_plan', plan);
      tt.setStorageSync('ecommerce_draft', pack.listing_draft);
      this.hydrate(pack.listing_draft, brief, pack, plan);
    } finally {
      tt.hideLoading();
    }
  },

  goLead() {
    tt.navigateTo({ url: '/pages/lead/lead' });
  }
});
