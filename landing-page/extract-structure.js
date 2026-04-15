const result = {};

// Find all images
const imgs = Array.from(document.querySelectorAll('img')).map(img => ({
  src: img.currentSrc || img.src,
  alt: img.alt || '',
  w: img.naturalWidth,
  h: img.naturalHeight,
  displayW: img.width,
  displayH: img.height,
})).filter(i => i.src && !i.src.startsWith('data:'));
result.images_count = imgs.length;
result.images_top15 = imgs.slice(0, 15);

// Background images on divs (hero, section bgs)
const bgImages = [];
Array.from(document.querySelectorAll('*')).slice(0, 3000).forEach(el => {
  const bi = getComputedStyle(el).backgroundImage;
  if (bi && bi !== 'none' && bi.includes('url(')) {
    const match = bi.match(/url\(["']?([^"')]+)["']?\)/);
    if (match && !match[1].startsWith('data:')) {
      const rect = el.getBoundingClientRect();
      bgImages.push({
        url: match[1],
        tag: el.tagName.toLowerCase(),
        w: Math.round(rect.width),
        h: Math.round(rect.height),
      });
    }
  }
});
result.bg_images_count = bgImages.length;
const uniqueBg = [];
const seen = new Set();
bgImages.forEach(b => { if (!seen.has(b.url)) { seen.add(b.url); uniqueBg.push(b); }});
result.bg_images_unique = uniqueBg.slice(0, 20);

// Section containers — find main sections
const sections = Array.from(document.querySelectorAll('section, [class*="section"], main > div > div')).slice(0, 15);
result.section_containers = sections.map(s => {
  const cs = getComputedStyle(s);
  const rect = s.getBoundingClientRect();
  return {
    tag: s.tagName.toLowerCase(),
    class: (s.className || '').toString().slice(0, 80),
    w: Math.round(rect.width),
    h: Math.round(rect.height),
    pt: cs.paddingTop,
    pb: cs.paddingBottom,
    bg: cs.backgroundColor,
    maxW: cs.maxWidth,
  };
});

// Specific CTA button extraction
const primaryCtaBtn = Array.from(document.querySelectorAll('a, button')).find(el => {
  const t = (el.textContent || '').trim();
  return /Join waitlist now|Join the wai/i.test(t);
});
if (primaryCtaBtn) {
  const cs = getComputedStyle(primaryCtaBtn);
  const rect = primaryCtaBtn.getBoundingClientRect();
  result.cta_button = {
    text: primaryCtaBtn.textContent.trim(),
    tag: primaryCtaBtn.tagName,
    bg: cs.backgroundColor,
    color: cs.color,
    font: cs.fontFamily,
    size: cs.fontSize,
    weight: cs.fontWeight,
    radius: cs.borderRadius,
    padding: cs.padding,
    w: Math.round(rect.width),
    h: Math.round(rect.height),
    boxShadow: cs.boxShadow,
    letterSpacing: cs.letterSpacing,
    transition: cs.transition,
  };
  // inspect inner children for the actual green fill
  const innerEls = primaryCtaBtn.querySelectorAll('*');
  result.cta_inner = Array.from(innerEls).slice(0, 5).map(ch => {
    const cs2 = getComputedStyle(ch);
    return {
      tag: ch.tagName,
      bg: cs2.backgroundColor,
      color: cs2.color,
      radius: cs2.borderRadius,
      padding: cs2.padding,
    };
  });
}

// Find the CSS stylesheets
result.stylesheets = Array.from(document.styleSheets).map(s => ({
  href: s.href || '(inline)',
  rules: (() => { try { return s.cssRules.length; } catch { return 'cross-origin'; } })(),
})).slice(0, 15);

// Google Fonts links
result.font_links = Array.from(document.querySelectorAll('link[href*="fonts.googleapis"], link[href*="framerusercontent"]')).map(l => l.href).slice(0, 10);

// Capture body background colour under different sections by scrollTo
// (Page is single-scroll, so bg is consistent; just verify)
result.body_bg = getComputedStyle(document.body).backgroundColor;
result.html_bg = getComputedStyle(document.documentElement).backgroundColor;

JSON.stringify(result, null, 2);
