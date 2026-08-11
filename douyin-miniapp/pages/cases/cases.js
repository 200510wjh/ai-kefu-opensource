const z = decodeURIComponent;

const copy = {
  title: '先用 3 个商品案例跑通托管方案',
  subtitle: '套用后会回到首页，直接生成商品上架包、客服 FAQ 和7天运营托管报价。',
  useCase: '套用这个商品'
};

const cases = [
  {
    id: 'serum',
    name: '美妆精华上新',
    desc: '适合抖音小店美妆商家，生成主图、详情页、客服 FAQ 和发布前风险检查。',
    tags: ['美妆', '抖音小店', '客服承接'],
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
    name: '电商零食批量上新',
    desc: '适合食品零食商家，一次生成多 SKU 上架草稿、卖点结构和售后边界。',
    tags: ['零食', '批量上新', '多SKU'],
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
    name: '手机壳多规格铺货',
    desc: '适合多型号配件商家，生成规格表、标题组合、客服问答和发布前检查。',
    tags: ['数码配件', '多规格', '拼多多'],
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

Page({
  data: {
    cases,
    copy
  },

  useCase(event) {
    const id = event.currentTarget.dataset.id;
    const item = cases.find((candidate) => candidate.id === id);
    if (!item) return;
    tt.setStorageSync('ecommerce_brief', item.brief);
    tt.reLaunch({
      url: '/pages/index/index'
    });
  }
});
