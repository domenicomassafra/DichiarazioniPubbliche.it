import assert from "node:assert/strict";

// The owner-selected Source layout puts the approved excerpt next to the media,
// with selectable statements below both. Test actual browser geometry and state.
export async function assertSourceReader(cdp, variant) {
  const layout = await cdp.evaluate(`(() => {
    const box = (selector) => document.querySelector(selector)?.getBoundingClientRect().toJSON();
    return { media: box('.source-story__media'), excerpt: box('.source-story__excerpts'), claims: box('.source-story__claims') };
  })()`);
  assert(layout.media && layout.excerpt && layout.claims, `content ${variant}: editorial panels missing`);
  if (variant === "desktop") {
    assert(layout.excerpt.left >= layout.media.right - 1, "content: transcript must sit beside the media");
    assert(Math.abs(layout.excerpt.top - layout.media.top) < 2, "content: media and transcript must align");
  } else {
    assert(layout.excerpt.top >= layout.media.bottom - 1, "content: transcript must follow media on mobile");
  }
  assert(layout.claims.top >= Math.max(layout.media.bottom, layout.excerpt.bottom) - 1,
    `content ${variant}: statement list must follow the source context`);
  const selectedId = await cdp.evaluate("document.querySelector('.source-story__claim button')?.dataset.contentSelect ?? ''");
  assert(selectedId, "content: no selectable approved statement");
  await cdp.evaluate("document.querySelector('.source-story__claim button').click()");
  const selection = await cdp.evaluate(`(() => ({
    current: document.querySelector('.source-story__claim button[aria-current="true"]')?.dataset.contentSelect,
    detail: document.querySelector('[data-content-detail]:not([hidden])')?.dataset.contentDetail,
    url: new URLSearchParams(location.search).get('momento')
  }))()`);
  assert.deepEqual(selection, { current: selectedId, detail: selectedId, url: selectedId },
    `content ${variant}: selection does not reveal the source-linked excerpt`);
}
