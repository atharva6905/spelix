const h1 = document.querySelector('h1');
const h2s = Array.from(document.querySelectorAll('h2'));
const ctas = Array.from(document.querySelectorAll('a,button')).filter(el => /Join waitlist|Join the/i.test(el.textContent || ''));
const navLinks = Array.from(document.querySelectorAll('nav a')).slice(0, 6);
const body = document.body;
const html = document.documentElement;

function tok(el, label) {
  if (!el) return { label, missing: true };
  const cs = getComputedStyle(el);
  return {
    label,
    tag: el.tagName,
    text: (el.textContent || '').trim().slice(0, 80),
    font: cs.fontFamily,
    size: cs.fontSize,
    weight: cs.fontWeight,
    lh: cs.lineHeight,
    letterSpacing: cs.letterSpacing,
    color: cs.color,
    bg: cs.backgroundColor,
    bgImage: cs.backgroundImage.slice(0, 60),
    borderRadius: cs.borderRadius,
    padding: cs.padding,
    display: cs.display,
  };
}

const allEls = Array.from(document.querySelectorAll('*'));
const colors = new Set();
const bgs = new Set();
const fonts = new Set();
const radii = new Set();
allEls.slice(0, 2000).forEach(el => {
  const cs = getComputedStyle(el);
  if (cs.color) colors.add(cs.color);
  if (cs.backgroundColor && cs.backgroundColor !== 'rgba(0, 0, 0, 0)') bgs.add(cs.backgroundColor);
  if (cs.fontFamily) fonts.add(cs.fontFamily);
  if (cs.borderRadius && cs.borderRadius !== '0px') radii.add(cs.borderRadius);
});

const greenBtn = ctas.find(c => {
  const bg = getComputedStyle(c).backgroundColor;
  return bg && bg !== 'rgba(0, 0, 0, 0)';
}) || ctas[0];

const sectionLabels = Array.from(document.querySelectorAll('*')).filter(el => {
  const t = (el.textContent || '').trim();
  return ['Introduction','AI in Action','Why It Works','Testimonials','FAQ'].includes(t) && el.children.length === 0;
}).slice(0, 5);

const result = {
  page: { w: html.scrollWidth, h: html.scrollHeight, title: document.title, bodyBg: getComputedStyle(body).backgroundColor, bodyFont: getComputedStyle(body).fontFamily },
  h1: tok(h1, 'h1'),
  h2_sample: h2s.slice(0, 4).map((el, i) => tok(el, `h2_${i}`)),
  cta_primary: tok(greenBtn, 'cta_primary'),
  nav_link_sample: navLinks.slice(0, 2).map((el, i) => tok(el, `nav_${i}`)),
  section_label_sample: sectionLabels.map((el, i) => tok(el, `label_${i}`)),
  fonts_unique: Array.from(fonts).slice(0, 10),
  colors_unique_count: colors.size,
  bgs_unique_count: bgs.size,
  bgs_top: Array.from(bgs).slice(0, 15),
  radii_unique: Array.from(radii).slice(0, 10),
  cssVars: (() => {
    const styles = getComputedStyle(html);
    const vars = {};
    for (let i = 0; i < styles.length; i++) {
      const name = styles[i];
      if (name.startsWith('--') && name.includes('token')) vars[name] = styles.getPropertyValue(name).trim();
    }
    return Object.keys(vars).length ? vars : 'none';
  })(),
};
JSON.stringify(result, null, 2);
