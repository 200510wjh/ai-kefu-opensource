const { generateManagedOpsPlan, generateProductMediaPack } = require('../../utils/api');

const platformOptions = [
  { label: '抖音小店', value: 'douyin' },
  { label: '淘宝', value: 'taobao' },
  { label: '拼多多', value: 'pdd' },
  { label: '闲鱼', value: 'xianyu' },
  { label: '小红书店铺', value: 'xiaohongshu' }
];

const styleOptions = ['蓝紫霓虹科技风', '高端极简白底', '直播间爆款风', '小红书种草风'];

const presets = [
  {
    id: 'serum',
    name: '美妆精华',
    tag: '主图详情',
    brief: {
      product_name: '补水保湿精华液',
      category: '美妆护肤',
      platform: 'douyin',
      price: '129.00',
      sku_options: '30ml,50ml,两瓶装',
      stock: '300',
      selling_points: '深层补水,清爽不粘,敏感肌可用,熬夜急救',
      audience: '18-35岁护肤用户',
      shipping: '48小时内发货，偏远地区除外',
      after_sales: '支持7天无理由，拆封影响二次销售除外',
      visual_style: '蓝紫霓虹科技风'
    }
  },
  {
    id: 'snack',
    name: '电商零食',
    tag: '批量上新',
    brief: {
      product_name: '冻干草莓脆',
      category: '休闲零食',
      platform: 'douyin',
      price: '39.90',
      sku_options: '3袋装,6袋装,家庭分享装',
      stock: '800',
      selling_points: '酸甜酥脆,独立小包装,办公室零食,孩子也爱吃',
      audience: '办公室零食和宝妈用户',
      shipping: '24小时内打包发货',
      after_sales: '破损包赔，食品类不支持无理由退换',
      visual_style: '直播间爆款风'
    }
  },
  {
    id: 'case',
    name: '手机壳',
    tag: '多SKU',
    brief: {
      product_name: '透明防摔手机壳',
      category: '数码配件',
      platform: 'pdd',
      price: '19.90',
      sku_options: 'iPhone 15,iPhone 15 Pro,华为Mate 60,小米14',
      stock: '1200',
      selling_points: '四角防摔,高清透明,不易发黄,镜头全包',
      audience: '手机配件刚需用户',
      shipping: '当日16点前下单当天发货',
      after_sales: '质量问题包退换',
      visual_style: '高端极简白底'
    }
  }
];

function decoratePresets(activeId) {
  return presets.map((item) => ({
    ...item,
    activeClass: item.id === activeId ? 'active' : ''
  }));
}

function currentPlatformLabel(value) {
  const item = platformOptions.find((option) => option.value === value);
  return item ? item.label : platformOptions[0].label;
}

Page({
  data: {
    activePreset: 'serum',
    brief: presets[0].brief,
    flow: ['1 填商品资料', '2 生成上架包', '3 留资托管'],
    loading: false,
    platformIndex: 0,
    platformLabel: '抖音小店',
    platformOptions,
    presets: decoratePresets('serum'),
    styleIndex: 0,
    styleOptions
  },

  onShow() {
    const storedBrief = tt.getStorageSync('ecommerce_brief');
    if (!storedBrief || !storedBrief.product_name) return;
    const platformIndex = platformOptions.findIndex((item) => item.value === storedBrief.platform);
    const styleIndex = styleOptions.findIndex((item) => item === storedBrief.visual_style);
    this.setData({
      activePreset: '',
      brief: storedBrief,
      platformIndex: platformIndex >= 0 ? platformIndex : 0,
      platformLabel: currentPlatformLabel(storedBrief.platform),
      presets: decoratePresets(''),
      styleIndex: styleIndex >= 0 ? styleIndex : 0
    });
  },

  onInput(event) {
    const key = event.currentTarget.dataset.key;
    this.setData({
      [`brief.${key}`]: event.detail.value
    });
  },

  choosePreset(event) {
    const id = event.currentTarget.dataset.id;
    const preset = presets.find((item) => item.id === id);
    if (!preset) return;
    const platformIndex = platformOptions.findIndex((item) => item.value === preset.brief.platform);
    const styleIndex = styleOptions.findIndex((item) => item === preset.brief.visual_style);
    this.setData({
      activePreset: id,
      brief: preset.brief,
      platformIndex: platformIndex >= 0 ? platformIndex : 0,
      platformLabel: currentPlatformLabel(preset.brief.platform),
      presets: decoratePresets(id),
      styleIndex: styleIndex >= 0 ? styleIndex : 0
    });
  },

  onPlatformChange(event) {
    const index = Number(event.detail.value || 0);
    const option = platformOptions[index] || platformOptions[0];
    this.setData({
      platformIndex: index,
      platformLabel: option.label,
      'brief.platform': option.value
    });
  },

  onStyleChange(event) {
    const index = Number(event.detail.value || 0);
    const style = styleOptions[index] || styleOptions[0];
    this.setData({
      styleIndex: index,
      'brief.visual_style': style
    });
  },

  async generate() {
    const brief = this.data.brief;
    if (!brief.product_name || !brief.selling_points || !brief.price) {
      tt.showToast({
        title: '先填商品名、价格和卖点',
        icon: 'none'
      });
      return;
    }

    this.setData({ loading: true });
    tt.showLoading({ title: '正在生成' });
    try {
      const pack = await generateProductMediaPack(brief);
      const plan = await generateManagedOpsPlan(brief, pack.pack_id);
      tt.setStorageSync('ecommerce_brief', brief);
      tt.setStorageSync('product_media_pack', pack);
      tt.setStorageSync('managed_ops_plan', plan);
      tt.setStorageSync('ecommerce_draft', pack.listing_draft);
      tt.navigateTo({ url: '/pages/result/result?mode=ecommerce' });
    } catch (error) {
      tt.showToast({
        title: '生成失败，稍后再试',
        icon: 'none'
      });
    } finally {
      tt.hideLoading();
      this.setData({ loading: false });
    }
  },

  goCases() {
    tt.navigateTo({ url: '/pages/cases/cases' });
  }
});
