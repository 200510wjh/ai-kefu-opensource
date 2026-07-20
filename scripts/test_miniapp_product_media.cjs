const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.resolve(__dirname, '..');
const API_FILE = path.join(ROOT, 'douyin-miniapp', 'utils', 'api.js');

function loadApiWithTt(ttMock) {
  const code = fs.readFileSync(API_FILE, 'utf8');
  const module = { exports: {} };
  const sandbox = {
    module,
    exports: module.exports,
    require,
    console,
    setTimeout,
    clearTimeout,
    Date,
    Error,
    Promise,
    String,
    RegExp,
    decodeURIComponent,
    tt: ttMock
  };
  vm.createContext(sandbox);
  vm.runInContext(code, sandbox, { filename: API_FILE });
  return module.exports;
}

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

async function main() {
  const brief = {
    product_name: 'Test Serum',
    category: 'Beauty',
    platform: 'douyin',
    price: '129.00',
    selling_points: 'Hydrating,Lightweight,Sensitive skin',
    audience: 'Young shoppers',
    visual_style: 'Neon commerce'
  };

  const fallbackApi = loadApiWithTt({
    request(options) {
      options.fail(new Error('network down'));
    },
    getStorageSync() {
      return [];
    },
    setStorageSync() {}
  });
  const fallbackPack = await fallbackApi.generateProductMediaPack(brief);
  assert(fallbackPack.product_name === 'Test Serum', 'fallback keeps product name');
  assert(fallbackPack.listing_draft, 'fallback returns listing draft');
  assert(fallbackPack.video_status === 'needs_ffmpeg', 'fallback marks video as unavailable');
  assert(Array.isArray(fallbackPack.scenes) && fallbackPack.scenes.length === 3, 'fallback returns three scenes');

  const successPayload = {
    pack_id: 'pack-test',
    product_name: 'Test Serum',
    main_image_url: '/artifacts/product_media/test_main.svg',
    detail_image_url: '/artifacts/product_media/test_detail.svg',
    video_preview_url: '/artifacts/product_media/test_preview.html',
    video_url: '/artifacts/product_media/test_video.mp4',
    video_status: 'rendered',
    listing_draft: {
      draft_id: 'draft-test',
      platform: 'Douyin',
      product_name: 'Test Serum',
      titles: ['Test Serum Hydrating'],
      short_title: 'Test Serum',
      selling_points: ['Hydrating'],
      main_image_prompts: ['main image prompt'],
      detail_sections: ['detail section'],
      sku_table: [{ sku: 'Standard', price: '129.00', stock: '100' }],
      listing_fields: { title: 'Test Serum Hydrating' },
      customer_faq: [{ question: 'Suitable?', answer: 'Yes' }],
      risk_checks: ['manual review'],
      publish_boundary: 'save_draft_only',
      next_action: 'review before publish'
    },
    scenes: [
      { title: 'Main', visual: 'main image', asset_url: '/artifacts/product_media/test_main.svg' },
      { title: 'Detail', visual: 'detail image', asset_url: '/artifacts/product_media/test_detail.svg' },
      { title: 'Video', visual: 'video', asset_url: '/artifacts/product_media/test_video.mp4' }
    ],
    test_checklist: ['main', 'detail', 'video'],
    next_action: 'review'
  };
  const successApi = loadApiWithTt({
    request(options) {
      assert(options.url.endsWith('/product-media/pack'), 'calls product-media pack API');
      assert(options.method === 'POST', 'uses POST');
      assert(options.data.render_video === true, 'requests video rendering');
      options.success({ statusCode: 200, data: successPayload });
    },
    getStorageSync() {
      return [];
    },
    setStorageSync() {}
  });
  const pack = await successApi.generateProductMediaPack(brief);
  assert(pack.video_status === 'rendered', 'success returns rendered video');
  assert(pack.main_image_url === 'https://wjhai.cn/merchant-admin/artifacts/product_media/test_main.svg', 'normalizes main image url');
  assert(pack.detail_image_url === 'https://wjhai.cn/merchant-admin/artifacts/product_media/test_detail.svg', 'normalizes detail image url');
  assert(pack.video_url === 'https://wjhai.cn/merchant-admin/artifacts/product_media/test_video.mp4', 'normalizes video url');
  assert(pack.listing_draft.publish_boundary === 'save_draft_only', 'keeps draft-only publish boundary');

  console.log(JSON.stringify({
    status: 'passed',
    fallback_video_status: fallbackPack.video_status,
    success_video_status: pack.video_status,
    main_image_url: pack.main_image_url,
    detail_image_url: pack.detail_image_url,
    video_url: pack.video_url
  }, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
