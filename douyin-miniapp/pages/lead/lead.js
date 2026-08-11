const { createLead } = require('../../utils/api');

const z = decodeURIComponent;

const copy = {
  title: '申请 AI 店铺运营托管',
  subtitle: '提交后进入后台线索池。适合商品上架、客服承接、每周素材更新和代运营试点。',
  business: z('%E5%95%86%E5%AE%B6%2F%E9%A1%B9%E7%9B%AE%E5%90%8D'),
  contact: z('%E8%81%94%E7%B3%BB%E6%96%B9%E5%BC%8F'),
  need: z('%E9%9C%80%E6%B1%82'),
  businessPlaceholder: z('%E4%BE%8B%E5%A6%82%EF%BC%9A%E9%9D%92%E6%8F%90%E8%8C%B6%E9%A5%AE%E4%B8%87%E8%BE%BE%E5%BA%97'),
  contactPlaceholder: z('%E6%89%8B%E6%9C%BA%E5%8F%B7%20%2F%20%E5%BE%AE%E4%BF%A1%E5%8F%B7'),
  needPlaceholder: '例如：想先托管10个商品，上架到抖音小店，配好主图、详情页和客服FAQ',
  submit: '提交托管需求',
  saving: '提交中...',
  required: '请补齐商家名、联系方式和需求',
  submitted: '已提交',
  failed: '提交失败，请稍后再试'
};

Page({
  data: {
    brief: {},
    buttonText: copy.submit,
    copy,
    form: {
      business_name: '',
      contact: '',
      need: ''
    },
    saving: false
  },

  onShow() {
    const brief = tt.getStorageSync('ecommerce_brief') || tt.getStorageSync('brief') || {};
    const plan = tt.getStorageSync('managed_ops_plan') || {};
    const productName = brief.product_name || '';
    const platform = plan.platform || '抖音小店';
    this.setData({
      brief,
      form: {
        business_name: productName || '',
        contact: '',
        need: productName
          ? `想托管 ${productName} 的${platform}商品上架、主图详情、短视频脚本和客服FAQ。方案：${plan.sellable_offer || '先做一批上架素材和7天复盘。'}`
          : '想做商品上架托管，先生成一批主图、详情页、短视频脚本和客服FAQ。'
      }
    });
  },

  onInput(event) {
    const key = event.currentTarget.dataset.key;
    this.setData({
      [`form.${key}`]: event.detail.value
    });
  },

  async submitLead() {
    const { form, brief } = this.data;
    if (!form.business_name || !form.contact || !form.need) {
      tt.showToast({
        title: copy.required,
        icon: 'none'
      });
      return;
    }

    this.setData({
      buttonText: copy.saving,
      saving: true
    });
    try {
      await createLead({
        source: 'douyin',
        industry: brief.category || brief.industry || 'AI店铺运营托管',
        business_name: form.business_name,
        contact: form.contact,
        need: form.need
      });
      tt.showToast({
        title: copy.submitted,
        icon: 'success'
      });
      setTimeout(() => {
        tt.reLaunch({
          url: '/pages/index/index'
        });
      }, 900);
    } catch (error) {
      tt.showToast({
        title: copy.failed,
        icon: 'none'
      });
    } finally {
      this.setData({
        buttonText: copy.submit,
        saving: false
      });
    }
  }
});
